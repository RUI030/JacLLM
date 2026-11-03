"""Export validated teacher runs with explicit JSON-to-tool-call provenance."""

import argparse, copy, hashlib, json, sys
from collections import Counter
from pathlib import Path

from transformers import AutoTokenizer

sys.path.append(str(Path(__file__).resolve().parents[2]))
from dataset.pipeline import split_and_write, report
from dataset.trajectory.common import write_trajectories, to_template_input, redact

# Setting =================================================
TASKS = ("revdev_plan", "revdev_scaffold", "revdev_function", "revdev_app", "revdev_resume")
UNIFIED_TASK = "revdev"
STUDENT_INTERFACE = """
The available tool schemas define this execution interface. plan_build is unavailable;
write the supplied grounded plan to docs/plan.md before source files. Use its Mermaid
Jac-module graph, frontend/backend module lists, and file order. Treat configuration
and styling as supporting files outside those module lists. The harness manages its
machine progress manifest.
Call the supplied tools directly. Preserve real failures and verify functionality.
"""
STUDENT_INTERFACE_V1 = """
The available tool schemas define this execution interface. plan_build is unavailable;
write the supplied grounded plan to docs/plan.md before source files. Use its Mermaid
module graph and file order. The harness manages its machine progress manifest.
Call the supplied tools directly. Preserve real failures and verify functionality.
"""
LEGACY_STUDENT_INTERFACE = """
The available tool schemas define this execution interface. plan_build is unavailable;
use the supplied grounded plan and write .jaccoder/build_plan.json before source files.
Call the supplied tools directly. Preserve real failures and verify functionality.
"""

# Functions ===============================================
def event_rows(events: list[dict]) -> list[dict]:
    rows = []
    for event in events:
        decision = event["decision"]
        if event.get("result", {}).get("origin") == "adapter_validation":
            # No harness tool ran. A schema-invalid proposal cannot be emitted
            # as a tool call in a dataset whose tool schemas are authoritative.
            continue
        if decision["kind"] == "final":
            # A schema-rejected final never ended the run or changed the
            # workspace. Keep it in raw evidence; project the later valid
            # continuation from the same execution state.
            if event.get("result", {}).get("executed") is False:
                continue
            rows.append({"role": "assistant", "mode": "reply", "content": decision["summary"]})
            continue
        rows.append({"role": "assistant", "mode": "tool_call", "name": decision["name"], "args": decision["args"],
                     "weight": 0 if event["result"].get("executed") is False else 1})
        content = event["result"]["content"]
        failed = event["result"].get("executed") is False or any(s in content for s in ("SYNTAX ERRORS", "TYPE ERRORS", "[ERROR]", "FAILED"))
        rows.append({"role": "harness", "mode": "tool_result", "content": content,
                     "status": "error" if failed else "ok", "status_source": "adapter flag and native diagnostic text"})
    return rows


def normalize_paths(value, roots: list[Path]):
    """Project run-local paths to a stable student workspace, retaining raw evidence."""
    mappings = [(str(path.resolve()), "/workspace") for path in roots]
    mappings += [(str(Path.home() / ".cache/jac"), "/runtime/jac-cache"),
                 (str(Path(__file__).resolve().parents[3]), "/project"),
                 (str(Path.home()), "/home/student")]
    mappings.sort(key=lambda pair: len(pair[0]), reverse=True)
    if isinstance(value, str):
        for source, target in mappings:
            value = value.replace(source, target)
        return value
    if isinstance(value, list):
        return [normalize_paths(item, roots) for item in value]
    if isinstance(value, dict):
        return {key: normalize_paths(item, roots) for key, item in value.items()}
    return value


def planning_system(plan_format: str, jac_version: str | None = None) -> str:
    version = f"Target Jac version: {jac_version}. " if jac_version else ""
    if plan_format == "markdown_mermaid_v2":
        instruction = ("Plan a Jac application in Markdown at docs/plan.md. Include a Mermaid graph "
                       "of .jac module dependencies, explicit frontend and backend .jac module lists, "
                       "public interfaces, build order, and verification. Treat configuration and styling "
                       "as supporting implementation files outside the module lists. Do not include "
                       "implementation bodies.")
    elif plan_format.startswith("markdown_mermaid_"):
        instruction = ("Plan a Jac application in Markdown at docs/plan.md. Include a Mermaid "
                       "module dependency diagram, files, public interfaces, build order, and "
                       "verification. Do not include implementation bodies.")
    else:
        instruction = ("Plan a Jac application: files, public interfaces, dependencies, "
                       "scaffold order and verification. Do not include implementation bodies.")
    return version + instruction


def unified_record(record: dict, stage: str, prior_split: str) -> dict:
    meta = record["meta"]
    if meta.get("validation") != "accepted" or not meta.get("split_group"):
        raise ValueError("Unified revdev accepts only validated records with a source group")
    return {**record, "meta": {**meta, "task_type": UNIFIED_TASK, "stage": stage,
                               "source_split": "train", "prior_export_split": prior_split}}


def write_unified(records: list[dict], destination: Path) -> dict:
    """Write one deterministic, train-only dataset, replacing repeated exports."""
    keyed = {}
    for record in records:
        meta = record["meta"]
        key = (meta["stage"], meta["fp"])
        keyed[key] = record
    ordered = [keyed[key] for key in sorted(keyed)]
    counts = split_and_write(ordered, destination, 0.0)
    (destination / "valid.jsonl").unlink(missing_ok=True)
    stages = Counter(record["meta"]["stage"] for record in ordered)
    groups = Counter(record["meta"]["split_group"] for record in ordered)
    stats = {"records": counts["train"], "context_tokens": sum(r["meta"]["tokens"] for r in ordered),
             "stage_counts": dict(sorted(stages.items())),
             "source_groups": dict(sorted(groups.items())),
             "split_policy": "All accepted source apps are train; evaluation uses a separate unseen app.",
             "mirror_policy": "Exclude -16k duplicate exports."}
    (destination / "statistic.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    return stats


def assemble_existing(source_root: Path, out_root: Path, name: str) -> dict:
    """Collect accepted stage projections into one train-only revdev dataset.

    The old stage directories remain provenance for earlier runs. Their 16k
    mirrors are excluded because they repeat the same examples. A future
    evaluation app must be held outside this training collection entirely.
    """
    records = []
    for stage_root in sorted(source_root.glob("revdev_*")):
        if not stage_root.is_dir():
            continue
        for dataset_dir in sorted(stage_root.iterdir()):
            if not dataset_dir.is_dir() or dataset_dir.name.endswith("-16k"):
                continue
            for split in ("train", "valid"):
                path = dataset_dir / f"{split}.jsonl"
                if not path.is_file():
                    continue
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    meta = record["meta"]
                    if meta.get("validation") != "accepted":
                        raise ValueError(f"Unaccepted projection at {path}:{number}")
                    if meta.get("task_type") != stage_root.name or not meta.get("split_group"):
                        raise ValueError(f"Invalid stage or source group at {path}:{number}")
                    records.append(unified_record(record, stage_root.name, split))
    if not records:
        raise ValueError(f"No accepted revdev stage records under {source_root}")
    destination = out_root / UNIFIED_TASK / name
    stats = write_unified(records, destination)
    print(json.dumps({"destination": str(destination), **stats}, indent=2))
    return stats


def export(args: argparse.Namespace) -> None:
    run = args.run.resolve()
    verdict = json.loads((run / "validation.json").read_text())
    if verdict["status"] != "accepted":
        raise ValueError("Only accepted runs can be exported")
    if not args.split_group or not args.split_group.strip():
        raise ValueError("--split-group must name the canonical source repository before export")
    tools = json.loads((run / "tools.json").read_text())
    run_meta = json.loads((run / "run.json").read_text())
    markdown_plan = run_meta.get("plan_format", "").startswith("markdown_mermaid_")
    system = ("# JacCoder reverse development student\n" +
              (STUDENT_INTERFACE if run_meta.get("plan_format") == "markdown_mermaid_v2"
               else STUDENT_INTERFACE_V1) if markdown_plan else
              (run / "system.txt").read_text().split("# Adapter execution protocol", 1)[0]
              + LEGACY_STUDENT_INTERFACE)
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer), local_files_only=True)
    contexts = [json.loads(p.read_text()) for p in sorted(run.glob("segment-*.json"))]
    if not contexts:
        contexts = [json.loads((run / "conversation.json").read_text())]
    workspace_roots = [Path(context["workspace"]) for context in contexts]
    bootstrap = run / "bootstrap.json"
    ground_plan = json.loads(bootstrap.read_text())["machine_plan"] if bootstrap.is_file() else {}
    app_class = "backend" if (ground_plan.get("ui", {}).get("backend_required")
                              and not ground_plan.get("ui", {}).get("pages")) else "fullstack"
    meta = {"source": "agent-synth", "format": "jac", "class": app_class, "fp": str(run),
            "split_group": args.split_group,
            "source_split": args.split,
            "validation": "accepted",
            "transport": "claude_cli_json_to_function_calls", "context_projection": True,
            "path_projection": "run workspaces -> /workspace; local runtime roots normalized",
            "system_transform": "adapter JSON-output protocol replaced with tool-call interface instruction; Markdown runs remove legacy JSON planner prompt",
            "provenance_sha256": hashlib.sha256((run / "run.json").read_bytes()).hexdigest()}
    candidates = {name: [] for name in TASKS}
    trajectories = []
    for index, context in enumerate(contexts):
        prompt = {k: v for k, v in context.items() if k not in {"events", "tools", "phase", "phase_instruction"}}
        opening = [{"role": "harness", "mode": "system", "content": system},
                   {"role": "user", "mode": "prompt", "content": json.dumps(prompt, ensure_ascii=False)}]
        rows = normalize_paths(opening + event_rows(context["events"]), workspace_roots)
        kind = "revdev_app" if index == 0 else "revdev_resume"
        if index < len(contexts) - 1:
            for row in rows:
                if row["role"] == "assistant" and row["mode"] == "reply":
                    row["weight"] = 0
        rejected_finals = sum(event["decision"]["kind"] == "final"
                              and event.get("result", {}).get("executed") is False
                              for event in context["events"])
        adapter_rejections = sum(event.get("result", {}).get("origin") == "adapter_validation"
                                 for event in context["events"])
        trajectory = {"meta": {**meta, "fp": f"{run}#segment{index}", "task_type": kind,
                               "segment_index": index, "tools": tools,
                               "projection_excluded_rejected_finals": rejected_finals,
                               "projection_excluded_adapter_rejections": adapter_rejections},
                      "rows": rows}
        candidates[kind].append(trajectory)
        trajectories.append(trajectory)
        # Prefix through the first write of every planned source is the scaffold example.
        if index == 0 and ("build_plan" in context or markdown_plan):
            machine_plan = (json.loads((run / "bootstrap.json").read_text())["machine_plan"]
                            if markdown_plan else context["build_plan"])
            planned = {f["path"] for f in machine_plan["files"]}
            seen = set()
            for j, event in enumerate(context["events"]):
                d = event["decision"]
                if d["name"] == "write_code" and event.get("result", {}).get("executed", True):
                    path = Path(d["args"]["file_path"])
                    seen.update(p for p in planned if path.as_posix().endswith("/" + p))
                if seen == planned:
                    candidates["revdev_scaffold"].append({"meta": {**meta, "task_type": "revdev_scaffold"},
                                                        "rows": normalize_paths(opening + event_rows(context["events"][:j+1]), workspace_roots)})
                    break
            plan = next(event["decision"]["args"]["content"] for event in context["events"]
                        if event["decision"]["name"] == "write_code"
                        and event["decision"]["args"].get("file_path", "").endswith(
                            "docs/plan.md" if markdown_plan else ".jaccoder/build_plan.json")
                        and event.get("result", {}).get("executed", True))
            if not markdown_plan:
                plan = json.loads(plan)
            candidates["revdev_plan"].append({"meta": {**meta, "task_type": "revdev_plan", "context_projection": True},
                "rows": [{"role": "harness", "mode": "system",
                          "content": planning_system(run_meta.get("plan_format", ""),
                                                     context.get("jac_version"))},
                         {"role": "user", "mode": "prompt", "content": context["task"]["request"]},
                         {"role": "assistant", "mode": "reply", "content": plan if markdown_plan else json.dumps(plan, ensure_ascii=False)}]})
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
                        "rows": normalize_paths([{"role": "harness", "mode": "system", "content": system},
                                 {"role": "user", "mode": "prompt", "content": instruction}] + event_rows([read, event]), workspace_roots)})
    write_trajectories(trajectories, run / "trajectory.jsonl")
    summary = {}
    active_records = []
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
            active_records.append(unified_record(record, kind, args.split))
            if count <= 16384:
                small.append(record)
        destination = run / "stage_exports" / kind / args.name
        counts = split_and_write(accepted, destination, 1.0 if args.split == "valid" else 0.0)
        report(counts, destination)
        split_and_write(small, run / "stage_exports" / kind / (args.name + "-16k"),
                        1.0 if args.split == "valid" else 0.0)
        stats = {"accepted": len(accepted), "eligible_16k": len(small), "rejected": rejected,
                 "split_note": "Historical stage export uses " + args.split
                 + "; active unified revdev collects every accepted app into train."}
        (destination / "statistic.json").write_text(json.dumps(stats, indent=2))
        summary[kind] = stats
    (run / "export.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    active = args.out / UNIFIED_TASK / "accepted"
    existing_path = active / "train.jsonl"
    existing = ([json.loads(line) for line in existing_path.read_text().splitlines()]
                if existing_path.is_file() else [])
    stats = write_unified(existing + active_records, active)
    print(json.dumps({"destination": str(active), **stats}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--assemble-existing", action="store_true",
                        help="Collect accepted stage exports into one train-only revdev dataset")
    parser.add_argument("--source-root", type=Path,
                        help="Historical revdev stage-export root for --assemble-existing")
    parser.add_argument("--out", type=Path, default=Path("dataset/sft"))
    parser.add_argument("--name", default="mindcraft-pilot")
    parser.add_argument("--split-group", help="Canonical source repository group for split leakage control")
    parser.add_argument("--split", choices=("train", "valid"), default="train",
                        help="Legacy stage-export split; the unified revdev dataset always trains accepted apps")
    parser.add_argument("--tokenizer", type=Path, default=Path("output/model/JacLLM-SFT-Ornith-9B-trajectory-bf16"))
    args = parser.parse_args()
    if args.assemble_existing:
        if args.source_root is None:
            parser.error("--source-root is required with --assemble-existing")
        assemble_existing(args.source_root, args.out, args.name)
    elif args.run:
        export(args)
    else:
        parser.error("--run is required unless --assemble-existing is used")

# Run =====================================================
if __name__ == "__main__":
    main()
