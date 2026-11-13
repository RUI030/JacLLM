"""Token-weighted loss of base, base + adapter (unmerged) and the merged model on the shortest SFT rows, all bf16.

A merge is right when "merged" matches "base + adapter" and both differ from "base". Rows are encoded with
`train/sft_img.py`'s collator, so images and the trained chat template are used exactly as in training.

    python script/eval/probe/merge_loss.py --base output/model/JacLLM-SFT-Ornith-9B-v1.35-vlm \\
        --adapter output/adapter/<run>/adapter --merged output/model/<name> \\
        --rows dataset/raw/prod/sft/prod-64k/valid.jsonl --n 6
"""

import argparse, gc, json, sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "train"))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
import sft_img                                     # imports unsloth before transformers/peft

import torch
from peft import PeftModel
from transformers import AutoModelForImageTextToText, AutoProcessor

# Setting =================================================
MAX_LEN = 65536
CHUNK   = 2048                     # lm_head rows per step: full-vocab logits of a 64k row do not fit at once

# Functions ===============================================
@torch.no_grad()
def loss(model, batches: list[dict]) -> tuple[float, int]:
    """Mean cross-entropy over label tokens and the label-token count."""
    tot, n = 0.0, 0
    for b in batches:
        b = {k: v.cuda() for k, v in b.items()}
        labels = b.pop("labels")
        hidden = model.model(**b).last_hidden_state
        tgt = labels[:, 1:]
        keep = tgt != -100
        h, t = hidden[:, :-1][keep], tgt[keep]
        for s in range(0, len(t), CHUNK):
            tot += torch.nn.functional.cross_entropy(model.lm_head(h[s:s + CHUNK]).float(), t[s:s + CHUNK],
                                                     reduction="sum").item()
        n += len(t)
    return tot / n, n


def load(path: Path):
    return AutoModelForImageTextToText.from_pretrained(path, dtype=torch.bfloat16, device_map="cuda").eval()


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--adapter", type=Path, required=True)
    ap.add_argument("--merged", type=Path, required=True)
    ap.add_argument("--rows", type=Path, required=True, help="SFT jsonl in sft_img's format")
    ap.add_argument("--n", type=int, default=6, help="shortest N rows")
    a = ap.parse_args()

    rows = [json.loads(l) for l in sorted(a.rows.read_text().splitlines(), key=len)[:a.n]]
    proc = AutoProcessor.from_pretrained(a.merged)
    print("generation prompt:", repr(sft_img.generation_prompt(proc.tokenizer)))
    batches = [b for b in map(sft_img.Collator(proc, MAX_LEN).encode, rows) if b]
    print(f"{len(batches)} rows, tokens {[b['input_ids'].shape[1] for b in batches]}")

    res = {}
    m = load(a.base)
    res["base"] = loss(m, batches)
    m = PeftModel.from_pretrained(m, a.adapter).eval()
    res["base + adapter (unmerged)"] = loss(m.get_base_model(), batches)     # LoRA layers are injected in place
    del m; gc.collect(); torch.cuda.ipc_collect()
    res["merged"] = loss(load(a.merged), batches)
    for k, (l, n) in res.items():
        print(f"{k:28s} loss {l:.4f}  ({n} label tokens)")
