"""Episodes -> SFT rows in sft_img.py's format.

Default: one row per trajectory (the plan, each build segment). Teacher turns are trained (weight 1) when they
worked; student turns are trained when they worked and the episode passed acceptance (`passed`); failed attempts, turns with a
repetition fix and turns in failed episodes stay context (weight 0).
--per-intervention: one row per teacher turn, the trajectory up to it as context and only that turn trained.

    python export.py [--episodes <dir>] [--out <file.jsonl>] [--per-intervention]
"""

import argparse, json, re
from pathlib import Path

from spike_utils import OUT_ROOT, load_task, tools
from episode import frontend_problems, plan_problems, unmet
from workspace import Workspace, scrub

# Setting =================================================
SOURCE    = "spike-teacher-intervention"
TASK_TYPE = "teacher_intervention"
CJK       = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
ADDRESSED = re.compile(r"\byou(?:r|rs|'re|'ve|'ll|'d)?\b", re.I)   # a teacher turn speaking to the student, not as it


# Functions ===============================================
def scrubbed(x, root: Path):
    """Every string in a message (content, reasoning, tool-call arguments) with host paths hidden; episodes before
    workspace.scrub covered all tool results showed them."""
    if isinstance(x, str):
        return scrub(x, root)
    if isinstance(x, list):
        return [scrubbed(v, root) for v in x]
    return {k: scrubbed(v, root) for k, v in x.items()} if isinstance(x, dict) else x


def teacher_ok(journal: list[dict], message: dict, where: list[str]) -> bool:
    """The proposal executed, and the failure it targeted did not immediately recur."""
    seq = next(r["seq"] for r in journal if r["actor"] == "teacher" and r["kind"] == "turn" and r["message"] == message)
    after = [r for r in journal if r["seq"] > seq]
    ids = {c["id"] for c in message.get("tool_calls", [])}
    if ids:
        res = [r for r in after if r["kind"] == "tool_result" and r["call"]["id"] in ids]
        if len(res) != len(ids) or any(r["failed"] for r in res):
            return False
        observed, student_turns = [], 0
        for r in after:
            if r["kind"] in ("teacher_called", "end"):
                break
            if r["actor"] == "student" and r["kind"] == "turn":
                student_turns += 1
                if student_turns > 5:
                    break
            observed.append(r)
        if any(r["kind"] == "tool_result" and r["failed"] and
               [r.get("fail_kind"), r.get("key")] == where for r in observed):
            return False
        if where[0] == "command_failed":
            return any(r["kind"] == "tool_result" and not r["failed"] and
                       r.get("key") == where[1] for r in observed)
        return True
    acc = next((r for r in after if r["kind"] == "acceptance"), None)
    return message.get("content", "") != "" and (acc is None or acc["ok"])


def in_voice(m: dict) -> dict | None:
    """A teacher turn as the student's own: one addressed to "you" (episodes before the first-person rule in
    teacher.py) keeps its tool calls with the text dropped; None when it has no tool calls, so nothing is left to train."""
    if not ADDRESSED.search(m.get("content", "")):
        return m
    return {**m, "content": ""} if m.get("tool_calls") else None


def rows_of(ep: Path) -> list[dict]:
    summary = json.loads((ep / "summary.json").read_text())
    journal = [json.loads(l) for l in (ep / "journal.jsonl").read_text().splitlines()]
    rows = []
    for k, iv in enumerate(summary["interventions"]):
        messages = json.loads((ep / iv.get("file", f"messages_{iv['phase']}.json")).read_text())
        t = messages[iv["index"]]
        if t.get("tool_calls") and not t["tool_calls"][0]["id"].startswith("teacher_"):
            continue                                   # index drifted; never train a student turn by mistake
        if iv["phase"] == "plan" and not t.get("content"):
            continue
        if iv["phase"] == "build" and not teacher_ok(journal, t, iv["where"]):
            continue
        if iv["phase"] == "build" and (t := in_voice(t)) is None:
            continue
        out = [{**m, "weight": 0} if m["role"] == "assistant" else m for m in messages[:iv["index"]]]
        out.append({**t, "weight": 1})
        ids = {c["id"] for c in t.get("tool_calls", [])}
        for m in messages[iv["index"] + 1:]:
            if m["role"] == "tool" and m["tool_call_id"] in ids:
                out.append(m)
            else:
                break
        rows.append({"messages": scrubbed(out, (ep / "workspace").resolve()), "tools": json.dumps(tools()) if iv["phase"] == "build" else None,
                     "meta": {"source": SOURCE, "format": "trajectory", "class": "fullstack", "task_type": TASK_TYPE,
                              "fp": f"{ep.name}#{k}", "phase": iv["phase"], "where": iv["where"],
                              "failed_attempts": iv["failed"], "diagnosis": iv["diagnosis"], "task": summary["task"]}})
        rows[-1]["meta"] = scrubbed(rows[-1]["meta"], (ep / "workspace").resolve())
    return rows


def student_ok(m: dict, failed: dict[str, bool], final: bool) -> bool:
    """A student turn worth training: complete, no repetition fix (weights are per message, the loop would be
    trained too), every tool call ran without failure, or the final answer of an episode that passed acceptance."""
    if m.get("repetition_fixes") or m.get("content", "").startswith("[Incomplete reply"):
        return False
    if CJK.search(m.get("content", "") + m.get("reasoning_content", "")):
        return False
    if m.get("tool_calls"):
        return all(c["id"] in failed and not failed[c["id"]] for c in m["tool_calls"])
    return final


def passed(ep: Path, summary: dict) -> bool:
    """The episode passed acceptance as it stands since 2026-11-07: earlier runs ended "success" on check and test
    alone, so the planned-modules and category checks (episode.unmet) and, for a web app, the frontend check
    (episode.frontend_problems) are applied to their final workspace here."""
    if summary["end"] != "success":
        return False
    plan = [m for m in json.loads((ep / "messages_plan.json").read_text()) if m["role"] == "assistant"][-1]["content"]
    task = load_task(summary["task"].removesuffix("_v1"))
    ws = Workspace(ep / "workspace")
    return not unmet(plan, ws, task.get("category")) and ("support_files" in task or not frontend_problems(ws.root))


def segment_rows(ep: Path) -> list[dict]:
    """One row per trajectory (plan, each build segment): teacher turns weight 1 when teacher_ok, student turns
    weight 1 when student_ok and the episode passed acceptance, everything else weight 0."""
    summary = json.loads((ep / "summary.json").read_text())
    journal = [json.loads(l) for l in (ep / "journal.jsonl").read_text().splitlines()]
    failed = {r["call"]["id"]: r["failed"] for r in journal if r["kind"] == "tool_result"}
    success = passed(ep, summary)
    teach = {(iv["file"], iv["index"]): iv for iv in summary["interventions"] if iv.get("file")}
    root, rows = (ep / "workspace").resolve(), []
    files = ["messages_plan.json"] + sorted(p.name for p in ep.glob("messages_build_s*.json"))
    for f in files:
        if not (ep / f).exists():
            continue
        messages = json.loads((ep / f).read_text())
        phase = "plan" if f == "messages_plan.json" else "build"
        last_a = max(i for i, m in enumerate(messages) if m["role"] == "assistant")
        out, n_teacher, n_student = [], 0, 0
        for i, m in enumerate(messages):
            if m["role"] != "assistant":
                out.append(m)
                continue
            if (f, i) in teach:
                iv = teach[(f, i)]
                w = int(bool(m.get("content")) if phase == "plan" else teacher_ok(journal, m, iv["where"]))
                if w and phase == "build":
                    m, w = (in_voice(m), 1) if in_voice(m) else (m, 0)
                n_teacher += w
            elif phase == "plan":                  # the plan the harness accepted ends the file
                w = int(i == last_a and success and not plan_problems(m.get("content", ""), False))
                n_student += w
            else:
                w = int(success and student_ok(m, failed, i == last_a and f == files[-1]))
                n_student += w
            out.append({**{k: v for k, v in m.items() if k != "repetition_fixes"}, "weight": w})
        if n_teacher + n_student == 0:
            continue
        rows.append({"messages": scrubbed(out, root), "tools": json.dumps(tools()) if phase == "build" else None,
                     "meta": scrubbed({"source": SOURCE, "format": "trajectory", "class": "fullstack",
                                       "task_type": TASK_TYPE, "fp": f"{ep.name}/{f}", "phase": phase,
                                       "end": summary["end"] if success or summary["end"] != "success" else "incomplete",
                                       "teacher_turns": n_teacher,
                                       "student_turns": n_student, "task": summary["task"]}, root)})
    return rows


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episodes", type=Path, default=OUT_ROOT / "episodes")
    ap.add_argument("--out", type=Path, default=OUT_ROOT / "sft/train.jsonl")
    ap.add_argument("--per-intervention", action="store_true",
                    help="one row per teacher turn, only that turn trained (the first export format)")
    a = ap.parse_args()
    fn = rows_of if a.per_intervention else segment_rows
    rows = [r for ep in sorted(a.episodes.iterdir()) if (ep / "summary.json").exists() for r in fn(ep)]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{len(rows)} rows -> {a.out}")
