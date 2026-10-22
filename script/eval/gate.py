import argparse, json, sys
from collections import defaultdict
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from utils.jac_block import extract_code, classify_output
from utils.jac_cli import check as jac_check, run as jac_run

# Setting =================================================
PRED_FILE     = ""     # e.g. output/eval/code_completion/<ds>/<tag>/predictions.jsonl
CHECK_TIMEOUT = 30     # seconds per file
RUN_TIMEOUT   = 30
CHECKS        = ["check"]          # static only; opt into executing model code with --checks check,run

# CLI overrides ============================================
cli = argparse.ArgumentParser(add_help=False)
cli.add_argument("--pred",   dest="pred",   help="predictions.jsonl path")
cli.add_argument("--checks", dest="checks", help="comma list, e.g. check,run (ladder short-circuits)")
args, _ = cli.parse_known_args()
if args.pred:   PRED_FILE = args.pred
if args.checks: CHECKS    = [c.strip() for c in args.checks.split(",") if c.strip()]


# Functions ===============================================
GATES = {
    "check": (jac_check, CHECK_TIMEOUT),
    "run":   (jac_run,   RUN_TIMEOUT),
}


def evaluate(pred_file=PRED_FILE, checks=CHECKS):
    """Score every prediction through the check→run ladder. Group by meta.class."""
    if not pred_file:
        raise ValueError("PRED_FILE must be set (--pred or top-of-file)")
    pred_path = Path(pred_file)
    if not pred_path.is_file():
        raise FileNotFoundError(f"Predictions not found: {pred_path}")

    # aggregate counters — track has_block / bare / wrong_fence / no_output separately
    output_kinds = ["has_block", "bare", "wrong_fence", "no_output"]
    counter_keys = ["n"] + output_kinds + [f"{c}_pass" for c in checks]
    def _zero(): return {k: 0 for k in counter_keys}
    overall = _zero()
    by_class: dict[str, dict[str, int]] = defaultdict(_zero)

    samples: list[dict] = []   # per-record diagnostic entries

    with pred_path.open("r", encoding="utf-8") as src:
        for line in src:
            rec = json.loads(line)
            cls = rec.get("meta", {}).get("class", "unknown")
            pred_txt = rec.get("prediction", "")
            overall["n"] += 1
            by_class[cls]["n"] += 1

            kind = classify_output(pred_txt)
            entry = {
                "id":         rec.get("id"),
                "class":      cls,
                "prediction": pred_txt,
                "kind":       kind,   # has_block / bare / wrong_fence / no_output
            }
            for c in checks:
                entry[f"{c}_ok"]  = None
                entry[f"{c}_err"] = None

            overall[kind] += 1
            by_class[cls][kind] += 1

            if kind not in ("has_block", "bare"):
                samples.append(entry)
                continue

            block = extract_code(pred_txt)
            # kind in (has_block, bare) guarantees block is not None

            # ladder: run each gate only if prior passed
            prev_ok = True
            for c in checks:
                if not prev_ok:
                    break
                gate_fn, timeout = GATES[c]
                ok, err = gate_fn(block, timeout=timeout)
                entry[f"{c}_ok"]  = ok
                entry[f"{c}_err"] = err if not ok else None
                if ok:
                    overall[f"{c}_pass"] += 1
                    by_class[cls][f"{c}_pass"] += 1
                prev_ok = ok

            samples.append(entry)

    report = {
        "pred_file": str(pred_path),
        "checks":    checks,
        "overall":   overall,
        "by_class":  dict(by_class),
        "samples":   samples,
    }
    out_path = pred_path.parent / "report.json"
    with out_path.open("w", encoding="utf-8") as dst:
        json.dump(report, dst, indent=2, ensure_ascii=False)

    n = overall["n"] or 1
    header = (f"n={overall['n']}  has_block={overall['has_block']}/{n}  bare={overall['bare']}  "
              f"wrong_fence={overall['wrong_fence']}  no_output={overall['no_output']}")
    for c in checks:
        header += f"  {c}_pass={overall[f'{c}_pass']}/{n}"
    print(header)
    for cls, s in by_class.items():
        cn = s["n"] or 1
        parts = [f"n={s['n']:4d}", f"block={s['has_block']:4d}", f"bare={s['bare']}",
                 f"wf={s['wrong_fence']}", f"no={s['no_output']}"]
        for c in checks:
            parts.append(f"{c}={s[f'{c}_pass']:4d} ({s[f'{c}_pass']*100/cn:.1f}%)")
        print(f"  {cls:15s} " + "  ".join(parts))
    print(f"Report: {out_path}")


# Run =====================================================
if __name__ == "__main__":
    evaluate()
