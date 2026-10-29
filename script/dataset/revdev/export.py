"""Export validated teacher runs with explicit JSON-to-tool-call provenance."""

import argparse, copy, hashlib, json, sys
from pathlib import Path

from transformers import AutoTokenizer

sys.path.append(str(Path(__file__).resolve().parents[2]))
from dataset.pipeline import split_and_write, report
from dataset.trajectory.common import write_trajectories, to_template_input, redact

# Setting =================================================
TASKS = ("revdev_plan", "revdev_scaffold", "revdev_function", "revdev_app", "revdev_resume")
STUDENT_INTERFACE = """
The available tool schemas define this execution interface. plan_build is unavailable;
use the supplied grounded plan and write .jaccoder/build_plan.json before source files.
Call the supplied tools directly. Preserve real failures and verify functionality.
"""

# Functions ===============================================
def event_rows(events: list[dict]) -> list[dict]:
    rows = []
    for event in events:
        decision = event["decision"]
        if decision["kind"] == "final":
            rows.append({"role": "assistant", "mode": "reply", "content": decision["summary"]})
            continue
        rows.append({"role": "assistant", "mode": "tool_call", "name": decision["name"], "args": decision["args"],
                     "weight": 0 if event["result"].get("executed") is False else 1})
        content = event["result"]["content"]
        failed = event["result"].get("executed") is False or any(s in content for s in ("SYNTAX ERRORS", "TYPE ERRORS", "[ERROR]", "FAILED"))
        rows.append({"role": "harness", "mode": "tool_result", "content": content,
                     "status": "error" if failed else "ok", "status_source": "adapter flag and native diagnostic text"})
    return rows


def export(args: argparse.Namespace) -> None:
    run = args.run.resolve()
    verdict = json.loads((run / "validation.json").read_text())
    if verdict["status"] != "accepted":
        raise ValueError("Only accepted runs can be exported")
    tools = json.loads((run / "tools.json").read_text())
    system = (run / "system.txt").read_text().split("# Adapter execution protocol", 1)[0] + STUDENT_INTERFACE
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer), local_files_only=True)
    contexts = [json.loads(p.read_text()) for p in sorted(run.glob("segment-*.json"))]
    if not contexts:
        contexts = [json.loads((run / "conversation.json").read_text())]
    meta = {"source": "agent-synth", "format": "jac", "class": "fullstack", "fp": str(run),
            "split_group": contexts[0]["task"]["reference_id"], "validation": "accepted",
            "transport": "claude_cli_json_to_function_calls", "context_projection": False,
            "system_transform": "adapter JSON-output protocol replaced with tool-call interface instruction",
            "provenance_sha256": hashlib.sha256((run / "run.json").read_bytes()).hexdigest()}
    candidates = {name: [] for name in TASKS}
    trajectories = []
    for index, context in enumerate(contexts):
        prompt = {k: v for k, v in context.items() if k not in {"events", "tools", "phase", "phase_instruction"}}
        opening = [{"role": "harness", "mode": "system", "content": system},
                   {"role": "user", "mode": "prompt", "content": json.dumps(prompt, ensure_ascii=False)}]
        rows = opening + event_rows(context["events"])
        kind = "revdev_app" if index == 0 else "revdev_resume"
        if index < len(contexts) - 1:
            for row in rows:
                if row["role"] == "assistant" and row["mode"] == "reply":
                    row["weight"] = 0
        trajectory = {"meta": {**meta, "fp": f"{run}#segment{index}", "task_type": kind, "segment_index": index, "tools": tools}, "rows": rows}
        candidates[kind].append(trajectory)
        trajectories.append(trajectory)
        # Prefix through the first write of every planned source is the scaffold example.
        if index == 0 and "build_plan" in context:
            planned = {f["path"] for f in context["build_plan"]["files"]}
            seen = set()
            for j, event in enumerate(context["events"]):
                d = event["decision"]
                if d["name"] == "write_code" and event.get("result", {}).get("executed", True):
                    path = Path(d["args"]["file_path"])
                    seen.update(p for p in planned if path.as_posix().endswith("/" + p))
                if seen == planned:
                    candidates["revdev_scaffold"].append({"meta": {**meta, "task_type": "revdev_scaffold"},
                                                        "rows": opening + event_rows(context["events"][:j+1])})
                    break
            plan = next(json.loads(event["decision"]["args"]["content"]) for event in context["events"]
                        if event["decision"]["name"] == "write_code"
                        and event["decision"]["args"].get("file_path", "").endswith("/.jaccoder/build_plan.json")
                        and event.get("result", {}).get("executed", True))
            candidates["revdev_plan"].append({"meta": {**meta, "task_type": "revdev_plan", "context_projection": True},
                "rows": [{"role": "harness", "mode": "system", "content": "Plan a Jac application: files, public interfaces, dependencies, scaffold order and verification. Do not include implementation bodies."},
                         {"role": "user", "mode": "prompt", "content": context["task"]["request"]},
                         {"role": "assistant", "mode": "reply", "content": json.dumps(plan, ensure_ascii=False)}]})
        # Conservative function projection: only dependency-free service files, after an actual read.
        observations = {}
        for j, event in enumerate(context["events"]):
            d = event["decision"]
            if d["kind"] != "tool":
                continue
            path = d["args"].get("file_path", "")
            if d["name"] == "read_file":
                observations[path] = event
            elif d["name"] in {"write_code", "edit_code"}:
                read = observations.pop(path, None)
                if d["name"] == "edit_code" and read and path.endswith("/services/island.jac"):
                    content = read["result"]["content"]
                    if "import " in content or "truncated" in content.lower():
                        continue
                    instruction = context["task"]["request"] + "\nContinue the existing island service. Inspect its definitions and fix its Jac 0.34.27 typing compatibility while preserving behavior."
                    candidates["revdev_function"].append({"meta": {**meta, "task_type": "revdev_function", "context_projection": True,
                                                                      "fp": f"{run}#segment{index}-event{j}", "variant": "function_repair",
                                                                      "segment_index": index, "event_index": j},
                        "rows": [{"role": "harness", "mode": "system", "content": system},
                                 {"role": "user", "mode": "prompt", "content": instruction}] + event_rows([read, event])})
    write_trajectories(trajectories, run / "trajectory.jsonl")
    summary = {}
    for kind, values in candidates.items():
        accepted = []
        small = []
        rejected = []
        for trajectory in values:
            msgs = to_template_input(trajectory, None)
            schemas = [] if kind == "revdev_plan" else tools
            text = tokenizer.apply_chat_template(msgs, tools=schemas, tokenize=False)
            count = len(tokenizer(text, add_special_tokens=False)["input_ids"])
            if count > 65536:
                rejected.append({"reason": "token_cap", "tokens": count})
                continue
            msgs = copy.deepcopy(msgs)
            for message in msgs:
                for call in message.get("tool_calls", []):
                    call["function"]["arguments"] = json.dumps(call["function"]["arguments"], ensure_ascii=False)
            record = redact({"messages": msgs, "tools": json.dumps(schemas), "meta": {**trajectory["meta"], "tokens": count}})
            record["meta"].pop("tools", None)
            accepted.append(record)
            if count <= 16384:
                small.append(record)
        destination = args.out / kind / args.name
        counts = split_and_write(accepted, destination, 0.0)
        report(counts, destination)
        split_and_write(small, args.out / kind / (args.name + "-16k"), 0.0)
        stats = {"accepted": len(accepted), "eligible_16k": len(small), "rejected": rejected,
                 "split_note": "Single-repository pilot is train-only; no independent validation claim."}
        (destination / "statistic.json").write_text(json.dumps(stats, indent=2))
        summary[kind] = stats
    (run / "export.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("dataset/sft"))
    parser.add_argument("--name", default="mindcraft-pilot")
    parser.add_argument("--tokenizer", type=Path, default=Path("output/model/JacLLM-SFT-Ornith-9B-trajectory-bf16"))
    export(parser.parse_args())

# Run =====================================================
if __name__ == "__main__":
    main()
