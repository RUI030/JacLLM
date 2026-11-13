"""Generate teacher decisions with Claude CLI and execute real JacCoder tools."""

import argparse, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

import jsonschema

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli
from dataset.revdev.checkpoint import save, restore, resume_handoff
from dataset.revdev.plan_md import render as render_plan_md, validate_rendered

# Setting =================================================
SUPPORTED = {"read_file", "write_code", "edit_code", "run_command", "load_jac_skill"}
PROTOCOL = """
# Adapter execution protocol (takes precedence over unavailable interface features)
You are operating through a synchronous JacCoder adapter. Built-in Claude tools are disabled.
Only the schemas in the user payload are executable. Return a JSON object with:
kind: 'tool' or 'final'; name: tool name or ''; args: tool arguments or {};
summary: a brief observable progress statement. Never return invented results.
Select ONE tool per response; its actual result will be supplied on the next turn.
plan_build is unavailable in this adapter. The grounded implementation plan is supplied
as visible Markdown context. Write it to docs/plan.md using write_code before source files.
Keep its Mermaid graph of .jac modules, explicit frontend and backend module lists,
public interfaces, and dependency order. Configuration and CSS are supporting files;
their exact paths are supplied separately in support_files for scaffolding. Do not invent
supporting-file paths or put them in the module graph or frontend/backend module lists. Update the Markdown
when evidence changes the plan. The harness manages its own private JSON progress manifest;
do not write or read that manifest unless diagnosing a harness failure.
Use the pinned Jac version in the task, including its client syntax. load_jac_skill may
return guidance for a different version: check its stated version against jac_version
and prefer the target binary's jac check diagnostics. For Jac 0.36.1, read
version-matched guidance through `run_command` with `jac guide <topic>` instead
of `load_jac_skill`; the captured JacCoder skill may target 0.34.27. Jac 0.34.27
uses explicit cl blocks; Jac 0.36.1 infers placement and rejects cl/sv markers.
Do not access anything outside workspace except the supplied load_jac_skill tool.
run_command is for bounded local Jac commands. After changing jac.toml dependencies,
use `jac install` to synchronize them before rebuilding. Only install dependencies
declared in the workspace jac.toml; do not use other package managers, delete
outside the workspace, access credentials, or use background jobs.
Create test files in the workspace and run them before finishing. Keep the app small,
functional and deterministic. Never call a real model. Write `by llm` functions exactly
where the plan specifies them; in tests, import the defining module (`import pkg.mod as m;`)
and assign `m.llm = MockLLM(model_name="mockllm", config={"outputs": [...]})` from
`jaclang.byllm.lib` before calling them. Finish only after acceptance checks.
"""
DECISION_SCHEMA = {
    "type": "object", "properties": {
        "kind": {"enum": ["tool", "final"]}, "name": {"type": "string"},
        "args": {"type": "object"}, "summary": {"type": "string"},
    }, "required": ["kind", "name", "args", "summary"], "additionalProperties": False,
}

# Functions ===============================================
def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def jac_version(jac: Path) -> str:
    result = subprocess.run([str(jac.resolve()), "--version"], capture_output=True,
                            text=True, check=True, timeout=15)
    match = re.search(r"\bjac (\d+\.\d+\.\d+)\b", result.stdout)
    if not match:
        raise ValueError(f"Could not read Jac version from {jac}: {result.stdout!r}")
    return match.group(1)


def check_resources(path: Path) -> dict:
    import shutil
    mem = {line.split(":")[0]: int(line.split()[1]) * 1024
           for line in Path("/proc/meminfo").read_text().splitlines()}
    disk = shutil.disk_usage(path)
    state = {"time": time.time(), "ram_available": mem["MemAvailable"], "disk_free": disk.free}
    if mem["MemAvailable"] < 4 * 1024**3 or disk.free < 20 * 1024**3:
        raise RuntimeError(f"Resource floor reached: {state}")
    return state


def phase_instruction(workspace: Path, markdown: bool) -> str:
    if markdown:
        opening = ("Write docs/plan.md before source files. " if not (workspace / "docs/plan.md").is_file()
                   else "Follow docs/plan.md and revise it only when evidence changes the plan. ")
    else:
        opening = "Follow .jaccoder/build_plan.json and its dependency order. "
    return (opening + "During scaffold phase ALL function and ability bodies must be ONLY "
            "raise NotImplementedError(); UI entry functions may return minimal JSX placeholders. "
            "Create every planned Jac module and every support_files path before working service bodies.")


def support_files(plan: dict) -> list[dict]:
    """Expose exact non-Jac scaffold paths without making them graph modules."""
    return [{"path": row["path"], "purpose": row["purpose"]}
            for row in plan["files"] if not row["path"].endswith(".jac")]


def validate_call(decision: dict, schemas: dict, workspace: Path,
                  hide_machine_plan: bool = False) -> None:
    jsonschema.validate(decision, DECISION_SCHEMA)
    if decision["kind"] == "final":
        return
    if decision["name"] not in schemas:
        raise ValueError("Tool not exposed by adapter")
    jsonschema.validate(decision["args"], schemas[decision["name"]]["parameters"])
    for key in ("file_path", "workdir"):
        if key in decision["args"]:
            path = Path(decision["args"][key])
            path = (workspace / path).resolve()
            if path != workspace and workspace not in path.parents:
                raise ValueError("Tool path is outside workspace")
            if hide_machine_plan and key == "file_path" and path == workspace / ".jaccoder/build_plan.json":
                raise ValueError("The harness progress manifest is private; use docs/plan.md")
            if (hide_machine_plan and key == "file_path" and decision["name"] in {"write_code", "edit_code"}
                    and path != workspace / "docs/plan.md" and not (workspace / "docs/plan.md").is_file()):
                raise ValueError("Write docs/plan.md before application files")
    if decision["name"] == "run_command":
        import shlex
        words = shlex.split(decision["args"]["command"])
        local_cat = len(words) == 2 and words[0] == "cat" and not words[1].startswith("-")
        if local_cat:
            target = (workspace / words[1]).resolve()
            local_cat = workspace in target.parents
            if hide_machine_plan and target == workspace / ".jaccoder/build_plan.json":
                raise ValueError("The harness progress manifest is private; use docs/plan.md")
        jac_check = len(words) >= 2 and words[0] == "jac" and words[1] in {"check", "test", "build", "run"}
        jac_guide = (len(words) == 3 and words[:2] == ["jac", "guide"]
                     and re.fullmatch(r"[A-Za-z0-9_/-]+", words[2]) is not None)
        jac_install = words == ["jac", "install"] and (workspace / "jac.toml").is_file()
        if not local_cat and words not in (["ls", "-la"], ["pwd"]) and not jac_check and not jac_guide and not jac_install:
            raise ValueError("Only ls -la, pwd, cat of one workspace file, bounded jac check/test/build/run, jac guide topic, and jac install after jac.toml exists are enabled")
        if any(c in decision["args"]["command"] for c in ";|&`$<>\n") or decision["args"].get("background"):
            raise ValueError("Shell chaining/background execution is disabled")



def execute_tool(call: dict, step_dir: Path, harness: Path, jac: Path,
                 harness_jac: Path | None = None) -> dict:
    """Execute a validated tool through JacCoder and preserve native results."""
    step_dir.mkdir(parents=True, exist_ok=True)
    write_json(step_dir / "call.json", call)
    result_path = step_dir / "result.json"
    result = jac_cli.execute(["run", str(Path(__file__).with_name("dispatch.jac"))],
        jac=str(harness_jac or jac), cwd=harness, timeout=150,
        env={"REVDEV_CALL": str(step_dir / "call.json"), "REVDEV_RESULT": str(result_path),
             "REVDEV_JAC": str(jac.resolve()), "PYTHONPATH": str(harness),
             "JACCODER_WEB_MODE": "1", "JAC_TEST_JOBS": "0"})
    write_json(step_dir / "execution.json", vars(result))
    if not result.ok or not result_path.is_file():
        raise RuntimeError(f"Dispatch interrupted at {step_dir}; do not retry mutations automatically")
    return json.loads(result_path.read_text())


def run(args: argparse.Namespace) -> None:
    target_jac_version = jac_version(args.jac)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=args.continue_run)
    workspace = out / "workspace"
    workspace.mkdir(exist_ok=args.continue_run)
    cli_cwd = out / "claude"
    cli_cwd.mkdir(exist_ok=args.continue_run)
    base = (args.prompt / "system.txt").read_text()
    if not args.continue_run:
        base = "\n".join(line for line in base.splitlines()
                         if "build_plan.json" not in line and "plan_build" not in line)
    system = base + "\n" + PROTOCOL
    if args.continue_run:
        system = (out / "system.txt").read_text()
    else:
        (out / "system.txt").write_text(system)
    tools = [t for t in json.loads((args.prompt / "tools.json").read_text()) if t["function"]["name"] in SUPPORTED]
    schemas = {t["function"]["name"]: t["function"] for t in tools}
    write_json(out / "tools.json", tools)
    task = json.loads(args.task.read_text())
    plan = json.loads(args.plan.read_text())
    claimed_versions = re.findall(r"\bJac (\d+\.\d+\.\d+)\b",
                                  json.dumps({"task": task, "plan": plan}))
    if any(version != target_jac_version for version in claimed_versions):
        raise ValueError(f"Recipe Jac version differs from --jac {target_jac_version}: {sorted(set(claimed_versions))}")
    plan_md = render_plan_md(plan, task["request"])
    validate_rendered(plan_md, plan)
    if not args.continue_run:
        machine_plan = workspace / ".jaccoder/build_plan.json"
        machine_plan.parent.mkdir(parents=True, exist_ok=True)
        write_json(machine_plan, plan)
        (out / "bootstrap.json").write_text(json.dumps({"machine_plan": plan,
            "student_visible_plan_path": "docs/plan.md", "origin": "adapter_harness_setup"}, indent=2) + "\n")
    context = {"task": task, "implementation_plan": plan_md,
               "support_files": support_files(plan), "workspace": str(workspace),
               "jac_version": target_jac_version, "tools": tools, "events": []}
    metadata = {"mode": "claude_json_decisions_real_jaccoder_tools", "status": "running",
                "task_id": task["task_id"], "schema_version": 1,
                "system_sha256": hashlib.sha256(system.encode()).hexdigest(),
                "reference_id": task["reference_id"], "workspace": str(workspace),
                "transport": "JSON decision; converted tool-call rows require provenance",
                "plan_format": "markdown_mermaid_v2", "jac_version": target_jac_version}
    start_step = 0
    segment = 0
    if args.continue_run:
        old_meta = json.loads((out / "run.json").read_text())
        if old_meta.get("jac_version", "0.34.27") != target_jac_version:
            raise ValueError("Cannot resume a run with a different Jac version")
        workspace = Path(old_meta["workspace"])
        segment = old_meta.get("segment", 0)
        state_path = out / "state.json"
        if state_path.exists():
            context = json.loads(state_path.read_text())
        else:
            last_request = sorted(out.glob("step-*/request.json"))[-1]
            context = json.loads(last_request.read_text())
            if context["workspace"] != str(workspace):
                context = json.loads((out / "conversation.json").read_text())
        if old_meta["status"] == "teacher_finished_unvalidated":
            context = json.loads((out / "conversation.json").read_text())
        metadata.update(workspace=str(workspace), segment=segment,
                        plan_format=old_meta.get("plan_format", "jaccoder_json_v1"))
        start_step = len(list(out.glob("step-*")))
    context["support_files"] = support_files(plan)
    write_json(out / "run.json", metadata)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer), local_files_only=True)
    for step in range(start_step, args.max_steps):
        context["phase"] = "implement" if all((workspace / f["path"]).is_file() for f in plan["files"]) else "scaffold"
        context["phase_instruction"] = phase_instruction(workspace, metadata["plan_format"].startswith("markdown_mermaid_"))
        token_count = len(tokenizer(system + json.dumps(context), add_special_tokens=False)["input_ids"])
        if context["events"] and (token_count > args.max_context_tokens or step == args.checkpoint_step or (args.feedback and step == start_step)):
            cp = out / "checkpoints" / f"segment-{segment}"
            write_json(out / f"segment-{segment}.json", context)
            snapshot = save(workspace, cp, run_id=out.name, after_event_id=f"step-{step-1}", segment_index=segment,
                 reference_id=task["reference_id"], harness_schema_hash=hashlib.sha256(json.dumps(tools).encode()).hexdigest(),
                 environment_fingerprint={"jac": str(args.jac), "harness": str(args.harness),
                                          "harness_jac": str(args.harness_jac or args.jac),
                                          "jac_test_jobs": "0"},
                 completed_work=[e["decision"]["summary"] for e in context["events"][-5:]],
                 remaining_work=["Read saved plan and existing source; complete and verify the task."])
            handoff = resume_handoff(snapshot, context["events"], plan)
            handoff = json.loads(json.dumps(handoff).replace(str(workspace), "/workspace"))
            write_json(cp / "handoff.json", handoff)
            segment += 1
            workspace = out / f"workspace-segment-{segment}"
            restore(cp, workspace)
            pending_feedback = context.get("review_feedback")
            context = {"task": task, "workspace": str(workspace), "jac_version": target_jac_version, "tools": tools,
                       "support_files": support_files(plan),
                       "resume": "Continue from this checkpoint. Read docs/plan.md once. Use the handoff file inventory and observed command results to decide which source needs inspection; read only files needed for the next edit or whose state is uncertain. Reuse reads within this segment. File hashes do not prove behavior. Make one allowed command per run_command call, complete remaining functionality, and rerun acceptance checks.",
                       "handoff": handoff,
                       "events": []}
            if pending_feedback is not None:
                context["review_feedback"] = pending_feedback
            metadata.update(workspace=str(workspace), segment=segment)
            write_json(out / "run.json", metadata)
        if args.feedback and step == start_step:
            context["review_feedback"] = json.loads(args.feedback.read_text())
        context["phase"] = "implement" if all((workspace / f["path"]).is_file() for f in plan["files"]) else "scaffold"
        context["phase_instruction"] = phase_instruction(workspace, metadata["plan_format"].startswith("markdown_mermaid_"))
        write_json(out / "state.json", context)
        step_dir = out / f"step-{step:03d}"
        step_dir.mkdir()
        write_json(step_dir / "resources.json", check_resources(out))
        write_json(step_dir / "request.json", context)
        command = ["claude", "-p", "--tools", "", "--system-prompt-file", str(out / "system.txt"),
                   "--output-format", "json", "--no-session-persistence", "--setting-sources", "",
                   "--strict-mcp-config", "--disable-slash-commands"]
        started = time.time()
        response = subprocess.run(command, input=json.dumps(context), text=True, capture_output=True,
                                  cwd=cli_cwd, timeout=240)
        (step_dir / "claude.stdout.json").write_text(response.stdout)
        (step_dir / "claude.stderr.txt").write_text(response.stderr)
        if response.returncode:
            raise RuntimeError(f"Claude failed at {step_dir}; no retry was executed")
        envelope = json.loads(response.stdout)
        if envelope.get("is_error"):
            raise RuntimeError(f"Claude returned an error at {step_dir}")
        raw = envelope["result"].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        decision, end = json.JSONDecoder().raw_decode(raw.strip())  # tolerate trailing junk such as a stray "}"
        if raw.strip()[end:].strip(" \n}"):
            raise ValueError(f"Unparsable decision tail at {step_dir}")
        write_json(step_dir / "decision.json", decision)
        try:
            validate_call(decision, schemas, workspace,
                          hide_machine_plan=metadata["plan_format"].startswith("markdown_mermaid_"))
        except (ValueError, jsonschema.ValidationError) as exc:
            rejection = {"origin": "adapter_validation", "content": str(exc), "executed": False}
            write_json(step_dir / "rejection.json", rejection)
            context["events"].append({"decision": decision, "result": rejection})
            write_json(out / "conversation.json", context)
            write_json(out / f"segment-{segment}.json", context)
            continue
        if decision["kind"] == "final":
            context["events"].append({"decision": decision})
            metadata.update(status="teacher_finished_unvalidated", steps=step + 1)
            write_json(out / "run.json", metadata)
            write_json(out / "conversation.json", context)
            write_json(out / f"segment-{segment}.json", context)
            print(json.dumps(metadata), flush=True)
            return
        call = {"workspace": str(workspace), "name": decision["name"], "args": decision["args"], "phase": context["phase"]}
        try:
            actual = execute_tool(call, step_dir, args.harness, args.jac, args.harness_jac)
        except RuntimeError:
            metadata.update(status="execution_interrupted", steps=step + 1)
            write_json(out / "run.json", metadata)
            raise
        context["events"].append({"decision": decision, "result": actual})
        write_json(out / "conversation.json", context)
        write_json(out / "state.json", context)
        print(json.dumps({"step": step, "tool": decision["name"], "seconds": round(time.time()-started),
                          "summary": decision["summary"], "result": str(actual["content"])[:160]}), flush=True)
    metadata.update(status="step_limit", steps=args.max_steps)
    write_json(out / "run.json", metadata)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prompt", "task", "plan", "out", "harness", "jac"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--harness-jac", type=Path,
                        help="Jac binary running JacCoder dispatch; defaults to --jac")
    parser.add_argument("--max-steps", type=int, default=60)
    parser.add_argument("--continue-run", action="store_true")
    parser.add_argument("--max-context-tokens", type=int, default=58000)
    parser.add_argument("--checkpoint-step", type=int, default=18)
    parser.add_argument("--tokenizer", type=Path, default=Path("output/model/JacLLM-SFT-Ornith-9B-trajectory-bf16"))
    parser.add_argument("--feedback", type=Path)
    run(parser.parse_args())

# Run =====================================================
if __name__ == "__main__":
    main()
