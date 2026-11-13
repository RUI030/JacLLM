"""Training mix for a fresh adapter on v1.35: prod-64k, the UI harness replays and the three synthetic fix sets,
with the loss kept on a subset of JacHammer's tools and long reasoning removed.

Rows keep JacHammer's own system prompt and all 27 tool schemas, so a row still looks like what the harness sends.
Only two things change, both on assistant messages:
  - a trained reply that calls a tool outside SUBSET becomes context (weight 0);
  - reasoning_content longer than THINK_CAP characters is removed (trained replies and history alike), so the
    model sees a short thought or none before a call.
Composition, counts and the reason for each choice: output/sft/mix_1112_subset/README.md.

    python script/dataset/sft/mix_subset.py [out dir]            # mix_1112_subset
    python script/dataset/sft/mix_subset.py <out dir> --mini     # the same rows plus the mini apps (mix_1113_mini)"""

import json, sys
from collections import Counter
from pathlib import Path

# Setting =================================================
ROOT       = Path(__file__).resolve().parents[3]
PROD_DIR   = ROOT / "dataset/raw/prod/sft/prod-64k"                              # train.jsonl, valid.jsonl
UI_FILE    = ROOT / "output/sft/jac_ui_build/ui_apps_harness_v1/train.jsonl"     # 20 apps x (main, planner)
SYNTH_FILE = ROOT / "output/sft/mix_1110/train.jsonl"                            # the synthetic rows 1110 was trained on
MINI_FILE  = ROOT / "output/sft/jac_ui_build/mini_apps_harness_v1/train.jsonl"   # one-screen wiring apps x (main, planner)
SYNTH      = ("synthetic-router", "synthetic-loop", "synthetic-brace")
OUT_DIR    = ROOT / "output/sft/mix_1112_subset"

# The tools a build needs: look, load a guide, plan, write, check. A final reply is plain text (no tool call).
SUBSET = {"list_files", "read_file", "grep_search", "load_jac_skill", "plan_build", "write_code", "edit_code",
          "delete_code", "run_command", "preview_status", "browser_validate"}
THINK_CAP = 400                                   # characters; the UI replays' longest thought is 284
REPEAT    = {"prod": 2, "ui": 3, "synthetic": 1, "mini": 3}   # copies of each train row (sft_img.py runs one epoch)
HOLDOUT   = ("pantry", "sprintboard",             # UI apps kept out of train, scored in valid.jsonl
             "scoreboard_walker", "contacts_form")   # and two mini apps, when --mini is given
# UI main rows left out for length. sft_img.py crashes on a row it has to skip (unsloth_zoo's batch counter wants
# "labels"), so no row may exceed max_seq_length 65,536. The first three are over it (docs/JACHAMMER_UI_APPS.md:
# 65.8k, 66.6k, 69.7k). inkwell is unconfirmed: it has more characters than cartwell, so it is left out too.
TOO_LONG  = ("cartwell", "tablefor", "staylight", "inkwell")

# Functions ===============================================
def rows(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open()]


def project(row: dict, stat: Counter) -> dict | None:
    """Apply the tool subset and the reasoning cap to one row. None when no trained reply is left."""
    trained = 0
    for m in row["messages"]:
        if m["role"] != "assistant":
            continue
        if len(m.get("reasoning_content") or "") > THINK_CAP:
            del m["reasoning_content"]
            stat["reasoning removed"] += 1
        if not m.get("weight", 1):
            continue
        if any(c["function"]["name"] not in SUBSET for c in m.get("tool_calls") or []):
            m["weight"] = 0
            stat["replies masked (tool outside subset)"] += 1
        else:
            trained += 1
    stat["replies trained"] += trained
    return row if trained else None


def mix(out_dir: Path = OUT_DIR, mini: bool = False) -> None:
    ui = rows(UI_FILE) + (rows(MINI_FILE) if mini else [])
    groups = {
        "prod":      rows(PROD_DIR / "train.jsonl"),
        "ui":        [r for r in rows(UI_FILE) if r["meta"]["app"] not in HOLDOUT
                      and not (r["meta"]["agent"] == "main" and r["meta"]["app"] in TOO_LONG)],
        "synthetic": [r for r in rows(SYNTH_FILE) if r["meta"]["source"] in SYNTH],
    }
    if mini:
        groups["mini"] = [r for r in rows(MINI_FILE) if r["meta"]["app"] not in HOLDOUT]
    valid = rows(PROD_DIR / "valid.jsonl") + [r for r in ui if r["meta"]["app"] in HOLDOUT]
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "train.jsonl").open("w") as f:
        for name, group in groups.items():
            stat = Counter()
            kept = [r for r in (project(r, stat) for r in group) if r]
            for _ in range(REPEAT[name]):
                for r in kept:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"{name}: {len(kept)} of {len(group)} rows x {REPEAT[name]}  {dict(stat)}")
    stat = Counter()
    kept = [r for r in (project(r, stat) for r in valid) if r]
    with (out_dir / "valid.jsonl").open("w") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"valid: {len(kept)} of {len(valid)} rows  {dict(stat)}")


# Run =====================================================
if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--mini"]
    mix(Path(args[0]) if args else OUT_DIR, mini="--mini" in sys.argv)
