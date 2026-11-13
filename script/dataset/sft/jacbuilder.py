"""Verified JacBuilder Teacher actions -> local-only, context-preserving SFT review records."""

import argparse, ast, collections, copy, hashlib, json, shutil, sys, tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from dataset.pipeline import split_and_write
from dataset.trajectory.common import redact
from utils.classifier import classify_structural as classify

# Setting =================================================
TASK_TYPE = "jacbuilder"
DS_NAME   = "debug-pilot-v1"
SOURCE    = "session"
DS_FORMAT = "chat"
REPO      = Path(__file__).resolve().parents[3]
OUT_DIR   = REPO / "dataset" / "sft" / TASK_TYPE / DS_NAME
MAX_TOKENS = 65536

# Functions ===============================================
def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sft_helpers(repo: Path) -> dict:
    """Load only the existing pure tokenization functions, without importing Unsloth or loading a model."""
    path = repo / "script/train/sft.py"
    names = {"chat_inputs", "tokenize_with_assistant_mask"}
    nodes = [n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in nodes} != names:
        raise ValueError("Existing SFT tokenization helpers not found")
    namespace = {"json": json}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def canonical_messages(messages: list[dict]) -> tuple[list[dict], list[int]]:
    """Preserve each text block exactly while making content uniformly strings for Arrow."""
    result, text_blocks = copy.deepcopy(messages), []
    for i, message in enumerate(result):
        content = message.get("content")
        if isinstance(content, list):
            if len(content) != 1 or content[0].get("type") != "text":
                raise ValueError("Only a single losslessly reversible text block is supported")
            message["content"] = content[0]["text"]
            text_blocks.append(i)
        if message.get("role") == "assistant":
            message["weight"] = 0
            message["masked"] = "historical_context_only"
    return result, text_blocks


def build_record(snapshot: Path, unit: dict, calls: list[dict]) -> dict:
    """An exact Teacher request prefix plus one verified edit, with all assistant loss still disabled."""
    episode = unit["episode"]
    folder = snapshot / "docs/experiments/data_collection_pilot" / episode
    root = next((folder / "episodes").iterdir())
    expected = {item["path"]: item["sha256"] for item in read_json(snapshot / "MANIFEST.json")["files"]}
    for item in folder.rglob("*"):
        if item.is_file() and expected.get(str(item.relative_to(snapshot))) != sha256(item):
            raise ValueError("Episode file differs from the immutable snapshot manifest")
    journal = root / "trajectory.jsonl"
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    event_map = {e["sequence"]: e for e in events}
    transport = event_map[unit["sequence"]]
    if transport["kind"] != "teacher_model_transport" or transport["actor"] != "teacher":
        raise ValueError("Candidate must come from a Teacher transport record")
    action = transport["data"]["action"]
    if action != unit["action"] or action["tool"] not in {"edit_code", "write_code"}:
        raise ValueError("Candidate action differs from audit evidence")
    matches = [p for p in (root / ".teacher_model_calls").iterdir()
               if read_json(p / "stdout.json").get("structured_output") == action]
    if len(matches) != 1:
        raise ValueError("Saved Teacher request is ambiguous or missing")
    cli = matches[0]
    request = read_json(cli / "request.json")
    process = read_json(cli / "process.json")
    if process["exit_code"] != 0 or process["timed_out"]:
        raise ValueError("Teacher transport did not finish successfully")
    linked = [c for c in calls if c["episode"] == episode and c["actor"] == "teacher"
              and c["signature"] == {"tool": action["tool"], "arguments": action["arguments"]}]
    if len(linked) != 1 or linked[0]["source"]["sha256"] != sha256(journal):
        raise ValueError("Candidate does not have one source-verified provider identity")
    indexed = linked[0]
    model_event = next(e for e in events if e["sequence"] == indexed["first_sequence"])
    target = copy.deepcopy(model_event["data"]["reply"])
    if len(target.get("tool_calls", [])) != 1:
        raise ValueError("Pilot review records require one exact verified target action")
    outcome_events = [event_map[n] for n in indexed["body_outcome_sequences"]]
    if not outcome_events or any(e["data"].get("status") != "ok" for e in outcome_events):
        raise ValueError("Teacher edit lacks a completed successful body outcome")
    recovery = read_json(folder / "recovery.json")
    verification = recovery["verification"]
    final = read_json(folder / "case-result.json")["final_verification"]
    if not verification["ok"] or not final["ok"] or not verification["checks"]["scope_ok"]:
        raise ValueError("Repair or handback is not independently verified within scope")
    if any(c["exit_code"] != 0 for c in verification["checks"]["checks"] + final["checks"]["checks"]):
        raise ValueError("Independent checks did not all pass")
    change = next(c for c in recovery["handback"]["changes"] if c["path"] == action["arguments"]["file_path"])
    source = root / Path(change["path"]).relative_to(read_json(folder / "student.json")["workspace"])
    before = next(e["data"]["content"] for e in events if e["kind"] == "teacher_before_write" and e["data"]["path"] == change["path"])
    if hashlib.sha256(before.encode()).hexdigest() != change["before_sha256"] or sha256(source) != change["after_sha256"]:
        raise ValueError("Teacher change hashes do not match the archived source")
    messages, text_blocks = canonical_messages(request["messages"])
    target["weight"], target["masked"] = 0, "pending_teacher_review"
    messages.append(target)
    record = {
        "messages": messages,
        "tools": json.dumps(request["tools"], ensure_ascii=False),
        "meta": {
            "source": SOURCE, "format": DS_FORMAT, "class": classify(action["arguments"].get("new_string", action["arguments"].get("content", ""))),
            "task_type": TASK_TYPE, "fp": f"{episode}#{indexed['provider_call_id']}",
            "id": f"{episode}#{indexed['provider_call_id']}", "harness": "jaccoder_teacher",
            "model": process["requested_model"], "jac_version": "0.34.28", "split_group": "jacbuilder/import-reference-typo",
            "episode": episode, "provider_call_id": indexed["provider_call_id"], "actor": "teacher",
            "origin_file": str(journal.relative_to(snapshot)), "origin_sha256": sha256(journal),
            "request_file": str((cli / "request.json").relative_to(snapshot)), "request_sha256": sha256(cli / "request.json"),
            "action_sequence": indexed["first_sequence"], "transport_sequence": unit["sequence"],
            "proposed_target_message_index": len(messages) - 1, "reversible_text_block_indices": text_blocks,
            "verification": "compiler_and_original_public_behavior_assertions_plus_readonly_continuation",
            "verification_receipt": verification, "change": change,
            "review_status": "pending", "training_approved": False, "local_only": True,
            "quality_flags": ["no_fresh_teacher_target_read", "single_template_family", "public_fixture_tests", "long_context"],
            "loss_requirement": "Use weight-aware per-conversation masks; ordinary unpacked response-only SFT ignores message weights",
        },
    }
    clean = redact(record)
    clean["meta"]["redaction_applied"] = clean != record
    return clean


def validate_record(record: dict, tokenizer, helpers: dict, max_tokens: int) -> tuple[dict, list[int]]:
    """Exercise JacLLM's actual packed-SFT mask function in memory, without training or truncation."""
    messages, tools = helpers["chat_inputs"](record)
    text = tokenizer.apply_chat_template(messages, tools=tools, tokenize=False, add_generation_prompt=False)
    count = len(tokenizer(text, add_special_tokens=False)["input_ids"])
    if count > max_tokens:
        raise ValueError(f"Whole context requires {count} tokens; refusing to truncate to {max_tokens}")
    actual = helpers["tokenize_with_assistant_mask"](messages, tools, tokenizer, max_tokens)
    if any(label != -100 for label in actual["labels"]):
        raise ValueError("Pending-review record unexpectedly has active labels")
    proposed = copy.deepcopy(messages)
    target = record["meta"]["proposed_target_message_index"]
    if target != len(proposed) - 1 or proposed[target]["role"] != "assistant":
        raise ValueError("Proposed target must be the final original Teacher action")
    proposed[target]["weight"] = 1
    preview = helpers["tokenize_with_assistant_mask"](proposed, tools, tokenizer, max_tokens)
    ids = [label for label in preview["labels"] if label != -100]
    if not ids:
        raise ValueError("Proposed Teacher action would have no target tokens")
    return {"id": record["meta"]["id"], "rendered_tokens": count, "active_target_tokens": 0,
            "proposed_teacher_target_tokens": len(ids), "truncated": False,
            "weight_aware_mask_executed": True, "decoded_proposed_target": tokenizer.decode(ids)}, ids


def export(snapshot: Path, audit: Path, index: Path, tokenizer_path: Path, output: Path, max_tokens: int = MAX_TOKENS) -> dict:
    """Write local review-only SFT rows and provenance; never train or promote labels."""
    from transformers import AutoTokenizer
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    units = read_json(audit / "review_units.json")
    calls = [json.loads(line) for line in (index / "tool_calls.jsonl").read_text().splitlines()]
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path), local_files_only=True)
    helpers = sft_helpers(REPO)
    records, validation, tokens = [], [], collections.Counter()
    for unit in units:
        record = build_record(snapshot, unit, calls)
        check, proposed = validate_record(record, tokenizer, helpers, max_tokens)
        record["meta"]["tokens"] = check["rendered_tokens"]
        record["meta"]["proposed_target_tokens"] = check["proposed_teacher_target_tokens"]
        records.append(record); validation.append(check); tokens.update(proposed)
    output.mkdir(parents=True)
    # Shared pipeline writes the JSONL; publish as review, not an accidental train split.
    with tempfile.TemporaryDirectory(prefix="jacbuilder-review-") as temporary:
        split_and_write(records, temporary, 0.0)
        shutil.copy2(Path(temporary) / "train.jsonl", output / "review.jsonl")
    ledger = [{"episode": call["episode"], "actor": call["actor"], "provider_call_id": call["provider_call_id"],
               "tool": call["signature"]["tool"], "source": call["source"],
               "disposition": "candidate_pending_review" if any(r["meta"]["episode"] == call["episode"] and r["meta"]["provider_call_id"] == call["provider_call_id"] for r in records) else "context_only",
               "training_approved": False} for call in calls]
    statistic = {"status": "review_only", "records": {"review": len(records), "train": 0, "valid": 0},
                 "rendered_tokens": sum(v["rendered_tokens"] for v in validation), "active_target_tokens": 0,
                 "proposed_teacher_target_tokens": sum(v["proposed_teacher_target_tokens"] for v in validation),
                 "split_groups": sorted({r["meta"]["split_group"] for r in records}), "max_tokens": max_tokens,
                 "validation": validation, "raw_actions_accounted_for": len(ledger), "raw_sources_unchanged": all(sha256(snapshot / r["source"]["path"]) == r["source"]["sha256"] for r in calls)}
    manifest = {"snapshot": str(snapshot), "snapshot_manifest_sha256": sha256(snapshot / "MANIFEST.json"),
                "audit": str(audit), "tool_index": str(index), "producer_sha256": sha256(Path(__file__)),
                "sft_mask_source_sha256": sha256(REPO / "script/train/sft.py"),
                "tokenizer": str(tokenizer_path), "tokenizer_sha256": sha256(tokenizer_path / "tokenizer.json"),
                "review_sha256": sha256(output / "review.jsonl"), "training_started": False,
                "raw_history_policy": "Immutable external originals; no windowing, summarization or truncation",
                "local_only": True}
    for name, value in [("statistic.json", statistic), ("manifest.json", manifest), ("disposition.json", ledger)]:
        (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    (output / "README.md").write_text(
        "# JacBuilder debug pilot v1 — review only\n\n"
        "Two verified Teacher edit candidates in JacLLM SFT `{messages, tools, meta}` format. "
        "`tools` and function arguments are JSON strings. Exact captured Teacher request prefixes are retained; "
        "single text blocks are reversibly unwrapped for Arrow (indices in meta). Raw logs remain external and unchanged.\n\n"
        "All assistant messages have weight 0. There is no train/valid split, recipe integration or automatic approval. "
        "`meta.proposed_target_message_index` identifies the one Teacher action for future review; `statistic.json` "
        "measures its hypothetical labels with the existing `sft.py` helper without activating them. Student failures, "
        "Teacher prelude, summaries and synthetic finish callbacks are not positive targets.\n\n"
        "Both candidates share one import-typo template family and must remain in the same split. "
        "They passed public compiler/behavior checks, but neither freshly read its target file; manual review remains necessary. "
        "Do not call these examples offset-correction demonstrations or evidence of generalized debugging skill.\n\n"
        "Use a weight-aware training path after explicit label review. `sft.py` with packing=False ignores per-message weights; "
        "default text SFT can also truncate these >40k contexts. Do not train this review file directly. "
        "Full-context lengths and proposed target-token counts are in statistic.json.\n\n"
        "This folder contains internal JacCoder prompts and is intentionally local-only/gitignored. "
        "No Hugging Face/GitHub upload or training was performed. See manifest.json and disposition.json for provenance.\n")
    assert not (output / "train.jsonl").exists() and not (output / "valid.jsonl").exists()
    return statistic

# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--snapshot", type=Path, required=True)
    cli.add_argument("--audit", type=Path, required=True)
    cli.add_argument("--index", type=Path, required=True)
    cli.add_argument("--tokenizer", type=Path, required=True)
    cli.add_argument("--out-dir", type=Path, default=OUT_DIR)
    cli.add_argument("--max-token", type=int, default=MAX_TOKENS)
    args = cli.parse_args()
    result = export(args.snapshot, args.audit, args.index, args.tokenizer, args.out_dir, args.max_token)
    print(json.dumps({k: v for k, v in result.items() if k != "validation"}, indent=2))
