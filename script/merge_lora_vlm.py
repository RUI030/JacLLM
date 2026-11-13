"""Merge a LoRA adapter into a bf16 safetensors VLM base at the tensor level, keeping the vision tower.

`merge_lora.py` loads through Unsloth with `text_only=True`, which drops `model.visual.*`; this script never
builds a model: for each base shard, W += scale * B @ A on the LoRA targets (fp32 on GPU, stored in the base
dtype) and every other tensor (visual tower, mtp, lm_head) is copied unchanged, so RAM stays around one shard.
The adapter's `chat_template.jinja` (the template it was trained with) replaces the base one.

Usage:
    python script/merge_lora_vlm.py \\
        --base output/model/JacLLM-SFT-Ornith-9B-v1.35-vlm \\
        --adapter output/adapter/<run>/adapter \\
        --out output/model/<name>
"""

import argparse, json, shutil
from pathlib import Path

import torch
from safetensors import safe_open
from safetensors.torch import save_file

# Functions ===============================================
def lora_pairs(adapter: Path) -> dict:
    """{base weight key: {"A": tensor, "B": tensor}} from adapter_model.safetensors."""
    pairs = {}
    with safe_open(adapter / "adapter_model.safetensors", "pt") as f:
        for k in f.keys():
            mod, ab = k.removeprefix("base_model.model.").rsplit(".lora_", 1)
            pairs.setdefault(mod + ".weight", {})[ab[0]] = f.get_tensor(k)
    return pairs


def merge(base: Path, adapter: Path, out: Path) -> None:
    """Write base + scale * B @ A shard by shard to `out`, copy the non-weight files, swap in the adapter template."""
    cfg = json.loads((adapter / "adapter_config.json").read_text())
    if cfg.get("use_dora"):
        raise SystemExit("DoRA adapters are not supported (magnitude vector is not a plain B @ A)")
    r, alpha = cfg["r"], cfg["lora_alpha"]
    scale = alpha / r**0.5 if cfg.get("use_rslora") else alpha / r
    lora = lora_pairs(adapter)
    print(f"r={r} alpha={alpha} rslora={cfg.get('use_rslora')} scale={scale} targets={len(lora)}")

    out.mkdir(parents=True, exist_ok=True)
    index = json.loads((base / "model.safetensors.index.json").read_text())
    merged = set()
    for shard in sorted(set(index["weight_map"].values())):
        tensors = {}
        with safe_open(base / shard, "pt") as f:
            meta = f.metadata()
            for k in f.keys():
                t = f.get_tensor(k)
                if k in lora:
                    A, B = lora[k]["A"].cuda().float(), lora[k]["B"].cuda().float()
                    t = (t.cuda().float() + scale * (B @ A)).to(t.dtype).cpu()
                    merged.add(k)
                tensors[k] = t
        save_file(tensors, out / shard, metadata=meta)
        print(f"{shard}: {len(tensors)} tensors")
        del tensors

    missing = set(lora) - merged
    if missing:     # adapter keys that match no base key (e.g. a text_only adapter on a VLM base) would silently be dropped
        raise SystemExit(f"{len(missing)} LoRA targets not in the base, e.g. {sorted(missing)[:3]}")
    print(f"merged {len(merged)} tensors")

    for p in base.iterdir():
        if p.suffix != ".safetensors":
            shutil.copy(p.resolve(), out / p.name)
    # serve with the template the adapter was trained with; tokenizer_config's copy would override the file
    shutil.copy(adapter / "chat_template.jinja", out / "chat_template.jinja")
    tc = json.loads((out / "tokenizer_config.json").read_text())
    tc.pop("chat_template", None)
    (out / "tokenizer_config.json").write_text(json.dumps(tc, indent=2, ensure_ascii=False) + "\n")
    print("done", out)


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", type=Path, required=True, help="bf16 safetensors model dir (with model.safetensors.index.json)")
    ap.add_argument("--adapter", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    merge(a.base, a.adapter, a.out)
