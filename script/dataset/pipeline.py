"""Shared record-writing pipeline for CPT/SFT/RL dataset producers.

Every dataset script builds a list of records (each a dict ready to write),
then splits + writes them. This module owns the split+write half so each
script only has to know how to turn one raw sample into one record (or task).
"""

import hashlib, json, random, shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from utils.io import json2parquet


def load_prompts(path, *keys: str) -> dict:
    """Load prompt_template.json; raise if any requested key is missing/empty."""
    tpl = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in keys if not tpl.get(k)]
    if missing:
        raise ValueError(f"Missing {missing} in prompt template: {path}")
    return {k: tpl[k] for k in keys}


FENCE_RATIO = 0.15      # share of records answered as a ```jac block; the rest reply with bare code


def chat_style(fp: str, prompts: dict, ratio: float = FENCE_RATIO):
    """(system prompt, wrap) of one record, decided by `fp` so a sample always gets the same style.

    A fenced record is a chat interface: its system prompt says so and the answer is a ```jac block.
    Every other record has a plain system prompt (None when `prompts["system"]` is empty), no fence is
    asked for anywhere, and the answer is the bare code. `prompts` needs "system" and "system_chat".
    """
    h      = int(hashlib.md5(str(fp).split("#part")[0].encode()).hexdigest(), 16)      # parts of one file share a style
    fenced = h % 10_000 < ratio * 10_000
    pool   = prompts["system_chat" if fenced else "system"]
    system = pool[(h // 10_000) % len(pool)] if pool else None
    return system, (lambda code: f"```jac\n{code}\n```") if fenced else (lambda code: code)


def split_and_write(records: list[dict], out_dir, valid_size: float,
                    format: str = "jsonl") -> dict[str, int]:
    """Split an already-shuffled list of records into train/valid and write.

    `valid_size=0.0` writes only train.jsonl (CPT mode). Otherwise writes both,
    with the first `int(N * valid_size)` rows going to valid.jsonl. When
    `format="parquet"`, JSONL is converted to Parquet in the same directory.

    Returns `{split_name: row_count}`.
    """
    out_dir = Path(out_dir)
    n_valid = int(len(records) * valid_size)
    splits  = {"train": records[n_valid:]}
    if n_valid > 0:
        splits["valid"] = records[:n_valid]

    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for split, rows in splits.items():
        with (out_dir / f"{split}.jsonl").open("w", encoding="utf-8") as f:
            for row in rows:
                json.dump(row, f, ensure_ascii=False)
                f.write("\n")
        counts[split] = len(rows)

    if format == "parquet":
        json2parquet(out_dir, out_dir)
    return counts


def report(counts: dict[str, int], out_dir) -> None:
    """Consistent completion message across all dataset scripts."""
    train = counts.get("train", 0)
    valid = counts.get("valid", 0)
    print(f"Created {train} train and {valid} validation samples in {out_dir}")
    if valid == 0:
        print("  (VALID_SIZE=0, valid.jsonl skipped — CPT mode)")


def write_rl_set(tasks: list[dict], out_dir, shared_meta: dict, split_ratio: tuple[float, float, float],
                 seed: int, rejected: list[dict] | None = None, extra_stats: dict | None = None) -> dict[str, int]:
    """Write an RL task set in the layout `rl/task.py` loads.

    Each task is `{"id", "meta": {entrypoints, difficulty, ...}, "visible": {name: text},
    "hidden": {name: text}}`: `visible` goes to tasks/<id>/ (model-visible), `hidden` to
    tests/<id>/ (grader-only). Tasks are shuffled with `seed` and cut into train/dev/test by
    `split_ratio`. Writes meta.json, splits/*.txt, statistic.json and rejected.jsonl; stale
    tasks/, tests/ and splits/ under `out_dir` are removed first. Returns {split: task count}.
    """
    out_dir = Path(out_dir)
    for sub in ("tasks", "tests", "splits"):
        shutil.rmtree(out_dir / sub, ignore_errors=True)
    for t in tasks:
        for kind, files in (("tasks", t["visible"]), ("tests", t["hidden"])):
            d = out_dir / kind / t["id"]
            d.mkdir(parents=True)
            for name, text in files.items():
                (d / name).write_text(text, encoding="utf-8")

    ids = [t["id"] for t in tasks]
    random.Random(seed).shuffle(ids)
    n_train, n_dev = int(len(ids) * split_ratio[0]), int(len(ids) * split_ratio[1])
    splits = {"train": ids[:n_train], "dev": ids[n_train:n_train + n_dev], "test": ids[n_train + n_dev:]}
    (out_dir / "splits").mkdir()
    for name, part in splits.items():
        (out_dir / "splits" / f"{name}.txt").write_text("".join(f"{i}\n" for i in sorted(part)))

    meta = {**shared_meta, "tasks": {t["id"]: t["meta"] for t in sorted(tasks, key=lambda t: t["id"])}}
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    stats = {
        "tasks":        len(tasks),
        "splits":       {k: len(v) for k, v in splits.items()},
        "difficulty":   dict(Counter(t["meta"].get("difficulty") for t in tasks).most_common()),
        "hidden_tests": sum(t.get("n_hidden", 0) for t in tasks),
        **(extra_stats or {}),
    }
    if rejected is not None:
        stats["rejected"] = dict(Counter(r["reason"] for r in rejected).most_common())
        with (out_dir / "rejected.jsonl").open("w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rejected)
    (out_dir / "statistic.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")
    return {k: len(v) for k, v in splits.items()}
