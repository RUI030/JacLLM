"""Shared helpers for CPT / SFT / GRPO training scripts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import torch
from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template

from utils.model import restore_architectures


REPO_ROOT   = Path(__file__).resolve().parent.parent.parent
OUTPUT_ROOT = REPO_ROOT / "output" / "adapter"


def finalize_out_dir(cfg: dict) -> None:
    """Populate cfg['out_dir'] with `<OUTPUT_ROOT>/<MM-DD_HH-MM>-<run_name>` if unset."""
    if cfg.get("out_dir"):
        return
    ts  = datetime.now().strftime("%m-%d_%H-%M")
    tag = cfg.get("run_name") or "run"
    cfg["out_dir"] = str((OUTPUT_ROOT / f"{ts}-{tag}").resolve())


def model_source(cfg: dict) -> str:
    """What `from_pretrained` loads: the resume checkpoint, else the adapter, else the base.

    A checkpoint is itself a PEFT adapter dir, so a resumed run keeps the LoRA
    shape it was trained with. A CPT->SFT stage keeps the CPT adapter's alpha
    rather than picking up the recipe's.
    """
    return cfg["resume_from"] or cfg["adapter"] or cfg["base_model"]


def load_trainable(cfg: dict):
    """Load the model to train and attach a fresh LoRA unless one comes with it.

    `adapter` or `resume_from` set means from_pretrained already wrapped the model
    with PEFT; get_peft_model is skipped to avoid double-wrapping. The LoRA shape is
    then frozen by the checkpoint; to change rank/target_modules, merge first.
    """
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name     = model_source(cfg),
        max_seq_length = cfg["max_seq_length"],
        dtype          = cfg["dtype"],
        load_in_4bit   = cfg["load_in_4bit"],
        text_only      = cfg["text_only"],
        # An adapter/resume load wraps the model inside from_pretrained, whose default "unsloth" offloads
        # checkpoints to host RAM (~0.65GB per 1k tokens on 27B) and ignores recipe.grad_checkpt.
        use_gradient_checkpointing = cfg["grad_checkpt"],
    )
    if not (cfg["adapter"] or cfg["resume_from"]):
        model = FastLanguageModel.get_peft_model(
            model,
            r                          = cfg["lora_rank"],
            target_modules             = cfg["target_module"],
            lora_alpha                 = cfg["lora_alpha"],
            lora_dropout               = cfg["lora_dropout"],
            bias                       = cfg["bias"],
            use_gradient_checkpointing = cfg["grad_checkpt"],
            random_state               = cfg["seed"],
            use_rslora                 = cfg["rslora"],
            loftq_config               = None,
        )
    restore_architectures(model)
    return model, tokenizer


def ensure_chat_template(tokenizer, cfg: dict):
    """Apply recipe.chat_template if set; otherwise require the base tokenizer's native one."""
    if cfg["chat_template"]:
        return get_chat_template(tokenizer, chat_template=cfg["chat_template"])
    if not tokenizer.chat_template:
        raise ValueError(
            "The base tokenizer has no chat template; set recipe.chat_template explicitly"
        )
    return tokenizer


def print_gpu_banner() -> None:
    """Print current GPU name and reserved / total memory."""
    stats    = torch.cuda.get_device_properties(0)
    reserved = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
    total    = round(stats.total_memory / 1024 / 1024 / 1024, 3)
    print(f"GPU = {stats.name}. Max memory = {total} GB.")
    print(f"{reserved} GB of memory reserved.")


def save_adapter(model, tokenizer, cfg: dict, stage: str) -> None:
    """Persist the trained adapter (or merged model) and optionally push to HF."""
    out = cfg["out_dir"]
    if cfg.get("merge"):
        model.save_pretrained_merged(f"{out}/merged", tokenizer, save_method=cfg["save_method"])
    else:
        model.save_pretrained(f"{out}/adapter")
        tokenizer.save_pretrained(f"{out}/adapter")
    if cfg.get("push_hf"):
        model_name = Path(cfg["base_model"]).name
        repo = cfg.get("hf_repo") or f"{cfg['hf_org']}/JacLLM-{model_name}"
        if stage in ("sft", "grpo"):
            repo += f"-{stage}"
        if cfg.get("merge"):
            model.push_to_hub_merged(
                repo, tokenizer,
                save_method=cfg["save_method"], token=cfg["hf_token"],
            )
        else:
            model.push_to_hub(repo, token=cfg["hf_token"])
            tokenizer.push_to_hub(repo, token=cfg["hf_token"])
