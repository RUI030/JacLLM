"""SFT on agent trajectories that carry images: VLM loaded in 4-bit, LoRA on the language model only, vision frozen.

Rows come from script/dataset/trajectory/clean.py: {"messages", "tools", "meta"}; image parts are
{"type": "image", "image": <path>} and an assistant message with "weight": 0 is context only.
"""

import argparse, json, math, os, sys, time
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")   # 64k steps fragment the allocator
from pathlib import Path

from unsloth import FastVisionModel   # must precede transformers to enable optimizations
import torch
from PIL import Image
from torch.utils.checkpoint import checkpoint
from transformers import Trainer, TrainingArguments
import transformers.models.qwen3_5.modeling_qwen3_5 as modeling_qwen3_5

# Under Unsloth the mask builder never takes its "use SDPA is_causal" shortcut, so every step built a dense additive
# L x L mask (8 GB at 64k; Unsloth's SDPA wrapper only drops boolean causal masks). Rows here are batch 1 with no
# padding and no cache, so the mask is plain causal: return None and SDPA runs with is_causal=True.
_create_causal_mask = modeling_qwen3_5.create_causal_mask


def plain_causal_mask(*args, **kwargs):
    pos = kwargs.get("position_ids")
    sequential = pos is None or (pos.shape[0] == 1 and bool((pos[0] == torch.arange(pos.shape[-1], device=pos.device)).all()))
    if args or not sequential or any(kwargs.get(k) is not None for k in ("attention_mask", "past_key_values",
                                                                          "or_mask_function", "and_mask_function")):
        return _create_causal_mask(*args, **kwargs)
    return None


modeling_qwen3_5.create_causal_mask = plain_causal_mask

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from train.utils import print_gpu_banner

# Setting =================================================
def default_config() -> dict:
    return {
        "base_model":     "output/model/JacLLM-SFT-Ornith-9B-v1.35-vlm",   # merged v1.35 + VLM config/processor
        "data_dir":       "dataset/raw/prod/sft/prod-64k",
        "out_dir":        "",
        "run_name":       "prod-img-sft",
        "max_seq_length": 65536,
        # The template decides what the model learns before its answer. The original Ornith template opens
        # "<think>\n" as the generation prompt (thinking: labels hold reasoning + "</think>" + answer); v1.35's own
        # copy forces enable_thinking=false. Taken from this repo id (or a .jinja path), not from base_model.
        "chat_template":  "ornith-ai/Ornith-1.5-9B",
        "load_in_4bit":   True,
        "epochs":         1,
        "batch_size":     1,
        "grad_acc":       8,
        "lr":             5e-5,          # continuing from a trained SFT model: well below the 2e-4 it was trained with
        "scheduler":      "cosine",
        "warmup_steps":   3,
        "weight_decay":   1e-3,
        "optimizer":      "adamw_8bit",
        "save_steps":     10,
        "log_freq":       1,
        "lora_rank":      16,
        "lora_alpha":     16,
        "lora_dropout":   0,
        "rslora":         True,
        "target_module":  ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "grad_checkpt":   True,          # on-GPU checkpoints: host RAM on this server cannot hold offloaded ones
        "loss_chunk":     2048,          # label positions per lm_head chunk (a full 64k x 248k logit matrix is ~32 GB)
        "seed":           3407,
        "max_steps":      -1,
    }


# Functions ===============================================
def chat_messages(row: dict) -> tuple[list[dict], list[dict], list[str], list[int]]:
    """Row -> (messages for the template, tools, image paths in order, weight per assistant message)."""
    msgs, paths, weights = [], [], []
    for m in row["messages"]:
        m = {k: v for k, v in m.items() if v is not None and k != "weight"}
        if "tool_calls" in m:
            m["tool_calls"] = [{**c, "function": {**c["function"], "arguments": json.loads(c["function"]["arguments"])}}
                               for c in m["tool_calls"]]
        if isinstance(m.get("content"), list):
            paths += [p["image"] for p in m["content"] if p.get("type") == "image"]
        msgs.append(m)
    weights = [m.get("weight", 1) for m in row["messages"] if m["role"] == "assistant"]
    return msgs, json.loads(row["tools"]) if row.get("tools") else None, paths, weights


def generation_prompt(tok) -> str:
    """What the template puts after the last message when asked to generate, e.g. "<|im_start|>assistant\n<think>\n"."""
    m = [{"role": "user", "content": "x"}]
    full = tok.apply_chat_template(m, tokenize=False, add_generation_prompt=True)
    return full[len(tok.apply_chat_template(m, tokenize=False)):]


def set_chat_template(processor, source: str) -> None:
    if source.endswith(".jinja"):
        tpl = Path(source).read_text()
    else:
        from huggingface_hub import hf_hub_download
        tpl = Path(hf_hub_download(source, "chat_template.jinja")).read_text()
    processor.tokenizer.chat_template = tpl
    processor.chat_template = tpl


class Collator:
    """Render, expand images with the processor, and label the assistant blocks whose message has weight 1.

    Labels start where the model starts generating at inference: after the template's generation prompt. A block
    that does not begin with that prompt (e.g. reasoning_content under a template that forces an empty <think>)
    would be learned at the wrong offset, so it is an error, not a silent mis-label."""
    def __init__(self, processor, max_len: int):
        self.p, self.max_len = processor, max_len
        tok = processor.tokenizer
        gen = generation_prompt(tok)
        self.head = tok("<|im_start|>assistant\n", add_special_tokens=False)["input_ids"]
        self.gen = tok(gen, add_special_tokens=False)["input_ids"]
        assert self.gen[:len(self.head)] == self.head, f"unexpected generation prompt {gen!r}"
        self.gen_text = gen[len("<|im_start|>assistant\n"):]
        self.end = tok.convert_tokens_to_ids("<|im_end|>")
        self.nl = tok("\n", add_special_tokens=False)["input_ids"][0]
        self.skipped = 0

    def encode(self, row: dict) -> dict | None:
        msgs, tools, paths, weights = chat_messages(row)
        text = self.p.tokenizer.apply_chat_template(msgs, tools=tools, tokenize=False)
        imgs = [Image.open(p).convert("RGB") for p in paths] or None
        enc = self.p(text=[text], images=imgs, return_tensors="pt")
        ids = enc["input_ids"][0]
        labels = torch.full_like(ids, -100)
        h, blocks, i = len(self.head), [], 0
        L = ids.tolist()
        while i <= len(L) - h:
            if L[i:i + h] == self.head:
                j = L.index(self.end, i + h) if self.end in L[i + h:] else len(L) - 1
                j += 1 if j + 1 < len(L) and L[j + 1] == self.nl else 0     # sft.py trains "<|im_end|>\n" too
                blocks.append((i + h, j + 1))
                i = j
            i += 1
        if len(blocks) != len(weights) or len(L) > self.max_len:
            self.skipped += 1
            print(f"skip {row['meta'].get('fp')}: {len(blocks)} assistant blocks vs {len(weights)} messages, "
                  f"{len(L)} tokens", flush=True)
            return None
        g = self.gen_text                                               # e.g. "<think>\n" after the role header
        for (a, b), w in zip(blocks, weights):
            if not w:
                continue
            k = a                                                       # first token wholly after the prompt, as in
            while k < b and len(self.p.tokenizer.decode(L[a:k])) < len(g):   # sft.py's offset rule: "\n\n" of an
                k += 1                                                  # empty <think> straddles it and is not trained
            if not self.p.tokenizer.decode(L[a:k]).startswith(g):
                raise ValueError(f"{row['meta'].get('fp')}: an assistant block does not start with the generation "
                                 f"prompt {g!r}; the template and the data disagree (reasoning under a non-thinking "
                                 "template?)")
            labels[k:b] = ids[k:b]
        # no attention_mask: batch 1 has no padding, and passing one makes the model build a dense L x L mask (8 GB at 64k)
        out = {"input_ids": ids[None], "labels": labels[None]}
        if imgs:
            out["pixel_values"], out["image_grid_thw"] = enc["pixel_values"], enc["image_grid_thw"]
        if "mm_token_type_ids" in enc:                                  # M-RoPE needs to know which tokens are image
            out["mm_token_type_ids"] = enc["mm_token_type_ids"]
        return out

    def __call__(self, rows: list[dict]) -> dict:
        assert len(rows) == 1, "batch_size must be 1 (samples are up to max_seq_length long)"
        return self.encode(rows[0]) or {"skip": torch.tensor(1)}


class ChunkedLossTrainer(Trainer):
    """Loss from hidden states at labelled positions only, lm_head applied in checkpointed chunks."""
    loss_chunk = 2048

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        if "skip" in inputs:
            z = sum(p.sum() * 0 for p in model.parameters() if p.requires_grad)
            return (z, None) if return_outputs else z
        labels = inputs.pop("labels")
        base = model.get_base_model() if hasattr(model, "get_base_model") else model
        hidden = base.model(**inputs).last_hidden_state                # (1, L, H), no logits materialized
        tgt = labels[:, 1:]
        keep = tgt != -100
        h, t = hidden[:, :-1][keep], tgt[keep]
        head = base.lm_head
        total = h.new_zeros((), dtype=torch.float32)
        for s in range(0, len(t), self.loss_chunk):
            total = total + checkpoint(
                lambda x, y: torch.nn.functional.cross_entropy(head(x).float(), y, reduction="sum"),
                h[s:s + self.loss_chunk], t[s:s + self.loss_chunk], use_reentrant=False)
        n = num_items_in_batch if num_items_in_batch is not None else max(1, len(t))
        loss = total / n
        return (loss, None) if return_outputs else loss


def load(cfg: dict):
    model, processor = FastVisionModel.from_pretrained(
        cfg["base_model"], load_in_4bit=cfg["load_in_4bit"], max_seq_length=cfg["max_seq_length"],
        use_gradient_checkpointing=cfg["grad_checkpt"])
    set_chat_template(processor, cfg["chat_template"])
    print(f"generation prompt: {generation_prompt(processor.tokenizer)!r}")
    model = FastVisionModel.get_peft_model(
        model,
        finetune_vision_layers     = False,
        finetune_language_layers   = True,
        finetune_attention_modules = True,
        finetune_mlp_modules       = True,
        target_modules             = cfg["target_module"],
        r                          = cfg["lora_rank"],
        lora_alpha                 = cfg["lora_alpha"],
        lora_dropout               = cfg["lora_dropout"],
        bias                       = "none",
        use_rslora                 = cfg["rslora"],
        random_state               = cfg["seed"],
        use_gradient_checkpointing = cfg["grad_checkpt"],
    )
    return model, processor


def rows(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open()] if path.exists() else []


def run_sft_img(config: dict) -> None:
    cfg = {**default_config(), **config}
    if not cfg["out_dir"]:
        cfg["out_dir"] = f"output/adapter/{time.strftime('%m-%d_%H-%M')}-{cfg['run_name']}"
    out = Path(cfg["out_dir"])
    (out / "runs").mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")
    model, processor = load(cfg)
    train = rows(Path(cfg["data_dir"]) / "train.jsonl")
    valid = rows(Path(cfg["data_dir"]) / "valid.jsonl")
    collate = Collator(processor, cfg["max_seq_length"])
    ChunkedLossTrainer.loss_chunk = cfg["loss_chunk"]
    args = TrainingArguments(
        output_dir                  = str(out),
        per_device_train_batch_size = cfg["batch_size"],
        gradient_accumulation_steps = cfg["grad_acc"],
        num_train_epochs            = cfg["epochs"],
        max_steps                   = cfg["max_steps"],
        learning_rate               = cfg["lr"],
        lr_scheduler_type           = cfg["scheduler"],
        warmup_steps                = cfg["warmup_steps"],
        weight_decay                = cfg["weight_decay"],
        optim                       = cfg["optimizer"],
        logging_steps               = cfg["log_freq"],
        save_steps                  = cfg["save_steps"],
        bf16                        = True,
        seed                        = cfg["seed"],
        report_to                   = ["tensorboard"],
        logging_dir                 = str(out / "runs"),
        remove_unused_columns       = False,
        dataloader_num_workers      = 0,
        gradient_checkpointing      = False,     # Unsloth already wraps the layers
    )
    trainer = ChunkedLossTrainer(model=model, args=args, train_dataset=train, data_collator=collate)
    print_gpu_banner()
    trainer.train()
    model.save_pretrained(str(out / "adapter"))
    processor.save_pretrained(str(out / "adapter"))
    if valid:
        model.eval()
        losses = []
        with torch.no_grad():
            for r in valid:
                b = collate.encode(r)
                if b:
                    b = {k: v.to(model.device) for k, v in b.items()}
                    losses.append(trainer.compute_loss(model, b).item())
        (out / "valid_loss.json").write_text(json.dumps({"mean": sum(losses) / max(1, len(losses)), "per_row": losses}) + "\n")
        print(f"valid loss {sum(losses) / max(1, len(losses)):.4f} over {len(losses)} rows")
    print(f"skipped rows: {collate.skipped}")


# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--data-dir")
    cli.add_argument("--base-model")
    cli.add_argument("--lr", type=float)
    cli.add_argument("--rank", type=int, dest="lora_rank")
    cli.add_argument("--max-steps", type=int)
    cli.add_argument("--grad-acc", type=int)
    cli.add_argument("--max-seq-length", type=int)
    cli.add_argument("--out-dir")
    cli.add_argument("--run-name")
    a = cli.parse_args()
    run_sft_img({k: v for k, v in vars(a).items() if v is not None})
