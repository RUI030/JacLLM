"""Gate exported revdev SFT records before adding them to training recipes."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import jsonschema
from transformers import AutoTokenizer

# Setting =================================================
DEFAULT_TOKENIZER = Path("output/model/JacLLM-SFT-Ornith-9B-trajectory-bf16")
CAP = 65536
DEFAULT_ROOTS = [Path("dataset/sft/revdev")]


# Functions ===============================================
def paths_under(roots: list[Path]) -> list[Path]:
    paths = []
    for root in roots:
        paths.extend(sorted(root.rglob("train.jsonl")))
        paths.extend(sorted(root.rglob("valid.jsonl")))
    return sorted(set(paths))


def training_input(row: dict) -> tuple[list[dict], list[dict]]:
    """Match train.sft.chat_inputs without importing GPU-only Unsloth."""
    messages = []
    for message in row["messages"]:
        clean = {key: value for key, value in message.items() if value is not None}
        if "tool_calls" in clean:
            clean["tool_calls"] = [
                {**call, "function": {**call["function"],
                 "arguments": json.loads(call["function"]["arguments"])}}
                for call in clean["tool_calls"]
            ]
        messages.append(clean)
    return messages, json.loads(row.get("tools") or "[]")


def audit(paths: list[Path], tokenizer) -> dict:
    issues = [] if paths else [{"reason": "no_dataset_files"}]
    rows = []
    splits = defaultdict(set)
    for path in paths:
        split = path.name.removesuffix(".jsonl")
        for index, line in enumerate(path.read_text().splitlines()):
            if not line.strip():
                continue
            location = f"{path}:{index + 1}"
            try:
                row = json.loads(line)
                messages, tools = training_input(row)
                schemas = {tool["function"]["name"]: tool["function"]["parameters"]
                           for tool in tools}
                group = row["meta"].get("split_group", "")
                if not group or group.startswith("ref_") or "/" in group:
                    issues.append({"row": location, "reason": "noncanonical_split_group", "value": group})
                splits[group].add(split)
                pending = []
                supervised = 0
                for message in messages:
                    content = json.dumps(message, ensure_ascii=False)
                    if "/home/imrui/" in content or "dataset/raw/repo/" in content:
                        issues.append({"row": location, "reason": "model_visible_local_path"})
                    if message["role"] == "assistant":
                        supervised += message.get("weight", 1) != 0
                        for call in message.get("tool_calls", []):
                            name = call["function"]["name"]
                            if name not in schemas:
                                issues.append({"row": location, "reason": "unknown_tool", "name": name})
                            else:
                                try:
                                    jsonschema.validate(call["function"]["arguments"], schemas[name])
                                except jsonschema.ValidationError as exc:
                                    issues.append({"row": location, "reason": "tool_schema", "name": name,
                                                   "detail": exc.message})
                            pending.append(call["id"])
                    elif message["role"] == "tool":
                        if not pending or pending.pop(0) != message.get("tool_call_id"):
                            issues.append({"row": location, "reason": "tool_result_pairing"})
                if pending:
                    issues.append({"row": location, "reason": "missing_tool_results", "count": len(pending)})
                if not supervised:
                    issues.append({"row": location, "reason": "no_supervised_assistant"})
                rendered = tokenizer.apply_chat_template(messages, tools=tools, tokenize=False)
                tokens = len(tokenizer(rendered, add_special_tokens=False)["input_ids"])
                if tokens != row["meta"].get("tokens"):
                    issues.append({"row": location, "reason": "token_metadata", "actual": tokens,
                                   "stored": row["meta"].get("tokens")})
                if tokens > CAP:
                    issues.append({"row": location, "reason": "over_cap", "tokens": tokens})
                rows.append({"location": location, "task_type": row["meta"].get("task_type"),
                             "split_group": group, "split": split, "tokens": tokens,
                             "supervised_turns": supervised})
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                issues.append({"row": location, "reason": "unreadable_record", "detail": str(exc)})
    for group, assigned in splits.items():
        if {"train", "valid"} <= assigned:
            issues.append({"reason": "repo_split_overlap", "split_group": group})
    return {"status": "passed" if not issues else "failed", "records": len(rows),
            "total_tokens": sum(row["tokens"] for row in rows), "issues": issues, "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roots", type=Path, nargs="+", default=DEFAULT_ROOTS)
    parser.add_argument("--tokenizer", type=Path, default=DEFAULT_TOKENIZER)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer), local_files_only=True)
    report = audit(paths_under(args.roots), tokenizer)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2))
    if report["issues"]:
        raise SystemExit(1)


# Run =====================================================
if __name__ == "__main__":
    main()
