"""Episode statistics: how often the student gets stuck, whether it gets itself out, and what the teacher fixes.

An incident is one place going wrong: from the first failed result with a given (kind, key) until the first passing
result on the same key. It is resolved by whoever made that passing call (student or teacher), or not at all.

    python analyze.py --group heldout-1105 --group heldout-1106 [--out <file.json>]
"""

import argparse, collections, json, re, statistics
from pathlib import Path

from spike_utils import OUT_ROOT

# Setting =================================================
EPISODES = OUT_ROOT / "episodes"
ECODE    = re.compile(r"\b(E\d{4})\b")


TARGETED = {"jac_errors", "edit_mismatch", "not_found", "command_failed"}   # fixed only by a pass on the same file/command;
                                               # other kinds (repeat, refused, after_done) end at any passing call


# Functions ===============================================
def target_of(r: dict) -> str:
    """The file (as /workspace/<rel>) or command a tool call works on."""
    args = json.loads(r["call"]["function"]["arguments"])
    if "file_path" in args:
        p = args["file_path"]
        return p if p.startswith("/") else "/workspace/" + p.removeprefix("./")
    return args.get("command", r["call"]["function"]["name"]).replace(" 2>&1", "").strip()


def episode_stats(ep: Path) -> dict:
    summary = json.loads((ep / "summary.json").read_text())
    journal = [json.loads(l) for l in (ep / "journal.jsonl").read_text().splitlines()]
    turns = [r for r in journal if r["actor"] == "student" and r["kind"] == "turn" and r["phase"] == "build"]
    results = [r for r in journal if r["kind"] == "tool_result"]
    student = [r for r in results if not r["call"]["id"].startswith("teacher_")]
    open_, incidents = {}, []
    for r in results:
        who, target = "teacher" if r["call"]["id"].startswith("teacher_") else "student", target_of(r)
        if r["failed"]:
            k = target if r["fail_kind"] in TARGETED else r["fail_kind"]
            inc = open_.setdefault(k, {"kind": r["fail_kind"], "key": k, "attempts": 0, "by": None})
            inc["attempts"] += who == "student"
            continue
        for k in [k for k in open_ if k == target or open_[k]["kind"] not in TARGETED]:
            inc = open_.pop(k)
            inc["by"] = who
            incidents.append(inc)
    incidents += open_.values()
    first_iv = next((i for i, r in enumerate(journal) if r["kind"] == "teacher_called"), None)
    student_before = sum(1 for r in journal[:first_iv] if r in turns) if first_iv is not None else len(turns)
    codes = collections.Counter(c for r in student if r["failed"] for c in set(ECODE.findall(r.get("text", ""))))
    return {
        "episode": ep.name, "end": summary["end"], "minutes": round(summary["seconds"] / 60, 1),
        "interventions": len(summary["interventions"]), "student_turns": len(turns),
        "plan_rejections": sum(r["kind"] == "plan_rejected" for r in journal),
        "student_calls": len(student), "student_failed": sum(r["failed"] for r in student),
        "fail_kinds": dict(collections.Counter(r["fail_kind"] for r in student if r["failed"])),
        "turns_before_first_teacher": student_before,
        "incidents": len(incidents),
        "resolved_by": dict(collections.Counter(i["by"] or "none" for i in incidents)),
        "student_fix_attempts": dict(collections.Counter(str(i["attempts"]) for i in incidents if i["by"] == "student")),
        "teacher_where": dict(collections.Counter(iv["where"][0] for iv in summary["interventions"])),
        "error_codes": dict(codes),
        "native_lowering_notes": sum("E5092" in r.get("text", "") for r in results),
        "repetition_fixes": sum(len(r.get("repetition_fixes") or []) for r in turns),
    }


def group_stats(rows: list[dict]) -> dict:
    add = lambda k: sum((collections.Counter(r[k]) for r in rows), collections.Counter())
    calls, failed = sum(r["student_calls"] for r in rows), sum(r["student_failed"] for r in rows)
    resolved = add("resolved_by")
    return {
        "episodes": len(rows), "success": sum(r["end"] == "success" for r in rows),
        "ends": dict(collections.Counter(r["end"] for r in rows)),
        "interventions_mean": round(statistics.mean(r["interventions"] for r in rows), 2),
        "interventions_mean_success": round(statistics.mean([r["interventions"] for r in rows if r["end"] == "success"]
                                                            or [0]), 2),
        "student_turns_mean": round(statistics.mean(r["student_turns"] for r in rows), 1),
        "student_call_fail_rate": round(failed / max(1, calls), 3),
        "turns_before_first_teacher_median": statistics.median(r["turns_before_first_teacher"] for r in rows),
        "incidents": sum(resolved.values()), "resolved_by": dict(resolved),
        "self_recovery_rate": round(resolved["student"] / max(1, sum(resolved.values())), 3),
        "student_fix_attempts": dict(sorted(add("student_fix_attempts").items(), key=lambda kv: int(kv[0]))),
        "fail_kinds": dict(add("fail_kinds").most_common()), "teacher_where": dict(add("teacher_where").most_common()),
        "error_codes": dict(add("error_codes").most_common(15)),
        "plan_rejections": sum(r["plan_rejections"] for r in rows),
        "repetition_fixes": sum(r["repetition_fixes"] for r in rows),
    }


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--group", action="append", required=True, help="episode-name prefix, e.g. heldout-1106")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    report = {}
    for g in a.group:
        rows = [episode_stats(ep) for ep in sorted(EPISODES.glob(g + "*")) if (ep / "summary.json").exists()]
        report[g] = {"summary": group_stats(rows), "episodes": rows}
        print(f"== {g}\n" + json.dumps(report[g]["summary"], indent=1))
    if a.out:
        a.out.write_text(json.dumps(report, indent=1) + "\n")
