"""Generate teacher decisions with Claude CLI and execute real JacCoder tools."""

import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path

import jsonschema

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli
from dataset.revdev.checkpoint import save, restore

# Setting =================================================
SUPPORTED = {"read_file", "write_code", "edit_code", "run_command", "load_jac_skill"}
PROTOCOL = """
# Adapter execution protocol (takes precedence over unavailable interface features)
You are operating through a synchronous JacCoder adapter. Built-in Claude tools are disabled.
Only the schemas in the user payload are executable. Return a JSON object with:
kind: 'tool' or 'final'; name: tool name or ''; args: tool arguments or {};
summary: a brief observable progress statement. Never return invented results.
Select ONE tool per response; its actual result will be supplied on the next turn.
plan_build is unavailable in this adapter. The complete grounded build plan is supplied
as visible context; write it to .jaccoder/build_plan.json using write_code before source files.
Use its public interfaces and dependency order. Evidence-based changes can be written back.
Use the pinned Jac version in the task, including its client syntax. load_jac_skill may
return newer guidance: check its stated version. For Jac 0.34.27 use explicit cl blocks.
Do not access anything outside workspace except the supplied load_jac_skill tool.
run_command is for bounded local build/test commands only. Never install packages, delete
outside the workspace, access credentials, or use networking. Do not use background jobs.
Create test files in the workspace and run them before finishing. Keep the app small,
functional and deterministic. Use no external AI. Finish only after acceptance checks.
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


def check_resources(path: Path) -> dict:
    import shutil
    mem = {line.split(":")[0]: int(line.split()[1]) * 1024
           for line in Path("/proc/meminfo").read_text().splitlines()}
    disk = shutil.disk_usage(path)
    state = {"time": time.time(), "ram_available": mem["MemAvailable"], "disk_free": disk.free}
    if mem["MemAvailable"] < 4 * 1024**3 or disk.free < 20 * 1024**3:
        raise RuntimeError(f"Resource floor reached: {state}")
    return state


def validate_call(decision: dict, schemas: dict, workspace: Path) -> None:
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
    if decision["name"] == "run_command":
        import shlex
        words = shlex.split(decision["args"]["command"])
        local_cat = len(words) == 2 and words[0] == "cat" and not words[1].startswith("-")
        if local_cat:
            target = (workspace / words[1]).resolve()
            local_cat = workspace in target.parents
        if not local_cat and words not in (["ls", "-la"], ["pwd"]) and (not words or words[0] != "jac" or len(words) < 2 or words[1] not in {"check", "test", "build", "run"}):
            raise ValueError("Only ls -la, pwd, cat of one workspace file and bounded jac check/test/build/run commands are enabled")
        if any(c in decision["args"]["command"] for c in ";|&`$<>\n") or decision["args"].get("background"):
            raise ValueError("Shell chaining/background execution is disabled")



def execute_tool(call: dict, step_dir: Path, harness: Path, jac: Path) -> dict:
    """Execute a validated tool through JacCoder and preserve native results."""
    step_dir.mkdir(parents=True, exist_ok=True)
    write_json(step_dir / "call.json", call)
    result_path = step_dir / "result.json"
    result = jac_cli.execute(["run", str(Path(__file__).with_name("dispatch.jac"))],
        jac=str(jac), cwd=harness, timeout=150,
        env={"REVDEV_CALL": str(step_dir / "call.json"), "REVDEV_RESULT": str(result_path),
             "PYTHONPATH": str(harness), "JACCODER_WEB_MODE": "1"})
    write_json(step_dir / "execution.json", vars(result))
    if not result.ok or not result_path.is_file():
        raise RuntimeError(f"Dispatch interrupted at {step_dir}; do not retry mutations automatically")
    return json.loads(result_path.read_text())


def run(args: argparse.Namespace) -> None:
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=args.continue_run)
    workspace = out / "workspace"
    workspace.mkdir(exist_ok=args.continue_run)
    cli_cwd = out / "claude"
    cli_cwd.mkdir(exist_ok=args.continue_run)
    base = (args.prompt / "system.txt").read_text()
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
    context = {"task": task, "build_plan": plan, "workspace": str(workspace),
               "jac_version": "0.34.27", "tools": tools, "events": []}
    metadata = {"mode": "claude_json_decisions_real_jaccoder_tools", "status": "running",
                "task_id": task["task_id"], "schema_version": 1,
                "system_sha256": hashlib.sha256(system.encode()).hexdigest(),
                "reference_id": task["reference_id"], "workspace": str(workspace),
                "transport": "JSON decision; converted tool-call rows require provenance"}
    start_step = 0
    segment = 0
    if args.continue_run:
        old_meta = json.loads((out / "run.json").read_text())
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
        metadata.update(workspace=str(workspace), segment=segment)
        start_step = len(list(out.glob("step-*")))
    write_json(out / "run.json", metadata)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer), local_files_only=True)
    for step in range(start_step, args.max_steps):
        context["phase"] = "implement" if all((workspace / f["path"]).is_file() for f in plan["files"]) else "scaffold"
        context["phase_instruction"] = "During scaffold phase ALL function and ability bodies must be ONLY raise NotImplementedError(); UI entry functions may return minimal JSX placeholders. No working service bodies until every planned file exists."
        token_count = len(tokenizer(system + json.dumps(context), add_special_tokens=False)["input_ids"])
        if context["events"] and (token_count > args.max_context_tokens or step == args.checkpoint_step or (args.feedback and step == start_step)):
            cp = out / "checkpoints" / f"segment-{segment}"
            write_json(out / f"segment-{segment}.json", context)
            save(workspace, cp, run_id=out.name, after_event_id=f"step-{step-1}", segment_index=segment,
                 reference_id=task["reference_id"], harness_schema_hash=hashlib.sha256(json.dumps(tools).encode()).hexdigest(),
                 environment_fingerprint={"jac": str(args.jac), "harness": str(args.harness)},
                 completed_work=[e["decision"]["summary"] for e in context["events"][-5:]],
                 remaining_work=["Read saved plan and existing source; complete and verify the task."])
            segment += 1
            workspace = out / f"workspace-segment-{segment}"
            restore(cp, workspace)
            context = {"task": task, "workspace": str(workspace), "jac_version": "0.34.27", "tools": tools,
                       "resume": "Continue this existing project. First read .jaccoder/build_plan.json and relevant existing source. Plan done flags can mean scaffolds; verify bodies. Complete remaining functionality and acceptance checks.",
                       "events": []}
            metadata.update(workspace=str(workspace), segment=segment)
            write_json(out / "run.json", metadata)
        if args.feedback and step == start_step:
            context["review_feedback"] = json.loads(args.feedback.read_text())
        context["phase"] = "implement" if all((workspace / f["path"]).is_file() for f in plan["files"]) else "scaffold"
        context["phase_instruction"] = "During scaffold phase ALL function and ability bodies must be ONLY raise NotImplementedError(); UI entry functions may return minimal JSX placeholders. No working service bodies until every planned file exists."
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
        decision = json.loads(raw)
        write_json(step_dir / "decision.json", decision)
        try:
            validate_call(decision, schemas, workspace)
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
            actual = execute_tool(call, step_dir, args.harness, args.jac)
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
