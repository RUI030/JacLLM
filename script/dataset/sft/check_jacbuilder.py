"""CPU-only plain-assert checks for the JacBuilder review export; no model loading."""

import argparse, collections, copy, csv, json, sys, tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from jacbuilder import canonical_messages, read_json, sft_helpers, validate_record

# Functions ===============================================
def check_primitives() -> None:
    original = [{"role": "user", "content": [{"type": "text", "text": "Exact\\nsource\ntext"}]},
                {"role": "assistant", "content": "Student failure"}]
    saved = copy.deepcopy(original)
    messages, indices = canonical_messages(original)
    assert original == saved
    assert indices == [0] and messages[0]["content"] == original[0]["content"][0]["text"]
    assert messages[1]["weight"] == 0
    for content in [[{"type": "image", "image": "private.png"}], [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]]:
        refused = False
        try:
            canonical_messages([{"role": "user", "content": content}])
        except ValueError:
            refused = True
        assert refused


def check_export(folder: Path, tokenizer_path: Path) -> dict:
    from datasets import load_dataset
    from transformers import AutoTokenizer
    check_primitives()
    rows = [json.loads(line) for line in (folder / "review.jsonl").read_text().splitlines()]
    assert len(rows) == 2
    assert not (folder / "valid.jsonl").exists()
    assert len({r["meta"]["split_group"] for r in rows}) == 1
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path), local_files_only=True)
    helpers = sft_helpers(Path(__file__).resolve().parents[3])
    frequencies = collections.Counter()
    with tempfile.TemporaryDirectory(prefix="jacbuilder-arrow-") as cache:
        ds = load_dataset("json", data_files={"review": str(folder / "review.jsonl")}, split="review", cache_dir=cache)
        assert len(ds) == len(rows)
        for row in ds:
            assert isinstance(row["tools"], str) and isinstance(json.loads(row["tools"]), list)
            assert row["meta"]["training_approved"] is False
            messages, tools = helpers["chat_inputs"](row)
            assert all(m["weight"] == 0 for m in messages if m["role"] == "assistant")
            actual = helpers["tokenize_with_assistant_mask"](messages, tools, tokenizer, 65536)
            assert actual["labels"] and all(v == -100 for v in actual["labels"])
            check, ids = validate_record(row, tokenizer, helpers, 65536)
            assert check["proposed_teacher_target_tokens"] > 0
            frequencies.update(ids)
            refused = False
            try:
                validate_record(row, tokenizer, helpers, 16384)
            except ValueError as e:
                refused = "refusing to truncate" in str(e)
            assert refused
            # Exact request prefix can be reconstructed after the Arrow-friendly text-block conversion.
            source = Path(read_json(folder / "manifest.json")["snapshot"]) / row["meta"]["request_file"]
            request = read_json(source)
            restored = copy.deepcopy(rows[[r["meta"]["id"] for r in rows].index(row["meta"]["id"])]["messages"][:-1])
            for message in restored:
                message.pop("weight", None);message.pop("masked", None)
            for i in row["meta"]["reversible_text_block_indices"]:
                restored[i]["content"] = [{"type": "text", "text": restored[i]["content"]}]
            assert restored == request["messages"], "Context changed beyond reversible text blocks/mask metadata"
    approved_rows, active_tokens = 0, 0
    if (folder / "train.jsonl").exists():
        approved = [json.loads(line) for line in (folder / "train.jsonl").read_text().splitlines()]
        assert len(approved) == len(rows)
        source_rows = {r["meta"]["id"]: r for r in rows}
        for row in approved:
            source = source_rows[row["meta"]["id"]]
            assert row.get("tools") == source.get("tools"), "Approved tool schemas differ from review source"
            assert row["meta"]["training_approved"] is True and row["meta"]["review_status"] == "approved_edit_only"
            expected_messages = copy.deepcopy(source["messages"])
            target = source["meta"]["proposed_target_message_index"]
            expected_messages[target]["weight"] = 1
            expected_messages[target].pop("masked", None)
            assert row["messages"] == expected_messages
            messages, tools = helpers["chat_inputs"](row)
            expected, _ = helpers["chat_inputs"]({**source, "messages": expected_messages})
            actual_labels = helpers["tokenize_with_assistant_mask"](messages, tools, tokenizer, 65536)
            expected_labels = helpers["tokenize_with_assistant_mask"](expected, tools, tokenizer, 65536)
            assert actual_labels == expected_labels
            active = sum(v != -100 for v in actual_labels["labels"])
            assert active == source["meta"]["proposed_target_tokens"]
            active_tokens += active
            approved_rows += 1
        manifest = read_json(folder / "train_manifest.json")
        import hashlib
        assert hashlib.sha256((folder / "train.jsonl").read_bytes()).hexdigest() == manifest["train_sha256"]
        assert active_tokens == manifest["active_target_tokens"]
    with (folder / "proposed_target_token_frequencies.csv").open("w", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(["token_id", "token", "count", "share"])
        total = sum(frequencies.values())
        for token_id, count in frequencies.most_common():
            writer.writerow([token_id, tokenizer.convert_ids_to_tokens(token_id), count, count / total])
    return {"status": "PASS", "review_rows": len(rows), "train_rows": approved_rows, "active_target_tokens": active_tokens, "proposed_target_tokens": total, "checks": [
        "primitive conversion preserves originals", "unsupported multimodal/multiblock content refused",
        "HF Arrow JSON loader accepts both rows", "tools and arguments use existing SFT serialization",
        "all Student/history/Teacher review labels masked", "existing actual SFT mask helper executed",
        "hypothetical final Teacher action labels nonempty", "16k cap refuses whole-context truncation",
        "original request prefixes reconstructed exactly", "one split group and no fake validation split", "any approved train rows differ only in reviewed final-action weights and metadata"],
        "training_started": False, "model_loaded": False}

# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--dataset", type=Path, required=True)
    cli.add_argument("--tokenizer", type=Path, required=True)
    args = cli.parse_args()
    result = check_export(args.dataset, args.tokenizer)
    (args.dataset / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
