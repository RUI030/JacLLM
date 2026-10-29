"""Prepare a Claude replacement system prompt from an observed JacCoder request."""

import argparse
import hashlib
import json
from pathlib import Path


# Setting =================================================
INSTRUCTION = Path(__file__).with_name("teacher_instruction.txt")


# Functions ===============================================
def prepare(capture_path: Path, request_index: int, destination: Path) -> dict:
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    request = capture["requests"][request_index]
    system = [m["content"] for m in request["messages"] if m["role"] == "system"]
    if not system or any(not isinstance(s, str) for s in system):
        raise ValueError("Expected observed string system messages")
    base = "\n\n".join(system)
    if "# JacCoder:" not in base:
        raise ValueError("Selected request is not a JacCoder system prompt")
    teacher = INSTRUCTION.read_text(encoding="utf-8")
    destination.mkdir(parents=True, exist_ok=False)
    combined = base + "\n\n" + teacher
    (destination / "system.txt").write_text(combined, encoding="utf-8")
    (destination / "tools.json").write_text(json.dumps(request["tools"], indent=2) + "\n", encoding="utf-8")
    metadata = {
        "capture": str(capture_path.resolve()), "request_index": request_index,
        "base_sha256": hashlib.sha256(base.encode()).hexdigest(),
        "teacher_sha256": hashlib.sha256(teacher.encode()).hexdigest(),
        "system_sha256": hashlib.sha256(combined.encode()).hexdigest(),
        "tool_count": len(request["tools"]),
        "execution_status": "prepared_not_executed",
        "note": "Replacing the prompt does not register JacCoder tools in Claude Code. tools.json requires an execution adapter.",
    }
    (destination / "provenance.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--request-index", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.capture, args.request_index, args.out), indent=2))


# Run =====================================================
if __name__ == "__main__":
    main()
