"""Score finished episodes part by part, for comparing models (and as candidate partial rewards for RL).

Each episode's final workspace is re-checked with the acceptance rules one by one (a run that ran out of turns still
gets credit for what it got right), plus frontend_check per check and idiom_check counts. Then per group (a glob of
episode dirs, e.g. one model's runs) pass@1 and pass@k per task, with the unbiased estimator over n runs.

    python score.py --groups new='eval-new-*' old='eval-1105-*' [--root <episodes dir>] [--k 1 2 4] [--out <json>]
"""

import argparse, json, math, re, shutil, sys, tempfile
from collections import defaultdict
from pathlib import Path

from spike_utils import OUT_ROOT, load_task
from episode import planned, REQUIRED
from workspace import SKIP_DIRS, Workspace
import frontend_check, idiom_check

# Setting =================================================
PARTS = ["plan", "check", "tests", "planned", "category", "scratch", "frontend"]   # in acceptance order


# Functions ===============================================
def plan_of(ep: Path) -> str | None:
    p = ep / "messages_plan.json"
    if not p.is_file():
        return None
    msgs = json.loads(p.read_text())
    return next((m["content"] for m in reversed(msgs) if m["role"] == "assistant"), None)


def score(ep: Path) -> dict:
    summary = json.loads((ep / "summary.json").read_text())
    task = load_task(summary["task"].removesuffix("_v1"))
    web, plan = "support_files" not in task, plan_of(ep)
    r = {"episode": ep.name, "task": summary["task"].removesuffix("_v1"), "end": summary["end"],
         "teacher_turns": len(summary.get("interventions", [])), "seconds": summary.get("seconds")}
    parts = dict.fromkeys(PARTS, False)
    parts["plan"] = plan is not None and (ep / "messages_build_s0.json").is_file()
    with tempfile.TemporaryDirectory(prefix="score-") as d:      # jac writes caches; keep the episode as it was
        root = Path(d) / "workspace"
        shutil.copytree(ep / "workspace", root, ignore=shutil.ignore_patterns(*SKIP_DIRS))
        ws = Workspace(root)
        files = ws.jac_files()
        if parts["plan"] and files:
            parts["check"] = not any(ws.jac_errors(p) for p in files)
            targets = ws.test_targets()
            parts["tests"] = bool(targets) and all(ws.jac(["test", str(t.relative_to(root))], 300).ok for t in targets)
            parts["planned"] = all((root / f).is_file() for f in planned(plan))
            text = "\n".join(p.read_text(errors="replace") for p in files)
            parts["category"] = all(re.search(pat, text) for pat, _ in REQUIRED.get(task.get("category"), []))
            parts["scratch"] = not ws.scratch_files()
            fe = frontend_check.check(root) if web else {"problems": {}}
            parts["frontend"] = not fe["problems"]
            r["frontend_problems"] = sorted(fe["problems"])
            r["idiom"] = idiom_check.workspace_report(root)
    r["parts"], r["accepted"] = parts, all(parts.values())
    return r


def pass_at(n: int, c: int, k: int) -> float:
    """Unbiased pass@k from n runs with c passes (Chen et al. 2021)."""
    return 1.0 if n - c < k else 1 - math.comb(n - c, k) / math.comb(n, k)


def report(rows: list[dict], ks: list[int]) -> dict:
    by = defaultdict(list)
    for r in rows:
        by[r["task"]].append(r)
    tasks = {t: {"n": len(v), "passed": sum(r["accepted"] for r in v),
                 **{f"pass@{k}": round(pass_at(len(v), sum(r["accepted"] for r in v), k), 3) for k in ks if k <= len(v)},
                 "parts": {p: sum(r["parts"][p] for r in v) for p in PARTS}} for t, v in sorted(by.items())}
    have = lambda key: [t[key] for t in tasks.values() if key in t]          # tasks with at least k runs
    mean = lambda key: round(sum(have(key)) / len(have(key)), 3) if have(key) else None
    return {"runs": len(rows), "tasks": tasks, **{f"pass@{k}": mean(f"pass@{k}") for k in ks},
            "parts": {p: round(sum(r["parts"][p] for r in rows) / max(1, len(rows)), 3) for p in PARTS}}


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--groups", nargs="+", required=True, help="name=glob of episode dirs under --root")
    ap.add_argument("--root", type=Path, default=OUT_ROOT / "episodes")
    ap.add_argument("--k", nargs="+", type=int, default=[1, 2, 4])
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    out = {}
    for g in a.groups:
        name, pattern = g.split("=", 1)
        rows = [score(ep) for ep in sorted(a.root.glob(pattern)) if (ep / "summary.json").is_file()]
        out[name] = {"report": report(rows, a.k), "runs": rows}
        rep = out[name]["report"]
        print(f"== {name}: {rep['runs']} runs  " + "  ".join(f"pass@{k} {rep[f'pass@{k}']}" for k in a.k))
        print("   parts passed: " + "  ".join(f"{p} {v:.0%}" for p, v in rep["parts"].items()))
        for t, v in rep["tasks"].items():
            print(f"   {t:22s} {v['passed']}/{v['n']}  " + " ".join(f"{p}={n}" for p, n in v["parts"].items()))
    if a.out:
        a.out.write_text(json.dumps(out, indent=1) + "\n")
