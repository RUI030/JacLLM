"""Independently check the reviewed JacBuilder SFT projection against its source."""

import argparse
import ast
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from dataset.sft.jacbuilder import read_json, sft_helpers, sha256
from dataset.sft.project_jacbuilder import PROJECTION_VERSION, digest, handoff_parts

# Setting =================================================
REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / "dataset/sft/jacbuilder/debug-pilot-v1"
PROJECTED = REPO / "dataset/sft/jacbuilder/debug-pilot-v2-projected"
TOKENIZER = REPO / "output/model/JacLLM-Ornith-9B-prod-img-sft-m7"

# Functions ===============================================
def check(source_dir: Path, projected_dir: Path, tokenizer_path: Path) -> dict:
    from transformers import AutoTokenizer
    manifest = read_json(projected_dir / "projection_manifest.json")
    source_manifest = read_json(source_dir / "train_manifest.json")
    if manifest["version"] != PROJECTION_VERSION:
        raise ValueError("Unexpected projection version")
    if not (sha256(source_dir / "train.jsonl") == source_manifest["train_sha256"] == manifest["source_train_sha256"]):
        raise ValueError("Source train hash changed")
    if sha256(projected_dir / "train.jsonl") != manifest["projected_train_sha256"]:
        raise ValueError("Projected train hash changed")
    source = [json.loads(line) for line in (source_dir / "train.jsonl").read_text().splitlines()]
    projected = [json.loads(line) for line in (projected_dir / "train.jsonl").read_text().splitlines()]
    proofs = manifest["proofs"]
    if not len(source) == len(projected) == len(proofs) == len(manifest["measurements"]):
        raise ValueError("Source/projected/proof row counts differ")
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path), local_files_only=True)
    helpers = sft_helpers(REPO)
    rows = []
    for original, derived, proof, recorded in zip(source, projected, proofs, manifest["measurements"]):
        if not original["meta"]["id"] == derived["meta"]["id"] == proof["id"] == recorded["id"]:
            raise ValueError("Row identities differ")
        canonical = json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if not (digest(canonical) == proof["source_row_sha256"] == derived["meta"]["source_row_sha256"]):
            raise ValueError("Source row fingerprint differs")
        index = proof["handoff_index"]
        if derived["messages"][:index] != original["messages"][:index] or derived["messages"][index + 1:] != original["messages"][index + 1:]:
            raise ValueError("Non-handoff messages changed")
        if derived["tools"] != original["tools"]:
            raise ValueError("Tool schemas changed")
        old_handoff = original["messages"][index]["content"]
        if digest(old_handoff) != proof["source_handoff_sha256"]:
            raise ValueError("Original handoff fingerprint differs")
        _, _, _, old_payload, _ = handoff_parts(old_handoff)
        old_student = old_payload["live_snapshot"][0]["content"]
        teacher = original["messages"][0]["content"]
        restored = "".join(part["text"] if part["kind"] == "student_only" else
                           teacher[part["start"]:part["end"]] for part in proof["segments"])
        if restored != old_student or digest(restored) != proof["student_system_sha256"]:
            raise ValueError("Student system cannot be reconstructed from exact shared lines")
        for part in proof["segments"]:
            if part["kind"] == "teacher_system_ref" and digest(teacher[part["start"]:part["end"]]) != part["sha256"]:
                raise ValueError("Teacher system reference changed")
        _, _, _, new_payload, _ = handoff_parts_projected(derived["messages"][index]["content"])
        expected_payload = json.loads(json.dumps(old_payload))
        expected_payload["live_snapshot"][0]["content"] = (
            "Student-only system instructions; exact shared lines are already in the Teacher system:\n"
            + "".join(part["text"] for part in proof["segments"] if part["kind"] == "student_only"))
        expected_payload["system_projection_version"] = PROJECTION_VERSION
        if new_payload != expected_payload:
            raise ValueError("Student history or observations changed")
        old_messages, old_tools = helpers["chat_inputs"](original)
        new_messages, new_tools = helpers["chat_inputs"](derived)
        if old_tools != new_tools:
            raise ValueError("Tool schemas changed after SFT serialization")
        old_encoded = helpers["tokenize_with_assistant_mask"](old_messages, old_tools, tokenizer, 65536)
        new_encoded = helpers["tokenize_with_assistant_mask"](new_messages, new_tools, tokenizer, 65536)
        old_targets = [v for v in old_encoded["labels"] if v != -100]
        new_targets = [v for v in new_encoded["labels"] if v != -100]
        if not old_targets or old_targets != new_targets:
            raise ValueError("Approved target token IDs changed")
        if len(old_encoded["input_ids"]) != recorded["original_tokens"] or len(new_encoded["input_ids"]) != recorded["projected_tokens"]:
            raise ValueError("Recorded token counts differ")
        rows.append({"id": proof["id"], "original_tokens": len(old_encoded["input_ids"]),
                     "projected_tokens": len(new_encoded["input_ids"]), "active_target_tokens": len(new_targets),
                     "snapshot_reconstructed": True, "target_token_ids_identical": True})
    return {"status": "PASS", "rows": rows, "source_train_sha256": manifest["source_train_sha256"],
            "projected_train_sha256": manifest["projected_train_sha256"], "training_started": False}


def handoff_parts_projected(content: str) -> tuple[str, tuple[str, str], str, dict, str]:
    before, marker, after = content.partition("message = ")
    if not marker:
        raise ValueError("Projected handoff has no message assignment")
    assignment, newline, tail = after.partition("\n")
    if not newline:
        raise ValueError("Projected handoff has no suffix")
    value = ast.literal_eval(assignment)
    body = value[0]
    start = body.index("{", body.index("The following projected Student context"))
    payload, length = json.JSONDecoder().raw_decode(body[start:])
    if start + length != len(body):
        raise ValueError("Projected handoff has unexpected suffix")
    return before, value, body[:start], payload, tail

# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--source", type=Path, default=SOURCE)
    cli.add_argument("--projected", type=Path, default=PROJECTED)
    cli.add_argument("--tokenizer", type=Path, default=TOKENIZER)
    args = cli.parse_args()
    result = check(args.source, args.projected, args.tokenizer)
    (args.projected / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
