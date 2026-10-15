import argparse, json
import sys
from pathlib import Path

from datasets import load_dataset
from unsloth import (
    UnslothTrainer,
    UnslothTrainingArguments,
    is_bfloat16_supported,
)
from unsloth.chat_templates import train_on_responses_only

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # script/: `utils` is script/utils, train helpers are train.utils
from train.utils import ensure_chat_template, finalize_out_dir, load_trainable, print_gpu_banner, save_adapter


# Defaults (also the config schema for train.py) ============================
def default_config() -> dict:
    return {
        # Model
        "base_model":     "ornith-ai/Ornith-1.5-9B",
        "adapter":        "",
        "resume_from":    "",
        "max_seq_length": 4096,
        "dtype":          None,
        "load_in_4bit":   True,
        "text_only":      True,
        "chat_template":  None,  # preserve the base tokenizer's native template
        # Output
        "run_name":       "",
        "out_dir":        "",
        "merge":          False,
        "save_method":    "merged_4bit",
        "push_hf":        False,
        "hf_org":         "jaseci",
        "hf_repo":        "",
        "hf_token":       "",
        "report_to":      ["tensorboard"],
        "log_freq":       10,
        # Hyperparameters
        "epochs":         1,
        "batch_size":     1,
        "grad_acc":       10,
        "optimizer":      "adamw_8bit",
        "lr":             2e-4,       # SFT LoRA standard, higher than CPT's 5e-5
        "embed_lr":       0,          # embed/lm_head not in TARGET_MODULE
        "scheduler":      "linear",
        "warmup_steps":   10,
        "max_steps":      -1,
        "weight_decay":   1e-3,
        "save_steps":     100,
        "save_total_limit": None,  # keep N newest checkpoint-*/ dirs; None = keep all
        "train_sampling": "random",  # random | sequential (set by mixer for sequential recipes)
        "eval_steps":     0.1,
        "do_eval":        False,      # SFT eval OOMs on 16GB VRAM; use gate/loss post-hoc
        # LoRA
        "lora_rank":      64,          # SFT: lower than CPT's 128
        "lora_alpha":     16,
        "lora_dropout":   0,
        "target_module": ["q_proj", "k_proj", "v_proj",
                          "o_proj", "gate_proj",
                          "up_proj", "down_proj"],  # NO embed/lm_head for SFT
        "rslora":         True,
        "bias":           "none",
        "grad_checkpt":   "unsloth",
        # Misc
        "seed":           3407,
        "packing":        False,  # True: response mask is built per conversation before packing
        # Response-only masking (chat template dependent)
        "instruction_part": "<|im_start|>user\n",
        "response_part":    "<|im_start|>assistant\n",
    }


def chat_inputs(row: dict) -> tuple[list[dict], list[dict] | None]:
    """One dataset row -> (messages, tools) as the chat template takes them.

    Tool-call datasets (`dataset/sft/tool_fim/`) store `tools` and every call's
    `arguments` as JSON strings, because Arrow would merge the keys of differing
    schemas; Arrow also fills keys a message lacks with None, which the template
    would render (`tool_calls: None`), so those are dropped.
    """
    msgs = []
    for m in row["messages"]:
        m = {k: v for k, v in m.items() if v is not None}
        if "tool_calls" in m:
            m["tool_calls"] = [{**c, "function": {**c["function"], "arguments": json.loads(c["function"]["arguments"])}}
                               for c in m["tool_calls"]]
        msgs.append(m)
    tools = row.get("tools")
    return msgs, json.loads(tools) if tools else None


def apply_chat_template(batch: dict, tokenizer) -> dict:
    rows = [dict(zip(batch, vals)) for vals in zip(*batch.values())]
    return {
        "text": [
            tokenizer.apply_chat_template(msgs, tools=tools, tokenize=False, add_generation_prompt=False)
            for msgs, tools in map(chat_inputs, rows)
        ]
    }


def tokenize_with_assistant_mask(msgs: list[dict], tools: list[dict] | None, tokenizer, max_len: int) -> dict:
    """Tokenize one conversation; `labels` keep only each assistant turn's tokens.

    Everything the model writes is trained: reply text, tool calls and the turn's
    <|im_end|>. System prompt (incl. rendered tool schemas), user turns and tool
    results stay context. An assistant message with `weight: 0` (a denied or looped
    response, trajectory/README.md) stays context too.

    Packing needs the mask per conversation: train_on_responses_only runs on the
    packed sequence and unmasks from an assistant marker to the next user marker,
    which then spans the following conversation's system prompt. The masked span is
    what the template renders for the turn (content + <|im_end|>\\n), i.e. the same
    tokens the unpacked path trains on.
    """
    render = lambda m, gen: tokenizer.apply_chat_template(
        m, tools=tools, tokenize=False, add_generation_prompt=gen
    )
    text  = render(msgs, False)
    spans = []
    for i, m in enumerate(msgs):
        if m["role"] != "assistant" or m.get("weight", 1) == 0:
            continue
        start, end = len(render(msgs[:i], True)), len(render(msgs[: i + 1], False))
        if not text.startswith(render(msgs[: i + 1], False)):
            raise ValueError("Chat template renders history differently from the full "
                             "conversation; per-turn assistant spans would be misaligned")
        spans.append((start, end))

    enc    = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    ids    = enc["input_ids"][:max_len]
    labels = [t if any(s <= a < e for s, e in spans) else -100
              for t, (a, _) in zip(ids, enc["offset_mapping"])]
    return {"input_ids": ids, "labels": labels}


def run_sft(config: dict, train_ds, eval_ds=None):
    """Run one SFT training loop over the given HF datasets.

    `train_ds` and (optional) `eval_ds` must expose a `messages` field — a
    list of role/content dicts. The chat template is applied here.
    """
    cfg = {**default_config(), **config}
    finalize_out_dir(cfg)
    Path(cfg["out_dir"], "runs").mkdir(parents=True, exist_ok=True)

    model, tokenizer = load_trainable(cfg)
    tokenizer = ensure_chat_template(tokenizer, cfg)

    if cfg["packing"]:
        # Pre-tokenized input_ids + labels: Unsloth skips its own tokenizing and
        # packs both columns together (an assistant_masks column would be dropped
        # by Unsloth's column selection). Rows truncated down to no assistant
        # tokens are dropped.
        prep = lambda ds, split: ds.map(
            lambda r: tokenize_with_assistant_mask(*chat_inputs(r), tokenizer, cfg["max_seq_length"]),
            remove_columns=ds.column_names, desc=f"Tokenizing + assistant mask ({split})",
        ).filter(lambda r: any(l != -100 for l in r["labels"]),
                 desc=f"Dropping rows with no assistant tokens ({split})")
    else:
        prep = lambda ds, split: ds.map(
            lambda b: apply_chat_template(b, tokenizer),
            batched=True, desc=f"Applying chat template ({split})",
        )
    train_ds = prep(train_ds, "train")
    eval_ds  = prep(eval_ds, "valid") if eval_ds is not None and cfg["do_eval"] else None

    training_args = UnslothTrainingArguments(
        per_device_train_batch_size = cfg["batch_size"],
        gradient_accumulation_steps = cfg["grad_acc"],

        num_train_epochs = cfg["epochs"],
        max_steps        = cfg["max_steps"],
        warmup_steps     = cfg["warmup_steps"],

        learning_rate           = cfg["lr"],
        embedding_learning_rate = cfg["embed_lr"],

        optim             = cfg["optimizer"],
        weight_decay      = cfg["weight_decay"],
        lr_scheduler_type = cfg["scheduler"],

        logging_steps = cfg["log_freq"],
        save_steps       = cfg["save_steps"],
        save_total_limit = cfg["save_total_limit"],

        train_sampling_strategy = cfg["train_sampling"],

        fp16 = not is_bfloat16_supported(),
        bf16 = is_bfloat16_supported(),

        seed       = cfg["seed"],
        output_dir = cfg["out_dir"],

        eval_strategy = "steps" if eval_ds is not None else "no",
        eval_steps    = cfg["eval_steps"] if eval_ds is not None else None,

        report_to   = cfg["report_to"],
        logging_dir = f"{cfg['out_dir']}/runs",
    )

    trainer = UnslothTrainer(
        model              = model,
        tokenizer          = tokenizer,
        train_dataset      = train_ds,
        eval_dataset       = eval_ds,
        dataset_text_field = "text",
        max_seq_length     = cfg["max_seq_length"],
        dataset_num_proc   = 4,
        packing            = cfg["packing"],
        args               = training_args,
    )

    # Loss only on assistant tokens (mask system + user). Packed runs already
    # carry labels from tokenize_with_assistant_mask.
    if not cfg["packing"]:
        trainer = train_on_responses_only(
            trainer,
            instruction_part = cfg["instruction_part"],
            response_part    = cfg["response_part"],
        )

    print_gpu_banner()
    trainer.train(resume_from_checkpoint=cfg["resume_from"] or None)
    save_adapter(model, tokenizer, cfg, stage="sft")


# CLI (single-dataset workflow — recipes go through train.py) ===============
def config_from_cli() -> tuple[dict, str, str]:
    cli = argparse.ArgumentParser(add_help=False)
    cli.add_argument("--ds", "--dataset", dest="dataset")
    cli.add_argument("--task", "--task-type", dest="task")
    cli.add_argument("--adapter", "--adapter-path", dest="adapter")
    cli.add_argument("--epochs", type=int)
    cli.add_argument("--lr", type=float)
    cli.add_argument("--rank", type=int)
    cli.add_argument("--steps", dest="max_steps", type=int)
    cli.add_argument("--resume", dest="resume",
                     help="checkpoint dir to resume from (mutex with --adapter)")
    args, _ = cli.parse_known_args()
    if args.resume and args.adapter:
        raise SystemExit(
            "--resume and --adapter are mutually exclusive; --resume already "
            "loads adapter weights + optimizer state"
        )

    cfg  = default_config()
    task = args.task    or "code_completion"
    ds   = args.dataset or "Nitin-9k-py2jac-idiom"
    cfg["adapter"]     = args.adapter or ""
    cfg["resume_from"] = args.resume  or ""
    if args.epochs    is not None: cfg["epochs"]    = args.epochs
    if args.lr        is not None: cfg["lr"]        = args.lr
    if args.rank      is not None: cfg["lora_rank"] = args.rank
    if args.max_steps is not None: cfg["max_steps"] = args.max_steps
    cfg["run_name"] = f"sft-{task}-{ds}"

    data_dir = Path(__file__).resolve().parent.parent.parent / "dataset" / "sft"
    return cfg, str(data_dir / task / ds / "train.jsonl"), str(data_dir / task / ds / "valid.jsonl")


if __name__ == "__main__":
    cfg, train_fp, valid_fp = config_from_cli()

    train_ds = load_dataset("json", data_files={"train": [train_fp]}, split="train")
    eval_ds  = None
    if cfg["do_eval"] and Path(valid_fp).is_file():
        eval_ds = load_dataset("json", data_files={"valid": [valid_fp]}, split="valid")

    run_sft(cfg, train_ds, eval_ds)
