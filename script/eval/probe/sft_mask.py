"""Build the real SFT trainer on a few dataset rows and print which tokens carry loss (no training)."""

import argparse, json, sys, tempfile
from pathlib import Path

from unsloth import UnslothTrainer     # must precede transformers/datasets to enable optimizations
from datasets import load_dataset

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
import train.sft as sft

# Setting =================================================
ROOT  = Path(__file__).resolve().parent.parent.parent.parent
WIDTH = 160                             # chars shown from the start of each run (and 100 from its end)

# Functions ===============================================
def print_mask(trainer: UnslothTrainer, *_, **__) -> None:
    """Stands in for `UnslothTrainer.train`: prints the first batch as runs of masked / trained tokens
    (packed rows are labelled by `tokenize_with_assistant_mask`, unpacked by `train_on_responses_only`), then exits."""
    tok    = getattr(trainer, "processing_class", None) or trainer.tokenizer
    batch  = next(iter(trainer.get_train_dataloader()))
    ids, labels = batch["input_ids"][0].tolist(), batch["labels"][0].tolist()
    print("collator", type(trainer.data_collator).__name__, "| shape", tuple(batch["input_ids"].shape))
    runs, cur, buf = [], None, []
    for t, l in zip(ids, labels):
        if (l != -100) != cur and buf:
            runs.append((cur, buf))
            buf = []
        cur = l != -100
        buf.append(t)
    runs.append((cur, buf))
    for trained, toks in runs:
        s = tok.decode(toks).replace("\n", "⏎")
        tail = f" … {s[-100:]}" if len(s) > WIDTH + 100 else ""
        print(f"[{'TRAIN' if trained else 'mask '}] {s[:WIDTH]}{tail}")
    raise SystemExit(0)

# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--ds",      required=True, help="dataset dir under dataset/sft, e.g. tool_fim/repo-all-pi")
    cli.add_argument("--n",       type=int, default=2, help="rows to load")
    cli.add_argument("--packed",  action="store_true")
    cli.add_argument("--base",    default=sft.default_config()["base_model"])
    cli.add_argument("--max-len", type=int, default=8192)
    args = cli.parse_args()

    with open(ROOT / "dataset/sft" / args.ds / "train.jsonl") as f:
        rows = [json.loads(l) for l, _ in zip(f, range(args.n))]
    for r in rows:                      # same columns the mixer keeps
        r.setdefault("tools", None)
        r.pop("meta", None)
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "rows.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
        ds = load_dataset("json", data_files=str(Path(tmp) / "rows.jsonl"), split="train")
        UnslothTrainer.train = print_mask
        sft.run_sft({"base_model": args.base, "max_seq_length": args.max_len, "packing": args.packed,
                     "out_dir": tmp, "report_to": [], "batch_size": 1}, ds)
