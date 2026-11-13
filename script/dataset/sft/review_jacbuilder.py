"""Review exactly two known JacBuilder import edits; replay in isolation before publishing edit-only labels."""

import argparse, ast, copy, csv, dataclasses, hashlib, json, shutil, sys, tempfile
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli
from dataset.sft.jacbuilder import read_json, sha256, sft_helpers

# Setting =================================================
REPO = Path(__file__).resolve().parents[3]
KNOWN_EDITS = {
    "batch-g5naf08b/04_dotted_module_typo": ("import from mathbox.opz { increment }", "import from mathbox.ops { increment }"),
    "batch-7sibgw5_/01_import_typo": ("import from helpers_typo { increment }", "import from helpers { increment }"),
}
MAX_TOKENS = 65536

# Functions ===============================================
def fixture(snapshot: Path, episode: str) -> tuple[dict, str, str]:
    batch, case = episode.split("/")
    file = snapshot / "docs/experiments/data_collection_pilot" / batch / "executed_fixtures.py"
    nodes = ast.parse(file.read_text()).body
    pin = next(ast.literal_eval(n.value) for n in nodes if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PIN" for t in n.targets))
    cases = next(n.value.elts for n in nodes if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CASES" for t in n.targets))
    row = next(n for n in cases if ast.literal_eval(n.args[0]) == case)
    return ast.literal_eval(row.args[3]), pin, ast.literal_eval(row.args[5])


def replay(row: dict, snapshot: Path, logs: Path, ordinal: int) -> dict:
    episode = row["meta"]["episode"]
    if episode not in KNOWN_EDITS:
        raise ValueError("This review does not approve unknown episodes")
    target = row["messages"][-1]["tool_calls"][0]["function"]
    args = json.loads(target["arguments"])
    old, new = KNOWN_EDITS[episode]
    if target["name"] != "edit_code" or args["old_string"] != old or args["new_string"] != new or args["replace_all"]:
        raise ValueError("Target differs from the specific edit reviewed")
    batch, case = episode.split("/")
    folder = snapshot / "docs/experiments/data_collection_pilot" / episode
    archived = next((folder / "episodes").iterdir())
    expected_files = {item["path"]: item["sha256"] for item in read_json(snapshot / "MANIFEST.json")["files"]}
    for path in folder.rglob("*"):
        if path.is_file() and expected_files.get(str(path.relative_to(snapshot))) != sha256(path):
            raise ValueError("Raw episode differs from the immutable snapshot")
    if sha256(archived / "trajectory.jsonl") != row["meta"]["origin_sha256"]:
        raise ValueError("Raw journal identity differs from exported evidence")
    events = [json.loads(line) for line in (archived / "trajectory.jsonl").read_text().splitlines()]
    original = next(e["data"]["content"] for e in events if e["kind"] == "teacher_before_write" and e["data"]["path"] == args["file_path"])
    golden, pin, task = fixture(snapshot, episode)
    request = read_json(snapshot / row["meta"]["request_file"])
    if old not in json.dumps(request["messages"], ensure_ascii=False):
        raise ValueError("Replacement text is not grounded in the captured request")
    if original.count(old) != 1:
        raise ValueError("Edit is ambiguous")
    patched = original.replace(old, new, 1)
    if patched != (archived / "broken.jac").read_text() or patched != golden["broken.jac"]:
        raise ValueError("Replay differs from archived verified repair/reference")
    module = new.split("import from ", 1)[1].split(" {", 1)[0]
    module_file = module.replace(".", "/") + ".jac"
    if not (archived / module_file).is_file():
        raise ValueError("Correct import does not refer to an existing module")
    workspace = Path(tempfile.mkdtemp(prefix="jacbuilder-edit-review-"))
    files = {}
    for file in archived.rglob("*"):
        relative = file.relative_to(archived)
        if file.is_file() and not any(p.startswith(".") for p in relative.parts) and file.name != "trajectory.jsonl":
            files[str(relative)] = file.read_text()
    for name, content in files.items():
        destination = workspace / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
    (workspace / "jac.toml").write_text(pin)
    (workspace / "broken.jac").write_text(original)
    verifier_sha = sha256(workspace / "verify.jac")
    results = []
    def execute(stage: str, command: list[str]) -> jac_cli.JacResult:
        environment = {"JAC_DATA_PATH": str(workspace / "graph"), "DO_NOT_TRACK": "1"}
        result = jac_cli.execute(command, cwd=workspace, env=environment, timeout=45)
        results.append({"stage": stage, "command": [jac_cli.JAC, *command], "cwd": str(workspace), **dataclasses.asdict(result)})
        (logs / f"replay-{ordinal}.json").write_text(json.dumps({"episode": episode, "checks": results}, indent=2))
        if result.timed_out or result.launch_error or result.mem_capped:
            raise RuntimeError("Isolated verification was blocked by infrastructure")
        return result
    baseline = execute("baseline", ["run", "verify.jac"])
    if baseline.returncode != 1:
        raise ValueError("Original fixture no longer reproduces the failing import")
    (workspace / "broken.jac").write_text(patched)
    compiler = execute("repaired", ["check", "broken.jac"])
    behavior = execute("repaired", ["run", "verify.jac"])
    (workspace / "review_checks.jac").write_text("import from broken { compute }\nwith entry { for x in [-999, -17, -1, 0, 1, 17, 999] { assert compute(x) == x + 1; } }\n")
    extra = execute("additional_inputs", ["run", "review_checks.jac"])
    if any(r.returncode != 0 for r in [compiler, behavior, extra]):
        raise ValueError("Repair failed independent review checks")
    if sha256(workspace / "verify.jac") != verifier_sha:
        raise ValueError("Verifier changed during replay")
    changed = [name for name, content in files.items() if name not in {"broken.jac", "jac.toml"} and (workspace / name).read_text() != content]
    if changed:
        raise ValueError("Unexpected mutation outside the repair")
    return {"id": row["meta"]["id"], "episode": episode, "reviewer": "Codex agent", "decision": "approve_edit_only",
            "task": task, "old_string": old, "new_string": new, "module_exists": module_file,
            "grounding": "Exact old import appears in captured compiler/context evidence; module file exists",
            "minimal_change": "One unique import replacement; helper, interface and verifier unchanged",
            "workspace": str(workspace), "check_log": f"agent-review/replay-{ordinal}.json",
            "baseline_exit_code": baseline.returncode, "post_check_exit_codes": [r.returncode for r in [compiler, behavior, extra]],
            "scope": "Correctness of this exact edit, not endorsement of the entire Teacher process",
            "limitations": ["Teacher did not freshly read edited target", "Public synthetic fixture, no hidden task tests", "One import-typo family, no offset-correction target", "Internal prompts/temporary paths retained; local-only", "Not evidence of FT/general debugging improvement"]}


def review(folder: Path, binary: Path) -> dict:
    from transformers import AutoTokenizer
    from datasets import load_dataset
    if (folder / "train.jsonl").exists() or (folder / "agent-review").exists():
        raise FileExistsError("Refusing to replace an existing review or train split")
    manifest = read_json(folder / "manifest.json")
    review_hash = sha256(folder / "review.jsonl")
    if review_hash != manifest["review_sha256"]:
        raise ValueError("Review source was modified")
    rows = [json.loads(line) for line in (folder / "review.jsonl").read_text().splitlines()]
    if len(rows) != 2 or {r["meta"]["episode"] for r in rows} != set(KNOWN_EDITS):
        raise ValueError("Only the two specifically inspected edits can be reviewed here")
    logs = folder / "agent-review"
    logs.mkdir()
    for name in ["README.md", "statistic.json", "validation.json"]:
        shutil.copy2(folder / name, logs / ("before-" + name))
    jac_cli.JAC = str(binary)
    version = jac_cli.execute(["--version"])
    if not version.ok or "jac 0.34.28 " not in version.stdout:
        raise ValueError("Pinned Jac 0.34.28 is required; no installation attempted")
    decisions = [replay(row, Path(manifest["snapshot"]), logs, i) for i, row in enumerate(rows)]
    tokenizer = AutoTokenizer.from_pretrained(manifest["tokenizer"], local_files_only=True)
    helpers = sft_helpers(REPO)
    train, validations, frequencies = [], [], Counter()
    for row, decision in zip(rows, decisions):
        approved = copy.deepcopy(row)
        i = row["meta"]["proposed_target_message_index"]
        if i != len(row["messages"]) - 1:
            raise ValueError("Only the final Teacher action may receive loss")
        approved["messages"][i]["weight"] = 1
        approved["messages"][i].pop("masked", None)
        approved["meta"].update(review_status="approved_edit_only", training_approved=True,
                                 reviewed_by="Codex agent", training_use="limited_minimal_import_repair_smoke",
                                 review_decision_file="agent-review/decisions.json")
        original_messages, tools = helpers["chat_inputs"](row)
        messages, _ = helpers["chat_inputs"](approved)
        actual = helpers["tokenize_with_assistant_mask"](messages, tools, tokenizer, MAX_TOKENS)
        expected_messages = copy.deepcopy(original_messages)
        expected_messages[i]["weight"] = 1
        expected = helpers["tokenize_with_assistant_mask"](expected_messages, tools, tokenizer, MAX_TOKENS)
        if actual != expected:
            raise ValueError("Labels differ from the one reviewed Teacher action")
        if any(m.get("weight", 1) != 0 for j, m in enumerate(messages) if m["role"] == "assistant" and j != i):
            raise ValueError("Historical assistant behavior would be trained")
        text = tokenizer.apply_chat_template(messages, tools=tools, tokenize=False, add_generation_prompt=False)
        length = len(tokenizer(text, add_special_tokens=False)["input_ids"])
        if length > MAX_TOKENS or len(actual["input_ids"]) != length:
            raise ValueError("Full-context training would truncate")
        tokens = [label for label in actual["labels"] if label != -100]
        if len(tokens) != row["meta"]["proposed_target_tokens"]:
            raise ValueError("Target token count changed from reviewed export")
        frequencies.update(tokens)
        validations.append({"id": row["meta"]["id"], "rendered_tokens": length, "active_target_tokens": len(tokens),
                            "truncated": False, "only_final_teacher_edit_labelled": True})
        train.append(approved)
    scratch = logs / "candidate-train.jsonl"
    scratch.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in train))
    with tempfile.TemporaryDirectory(prefix="jacbuilder-reviewed-arrow-") as cache:
        loaded = load_dataset("json", data_files=str(scratch), split="train", cache_dir=cache)
        if len(loaded) != 2:
            raise ValueError("Arrow could not read the train split")
        for row in loaded:
            messages, tools = helpers["chat_inputs"](row)
            encoded = helpers["tokenize_with_assistant_mask"](messages, tools, tokenizer, MAX_TOKENS)
            if sum(x != -100 for x in encoded["labels"]) != row["meta"]["proposed_target_tokens"]:
                raise ValueError("Arrow round trip changed active labels")
    if sha256(folder / "review.jsonl") != review_hash:
        raise ValueError("Original review data changed")
    for row in rows:
        if sha256(Path(manifest["snapshot"]) / row["meta"]["origin_file"]) != row["meta"]["origin_sha256"]:
            raise ValueError("Raw journal changed during review")
    (logs / "decisions.json").write_text(json.dumps(decisions, indent=2))
    scratch.replace(folder / "train.jsonl")
    with (folder / "target_token_frequencies.csv").open("w", newline="") as output:
        writer = csv.writer(output);writer.writerow(["token_id", "token", "count", "share"])
        total = sum(frequencies.values())
        for token_id, count in frequencies.most_common():
            writer.writerow([token_id, tokenizer.convert_ids_to_tokens(token_id), count, count / total])
    stats = read_json(folder / "statistic.json")
    stats.update(status="approved_edit_only", records={"review": 2, "train": 2, "valid": 0},
                 active_target_tokens=total, validation=validations,
                 no_heldout_split_reason="Both near-identical edits belong to one template family; no random train/valid leakage")
    (folder / "statistic.json").write_text(json.dumps(stats, indent=2) + "\n")
    train_manifest = {"review_source_sha256": review_hash, "train_sha256": sha256(folder / "train.jsonl"),
                      "reviewer_source_sha256": sha256(Path(__file__)), "decisions_sha256": sha256(logs / "decisions.json"),
                      "jac_binary": str(binary), "jac_version": version.stdout.strip(), "active_target_tokens": total,
                      "raw_and_review_data_unchanged": True, "training_started": False, "local_only": True,
                      "requirements": {"weight_aware_mask": True, "text_sft_packing": True, "max_seq_length_minimum": max(v["rendered_tokens"] for v in validations)}}
    (folder / "train_manifest.json").write_text(json.dumps(train_manifest, indent=2) + "\n")
    (folder / "README.md").write_text(
        "# JacBuilder debug pilot v1 — two reviewed edit targets\n\n"
        "`train.jsonl` contains two Codex-reviewed, independently replayed minimal import fixes. Only the final Teacher edit "
        "has weight 1; all Student failures and other historical assistant messages remain weight 0. "
        "`review.jsonl` is the unchanged original pending-review export, retained as evidence. Do not mix both files for training.\n\n"
        "Each original bad import failed in a fresh Jac 0.34.28 server workspace; replayed exact edits then passed compiler, "
        "original verifier, and additional compute(x)==x+1 checks for [-999,-17,-1,0,1,17,999]. "
        "The helper and verifier were unchanged. Decisions and complete commands/results are in agent-review/.\n\n"
        "Approval is limited to these edits, not the Teacher's whole trajectory: neither Teacher freshly read the edited target. "
        "Both examples are the same import-typo family and stay in train together; no independent valid split is claimed. "
        "They are not demonstrations of correcting read offsets or evidence of generalized debugging improvement.\n\n"
        "There are 82,229 rendered sequence tokens and 217 active target tokens (108+109), including template markers. "
        "Contexts are 41,007 and 41,222 tokens. Use a weight-aware path such as text sft.py with packing=True and sufficient "
        "max_seq_length (65536 tested). packing=False ignores message weights and is unsafe for these rows. No truncation, "
        "summarization or arbitrary tool-call deletion was applied. No training recipe was enabled and no FT was started.\n\n"
        "This data includes internal prompts and contextual temporary paths and remains local-only/gitignored. "
        "See train_manifest.json, statistic.json and target_token_frequencies.csv. Prior review artifacts are in agent-review/.\n")
    return {"reviewed": len(decisions), "approved_edit_targets": len(train), "active_target_tokens": total,
            "review_source_unchanged": sha256(folder / "review.jsonl") == review_hash,
            "train_file": str(folder / "train.jsonl"), "training_started": False}

# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--dataset", type=Path, required=True)
    cli.add_argument("--jac", type=Path, required=True)
    args = cli.parse_args()
    print(json.dumps(review(args.dataset, args.jac), indent=2))
