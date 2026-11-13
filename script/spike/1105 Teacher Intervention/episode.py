"""Run one app task with the served student; on three failures at the same place the teacher writes the next turn.

Phase plan: the student writes the implementation plan (training plan prompt, no tools); the harness rejects a
plan that is cut off, has no Mermaid graph, no .jac modules, no typed signatures or no verification section.
Phase build: the student builds the app in a clean workspace with JacCoder's tools until it gives a final answer
that the harness accepts (`Episode.accept`), or a budget runs out.

Every student turn is journaled. A failed turn stays in the context, so the student retries seeing its failure.
After FAILS_TO_TEACH consecutive failures with the same (kind, key) the teacher gets the trajectory and writes the
next turn, which is executed like a student turn; the episode then continues with the student.

    python episode.py --task records_crud [--out <dir>] [--max-turns 80] [--no-thinking]
"""

import argparse, hashlib, json, re, time
from pathlib import Path

import frontend_check, generate, teacher
from workspace import jac_cli
from spike_utils import OUT_ROOT, SUPPORT, WS, JAC_VERSION, Journal, load_task, prompt, tools
from workspace import SKIP_DIRS, Outcome, Workspace

# Setting =================================================
FAILS_TO_TEACH    = 3
WINDOW            = 12             # turns in which FAILS_TO_TEACH failures at one place count as stuck
MAX_INTERVENTIONS = 8
COMPACT_AT        = 48000          # prompt tokens: start a new segment from a resume handoff (revdev resume format)
MAX_SEGMENTS      = 5
RESUME_TEXT       = ("Continue from this checkpoint. Read docs/plan.md once. Use the handoff file inventory and observed "
                     "command results to decide which source needs inspection; read only files needed for the next edit "
                     "or whose state is uncertain. Reuse reads within this segment. File hashes do not prove behavior. "
                     "Make one allowed command per run_command call, complete remaining functionality, and rerun "
                     "acceptance checks.")             # verbatim from the revdev resume rows the student was trained on
STUB              = re.compile(r"NotImplementedError|#\s*TODO|\bpass;")
PLANNED           = re.compile(r'(?m)^\s*(?:[-*]|\d+\.)\s+`?(\w[\w./-]*\.jac)\b|\["(\w[\w./-]*\.jac)')   # a module the plan
                                                 # lists (list item that starts with the path, or a Mermaid node label)
REQUIRED          = {   # category -> (pattern every app of that kind needs, what is missing); task constraints
    "llm":   [(r"\bby llm\b", "no function uses `by llm`, which the task requires")],
    "graph": [(r"(?m)^\s*node\s+\w+", "no `node` archetype, which the task requires"),
              (r"(?m)^\s*edge\s+\w+", "no `edge` archetype, which the task requires")],
}
FRONTEND_NOT_DONE = "The task is not finished: the web app's frontend does not load yet."
FRONTEND_NOTE     = ("The student's checks pass, but the harness's frontend check (fe-check; its output is not shown "
                     "to the student) reports:\n")
PLAN_MAX_TOKENS   = 6144
TURN_MAX_TOKENS   = 8192


# Functions ===============================================
def plan_problems(text: str, capped: bool, web: bool = True) -> list[str]:
    """Why a plan is not acceptable (empty list: accepted). Same checks as the user spec, plus .jac frontend.
    A non-web task (a library with a CLI entry) needs no frontend/backend module lists."""
    problems = []
    if capped:
        problems.append("the plan was cut off at the token limit (it repeats or is far too long)")
    if "```mermaid" not in text:
        problems.append("it has no ```mermaid module graph")
    if len(set(re.findall(r"[\w/]+\.jac", text))) < 2:
        problems.append("it names fewer than two .jac modules")
    if not re.search(r"def(?::pub)?\s+\w+\([^)]*\)\s*->", text):
        problems.append("it gives no typed public signatures written as `def name(arg: type) -> type`")
    if not re.search(r"(?im)^#+.*(verif|test)", text):
        problems.append("it has no verification section")
    if re.search(r"\.(js|jsx|ts|tsx|html)\b", text):
        problems.append("it plans JavaScript/HTML files; the frontend must be .jac client components")
    if re.search(r"\.(py|j2)\b|\b(?:Flask|Jinja2?|Django|FastAPI)\b", text, re.I):
        problems.append("it plans a Python web framework or template; build the app with Jac modules")
    for section in ("frontend", "backend") if web else ():
        match = re.search(rf"(?ims)^#+[^\n]*{section}[^\n]*\n(.*?)(?=^#+|\Z)", text)
        if not match or not re.search(r"(?m)^\s*(?:[-*]|\d+\.)\s.*\.jac\b", match.group(1)):
            problems.append(f"it has no {section} .jac module in the {section} module list")
    return problems


def planned(plan: str) -> list[str]:
    """The .jac modules a plan commits to, in order."""
    return list(dict.fromkeys(a or b for a, b in PLANNED.findall(plan)))


def unmet(plan: str, ws: Workspace, category: str | None) -> list[str]:
    """What the finished workspace still lacks besides check and test: planned modules not written, and what the
    task's category requires (REQUIRED)."""
    missing = [f for f in planned(plan) if not (ws.root / f).is_file()]
    text = "\n".join(p.read_text(errors="replace") for p in ws.jac_files())
    return ((["Planned files not written yet: " + ", ".join(missing)] if missing else [])
            + [why for pattern, why in REQUIRED.get(category, []) if not re.search(pattern, text)])


def frontend_problems(root: Path) -> list[str]:
    """A web app's frontend as frontend_check sees it (entry exports a client `def:pub app`, compiles, valid JSX
    elements, every component bundled), as acceptance report lines."""
    return [f"Frontend ({k}): {m}" for k, v in frontend_check.check(root)["problems"].items() for m in v[:3]]


class Streak:
    """Failures at the same place, (kind, key), within the last WINDOW turns. Successes in between do not reset it:
    a student alternating "run app (ok) / run test (fails)" is stuck too."""
    def __init__(self):
        self.turns, self.where, self.indexes = [], None, []

    def add(self, where: tuple[str, str] | None, index: int) -> bool:
        """Record one turn (where=None: it succeeded). True when the teacher should step in."""
        self.turns = (self.turns + [(index, where)])[-WINDOW:]
        hits = [i for i, w in self.turns if where is not None and w == where]
        if len(hits) < FAILS_TO_TEACH:
            return False
        self.where, self.indexes = where, hits[-FAILS_TO_TEACH:]
        return True

    def reset(self) -> None:
        self.turns, self.where, self.indexes = [], None, []


def tree_hash(ws: Workspace) -> str:
    h = hashlib.sha256()
    for p in sorted(ws.root.rglob("*")):
        if p.is_file() and not SKIP_DIRS & set(p.relative_to(ws.root).parts[:-1]):
            h.update(str(p.relative_to(ws.root)).encode() + p.read_bytes())
    return h.hexdigest()


class Episode:
    def __init__(self, task: dict, out: Path, thinking: bool, max_turns: int, teacher: bool = True):
        self.task, self.out, self.thinking, self.max_turns = task, out, thinking, max_turns
        self.teacher = teacher                     # False: the student alone (eval, pass@k); being stuck is not an end
        self.web = "support_files" not in task                   # non-web tasks bring their own support files
        self.ws = Workspace(out / "workspace")
        self.journal = Journal(out / "journal.jsonl")
        self.tools = tools()
        self.interventions, self.done, self.seen_calls = [], False, {}
        self.segment, self.observed = 0, []

    def accept(self, plan: str) -> tuple[bool, str, str]:
        """Workspace.acceptance plus what check and test cannot see: every .jac file the plan names exists, and the
        app uses what its category requires (REQUIRED). Before 2026-11-07 only check and test counted, so apps that
        skipped their planned frontend files or never called `by llm` were accepted; before 2026-11-07 noon a web app
        was accepted without a mountable frontend (frontend_problems).
        Returns (ok, report for the student, report for the teacher only). frontend_check is our tool, not JacCoder's,
        so its findings go to the teacher only (since 2026-11-07 evening)."""
        ok, report = self.ws.acceptance()
        problems = ([report] if report else []) + unmet(plan, self.ws, self.task.get("category"))
        if problems:
            return False, "\n".join(problems), ""
        hidden = frontend_problems(self.ws.root) if self.web else []   # last: it builds the frontend
        return not hidden, "", "\n".join(hidden)

    def file(self, phase: str) -> str:
        return f"messages_{phase}.json" if phase == "plan" else f"messages_build_s{self.segment}.json"

    def save(self, phase: str, messages: list[dict]) -> None:
        (self.out / self.file(phase)).write_text(json.dumps(messages, ensure_ascii=False, indent=1) + "\n")

    def ask_student(self, messages: list[dict], phase: str, max_tokens: int) -> tuple[dict | None, bool, int]:
        r = generate.turn(messages, self.tools if phase == "build" else None, max_tokens, self.thinking,
                          COMPACT_AT if phase == "build" else None)
        msg = r["message"]
        if msg is None:
            return None, False, r["prompt_tokens"]
        for i, c in enumerate(msg.get("tool_calls", [])):
            c["id"] = f"call_{time.time_ns()}_{i}"
        self.journal.write("student", "turn", phase=phase, segment=self.segment, message=msg, capped=r["capped"],
                           prompt_tokens=r["prompt_tokens"], repetition_fixes=r["fixes"])
        return msg, r["capped"], r["prompt_tokens"]

    def intervene(self, messages: list[dict], streak: Streak, phase: str, note: str = "") -> dict | None:
        n = len(self.interventions)
        if n >= MAX_INTERVENTIONS or not self.teacher:
            return None
        log = self.out / "teacher" / f"{n:02d}"
        self.journal.write("controller", "teacher_called", phase=phase, where=list(streak.where), failed=streak.indexes)
        try:
            t = teacher.ask(messages, streak.indexes, self.tools if phase == "build" else [], self.ws.root, log,
                            note="This is the planning step: the turn is the full Markdown plan, with no tool calls."
                            if phase == "plan" else note)
        except (RuntimeError, ValueError, json.JSONDecodeError, TimeoutError) as ex:
            self.journal.write("teacher", "error", error=str(ex))
            return None
        msg = {"role": "assistant", "content": t.get("content", "")}
        if t.get("tool_calls"):
            msg["tool_calls"] = [{"id": f"teacher_{n}_{i}", "type": "function",
                                  "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
                                 for i, c in enumerate(t["tool_calls"])]
        self.journal.write("teacher", "turn", phase=phase, message=msg, diagnosis=t.get("diagnosis"), raw=t.get("raw"))
        self.interventions.append({"phase": phase, "file": self.file(phase), "segment": self.segment,
                                   "index": len(messages), "failed": streak.indexes,
                                   "where": list(streak.where), "diagnosis": t.get("diagnosis"), "log": str(log)})
        return msg

    def run_plan(self) -> str:
        messages = [{"role": "system", "content": prompt("plan_system.md")}, {"role": "user", "content": self.task["request"]}]
        streak = Streak()
        for _ in range(FAILS_TO_TEACH * 3):
            msg, capped, _ = self.ask_student(messages, "plan", PLAN_MAX_TOKENS)
            messages.append(msg)
            problems = plan_problems(msg["content"], capped, self.web)
            if not problems:
                self.save("plan", messages)
                return msg["content"]
            self.journal.write("controller", "plan_rejected", problems=problems)
            if streak.add(("plan", "plan"), len(messages) - 1):
                t = self.intervene(messages, streak, "plan")
                if t is not None:
                    messages.append(t)
                    if not plan_problems(t["content"], False, self.web):
                        self.save("plan", messages)
                        return t["content"]
                    streak = Streak()
            messages.append({"role": "user", "content": "The plan is not accepted: " + "; ".join(problems)
                             + ". Write the complete plan again."})
        self.save("plan", messages)
        raise RuntimeError("no acceptable plan")

    def execute(self, msg: dict) -> tuple[list[dict], tuple[str, str] | None]:
        """Run one assistant turn's tool calls. Returns the tool messages and the first failure's (kind, key)."""
        results, where = [], None
        for c in msg.get("tool_calls", []):
            try:
                args = json.loads(c["function"]["arguments"]) if isinstance(c["function"]["arguments"], str) else c["function"]["arguments"]
            except json.JSONDecodeError as ex:
                args, o = None, Outcome(f"Error: arguments are not valid JSON: {ex}", True, "bad_call", c["function"]["name"])
            if args is not None:
                call = (c["function"]["name"], json.dumps(args, sort_keys=True))
                if self.done:
                    o = Outcome("The acceptance checks already pass. Reply with a short final summary of what was built "
                                "and verified; do not call more tools.", True, "after_done", "done")
                elif self.seen_calls.get(call) == tree_hash(self.ws):   # same call, nothing changed since it last ran
                    o = self.ws.dispatch(c["function"]["name"], args)
                    o = Outcome(o.text, True, "repeat", call[0] + " " + call[1][:80])
                else:
                    o = self.ws.dispatch(c["function"]["name"], args)
                self.seen_calls[call] = tree_hash(self.ws)
                if not o.failed and call[0] == "run_command" and "jac test" in args.get("command", ""):
                    self.done, report, hidden = self.accept(self.plan)
                    self.journal.write("controller", "acceptance", ok=self.done, report=report, teacher_only=hidden)
            results.append({"role": "tool", "tool_call_id": c["id"], "content": o.text})
            if args is not None and c["function"]["name"] == "run_command" and o.kind != "refused":
                self.observed.append({"command": args.get("command", ""), "executed": True, "result_excerpt": o.text[:400]})
            self.journal.write("harness", "tool_result", call=c, failed=o.failed, fail_kind=o.kind, key=o.key, text=o.text[:4000])
            if o.failed and where is None:
                where = (o.kind, o.key)
        return results, where

    def handoff(self, plan: str) -> dict:
        """Resume handoff as in the revdev resume rows: planned-file inventory and recent command results."""
        sha = lambda b: hashlib.sha256(b).hexdigest()
        files = []
        for path in dict.fromkeys(re.findall(r"[\w./-]+\.(?:jac|toml|css|md)\b", plan)):
            p = self.ws.root / path
            entry = {"path": path, "present": p.is_file()}
            if p.is_file():
                data = p.read_bytes()
                entry.update(sha256=sha(data), size=len(data), contains_stub=bool(STUB.search(data.decode(errors="replace"))))
            files.append(entry)
        tree = tree_hash(self.ws)
        return {"checkpoint_id": tree[:16], "workspace_tree_sha256": tree, "plan_sha256": sha(plan.encode()),
                "planned_files": files, "observed_commands": self.observed[-4:]}

    def segment_start(self, plan: str) -> list[dict]:
        task = {k: v for k, v in self.task.items() if k not in ("source", "category", "support_files")}
        user = {"task": task, "workspace": WS, "jac_version": JAC_VERSION,
                "support_files": self.task.get("support_files", SUPPORT)}   # non-web tasks bring their own jac.toml purpose
        if self.segment == 0:
            user["implementation_plan"] = plan
        else:
            user.update(resume=RESUME_TEXT, handoff=self.handoff(plan))
        return [{"role": "system", "content": prompt("student_system.md")}, {"role": "user", "content": json.dumps(user)}]

    def run_build(self, plan: str) -> str:
        self.plan = plan
        messages = self.segment_start(plan)
        streak = Streak()
        for turn in range(self.max_turns):
            msg, capped, ctx = self.ask_student(messages, "build", TURN_MAX_TOKENS)
            if msg is None:                        # prompt over COMPACT_AT: the next segment starts from the handoff
                self.save("build", messages)
                if self.segment + 1 >= MAX_SEGMENTS:
                    return "context_full"
                self.segment += 1
                self.journal.write("controller", "compaction", segment=self.segment, prompt_tokens=ctx)
                messages, streak, self.seen_calls = self.segment_start(plan), Streak(), {}
                continue
            outcome = self.step(messages, msg, capped, streak)
            if outcome:
                return outcome
            self.save("build", messages)
        self.save("build", messages)
        return "turn_budget"

    def step(self, messages: list[dict], msg: dict, capped: bool, streak: Streak, actor: str = "student") -> str:
        """Append one assistant turn and its results; may call the teacher. Returns an end state or ''."""
        if capped:
            # A partial tool call is invalid history: llama-server fails to parse it on the next request.
            msg = {"role": "assistant", "content": "[Incomplete reply omitted after the token limit.]"}
        messages.append(msg)
        index, hidden = len(messages) - 1, ""
        if capped:
            where = ("length", "turn")
            messages.append({"role": "user", "content": "Your last reply hit the token limit without finishing. "
                             "Think briefly and make one concrete tool call."})
        elif msg.get("tool_calls"):
            results, where = self.execute(msg)
            messages.extend(results)
        else:
            ok, report, hidden = self.accept(self.plan)
            self.journal.write("controller", "acceptance", ok=ok, report=report, teacher_only=hidden, final=True)
            if ok:
                self.save("build", messages)
                return "success"
            where = ("premature_finish", "final")
            messages.append({"role": "user", "content": "The task is not finished. The harness checks report:\n" + report
                             if report else FRONTEND_NOT_DONE})
        if actor == "teacher":
            if where:
                self.journal.write("controller", "teacher_turn_failed", where=list(where))
            return ""
        note = ""
        if hidden:
            # only our frontend check failed: the student cannot see why, so the teacher steps in at once
            streak.where, streak.indexes = where, [index]
            note = FRONTEND_NOTE + hidden
        if note or streak.add(where, index):
            if not self.teacher:
                streak.reset()
                return ""
            t = self.intervene(messages, streak, "build", note)
            if t is None:
                return "teacher_unavailable" if len(self.interventions) < MAX_INTERVENTIONS else "intervention_budget"
            reset = Streak()
            end = self.step(messages, t, False, reset, actor="teacher")
            streak.reset()
            if end:
                return end
        return ""

    def run(self) -> dict:
        started = time.time()
        self.journal.write("controller", "start", task=self.task["task_id"], thinking=self.thinking)
        jac_cli.start_pg()                         # outside any per-call memory scope (CLAUDE.md, jac test gotcha)
        try:
            plan = self.run_plan()
            end = self.run_build(plan)
        except RuntimeError as ex:
            end = f"error: {ex}"
        finally:
            jac_cli.purge_pg()                     # jac test leaves one database per test block
        summary = {"task": self.task["task_id"], "end": end, "teacher": self.teacher,
                   "interventions": self.interventions, "seconds": round(time.time() - started),
                   "thinking": self.thinking}
        (self.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        self.journal.write("controller", "end", **summary)
        return summary


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, help="tasks/<slug>.json")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--max-turns", type=int, default=80)
    ap.add_argument("--no-thinking", action="store_true")
    ap.add_argument("--no-teacher", action="store_true", help="the student alone, until it passes or the turn budget ends")
    a = ap.parse_args()
    out = a.out or OUT_ROOT / "episodes" / f"{time.strftime('%m-%d_%H-%M')}-{a.task}"
    print(json.dumps(Episode(load_task(a.task), out, not a.no_thinking, a.max_turns, not a.no_teacher).run(), indent=2))
