"""Shared Unsloth model loading + single-turn generation."""

from unsloth import FastLanguageModel
import torch


def restore_architectures(model) -> None:
    """Set `config.architectures` where the Unsloth 2026.8.19 text-only VLM path left it None.

    `generate()` (plain or inside GRPOTrainer) iterates it and fails on None.
    """
    base = model.get_base_model() if hasattr(model, "get_base_model") else model
    arch = type(base).__name__
    seen = set()
    for cfg in (model.config, base.config):
        if id(cfg) in seen:
            continue
        seen.add(id(cfg))
        if not getattr(cfg, "architectures", None):
            cfg.architectures = [arch]


def load_model(
    model_name: str,
    max_seq_length: int,
    load_in_4bit: bool = True,
    dtype=None,
    device_map=None,
):
    """Load base model or LoRA adapter path.

    Restores `config.architectures` after the Unsloth 2026.8.19 text-only VLM
    adapter path leaves it as None, which breaks `generate()`.

    `device_map` defaults to letting unsloth/accelerate decide; pass
    {"": "cuda:0"} to force everything on the primary GPU (avoids CPU spill
    when loading an adapter checkpoint on a modest VRAM box).
    """
    print(f"Loading: {model_name}")
    kwargs = dict(
        model_name=model_name,
        max_seq_length=max_seq_length,
        dtype=dtype,
        load_in_4bit=load_in_4bit,
        text_only=True,
        fast_inference=False,
    )
    if device_map is not None:
        kwargs["device_map"] = device_map
    model, tokenizer = FastLanguageModel.from_pretrained(**kwargs)

    restore_architectures(model)

    # If the loaded path was a LoRA adapter, fold it into the base weights so
    # inference matches merge_lora.py output. Loading Ornith adapters via
    # unsloth's text-only unwrap otherwise silently mis-attaches PEFT and
    # returns raw base-model output. Base or already-merged model dirs skip
    # this branch (no peft_config).
    #
    # MoE adapters with LoRA on fused expert parameters (`target_parameters`,
    # e.g. Qwen3-Coder-30B-A3B) are the opposite case: merge_and_unload on the
    # 4-bit base generates exactly like the base model, while the unmerged
    # adapter produces the trained output. Keep those attached.
    #
    # Any adapter on a 4-bit (NF4) base stays attached too: folding the LoRA delta
    # into quantised weights re-rounds them. On Qwen3.8-27B (r32, checkpoint-90) the
    # merged path scored 24% on the Nitin test split vs ~52% unmerged on a 25-problem
    # A/B, and the training itself had used the unmerged adapter. A merge for export
    # goes through the original bf16 shards instead (see merge_lora.py).
    if hasattr(model, "peft_config"):
        if any(getattr(c, "target_parameters", None) for c in model.peft_config.values()):
            print("MoE expert LoRA (target_parameters): keeping adapter unmerged for inference")
        elif load_in_4bit:
            print("4-bit base: keeping adapter unmerged for inference")
        else:
            print("Merging LoRA into base (in-memory) for inference")
            model = model.merge_and_unload()

    FastLanguageModel.for_inference(model)
    tokenizer.truncation_side = "left"
    return model, tokenizer


def generate(
    model,
    tokenizer,
    messages,
    max_new_tokens: int = 1024,
    temperature: float = 0.0,
    top_p: float = 0.9,
    repetition_penalty: float = 1.05,
    enable_thinking: bool = False,
) -> str:
    """Generate one assistant reply given a full message list."""
    max_seq = getattr(model.config, "max_position_embeddings", None) or 4096
    prompt_limit = max_seq - max_new_tokens
    if prompt_limit <= 0:
        raise ValueError("max_new_tokens must be smaller than model max seq")

    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=enable_thinking,
        truncation=True,
        max_length=prompt_limit,
        return_tensors="pt",
        return_dict=True,
    ).to("cuda")

    args = {
        "max_new_tokens": max_new_tokens,
        "max_length": None,   # silence HF "both set" warning; max_new_tokens is what we want
        "use_cache": True,
        "repetition_penalty": repetition_penalty,
        "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
    }
    if temperature > 0:
        args.update(do_sample=True, temperature=temperature, top_p=top_p)
    else:
        args["do_sample"] = False

    prompt_tokens = inputs["input_ids"].shape[-1]
    with torch.inference_mode():
        outputs = model.generate(**inputs, **args)
    return tokenizer.decode(outputs[0, prompt_tokens:], skip_special_tokens=True).strip()


def generate_batched(
    model,
    tokenizer,
    messages_list,
    max_new_tokens: int = 1024,
    temperature: float = 0.0,
    top_p: float = 0.9,
    repetition_penalty: float = 1.05,
    enable_thinking: bool = False,
) -> list[str]:
    """Generate one reply per messages list, all in a single batched forward pass.

    Left-pads prompts so autoregressive generation from `input_ids.shape[-1]`
    still aligns per sample.
    """
    if not messages_list:
        return []

    max_seq = getattr(model.config, "max_position_embeddings", None) or 4096
    prompt_limit = max_seq - max_new_tokens
    if prompt_limit <= 0:
        raise ValueError("max_new_tokens must be smaller than model max seq")

    prompt_ids = [
        tokenizer.apply_chat_template(
            m,
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
            truncation=True,
            max_length=prompt_limit,
        )
        for m in messages_list
    ]

    pad_id = tokenizer.pad_token_id
    if pad_id is None:
        pad_id = tokenizer.eos_token_id

    prev_side = tokenizer.padding_side
    tokenizer.padding_side = "left"
    try:
        batch = tokenizer.pad(
            {"input_ids": prompt_ids},
            padding=True,
            return_tensors="pt",
        )
    finally:
        tokenizer.padding_side = prev_side

    batch = {k: v.to("cuda") for k, v in batch.items()}

    args = {
        "max_new_tokens": max_new_tokens,
        "max_length": None,
        "use_cache": True,
        "repetition_penalty": repetition_penalty,
        "pad_token_id": pad_id,
    }
    if temperature > 0:
        args.update(do_sample=True, temperature=temperature, top_p=top_p)
    else:
        args["do_sample"] = False

    padded_prompt_len = batch["input_ids"].shape[-1]
    with torch.inference_mode():
        outputs = model.generate(**batch, **args)
    completions = outputs[:, padded_prompt_len:]
    return [
        tokenizer.decode(seq, skip_special_tokens=True).strip()
        for seq in completions
    ]
