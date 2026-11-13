"""Replay three live Teacher repairs as candidate evidence, without SFT approval."""

import argparse
import dataclasses
import hashlib
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli

# Setting =================================================
REPO = Path(__file__).resolve().parents[3]
SNAPSHOT = Path("/home/ryl/Documents/Jaseci/jacbuilder-experiment-data/snapshot-2026-10-30-cg_kmqym")
PILOT = "docs/experiments/teacher_model_pilot/run-enupzv9w/episodes"
OUT = REPO / "dataset/sft/jacbuilder/live-teacher-candidate-audit-v1"
PINNED_JAC = Path("/home/ryl/.jacbin_pinned/jac")
EXTRA = {
    "off_by_one": "import from broken { increment }\nwith entry { for x in [-999, -17, -1, 0, 1, 17, 999] { assert increment(x) == x + 1; } }\n",
    "positive_filter": "import from broken { positives }\nwith entry { assert positives([-9, 0, 4, -1, 4, 0, 2]) == [4, 4, 2]; assert positives([0, 0]) == []; assert positives([]) == []; }\n",
    "walker_accumulation": "import from broken { Item, Sum }\nwith entry { a = Item(value=7); b = Item(value=-2); c = Item(value=0); root ++> a; root ++> b; root ++> c; w = root spawn Sum(); assert w.total == 5; }\n",
}

# Functions ===============================================
def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(snapshot: Path, entry: dict, expected: dict) -> dict:
    from utils.jac_cli import jac_workspace
    name = entry["case"]
    if name not in EXTRA or entry.get("student_kind") != "scripted_failure_fixture":
        raise ValueError("Only the three known scripted-Student cases are supported")
    folder = snapshot / PILOT / Path(entry["workspace"]).name
    journal = folder / "trajectory.jsonl"
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    edits = [e for e in events if e["actor"] == "teacher" and e["kind"] == "teacher_model_transport"
             and e["data"].get("action", {}).get("tool") == "edit_code"]
    reads = [e for e in events if e["actor"] == "teacher" and e["kind"] == "teacher_model_transport"
             and e["data"].get("action", {}).get("tool") == "read_file"]
    if len(edits) != 1 or len(reads) != 1 or reads[0]["sequence"] >= edits[0]["sequence"]:
        raise ValueError("Expected one Teacher read before one edit")
    action = edits[0]["data"]["action"]
    if action != entry["teacher_actions"][1] or action["arguments"].get("replace_all") is not False:
        raise ValueError("Archived edit differs from pilot summary")
    old, new = action["arguments"]["old_string"], action["arguments"]["new_string"]
    final = (folder / "broken.jac").read_text()
    if final != entry["final_source"] or final.count(new) != 1:
        raise ValueError("Final source differs or reverse edit is ambiguous")
    original = final.replace(new, old, 1)
    if original.count(old) != 1 or original.replace(old, new, 1) != final:
        raise ValueError("Original source cannot be reconstructed exactly")
    if not entry["pipeline_ok"] or entry["baseline"]["ok"] or not entry["verification"]["ok"]:
        raise ValueError("Pilot did not record a verified recovery")
    checks = []
    with jac_workspace({"broken.jac": original, "verify.jac": (folder / "verify.jac").read_text(),
                        "extra_checks.jac": EXTRA[name], "jac.toml": (folder / "jac.toml").read_text()}) as workspace:
        def execute(stage: str, args: list[str]) -> int:
            result = jac_cli.execute(args, timeout=50, cwd=workspace,
                                     env={"JAC_DATA_PATH": str(workspace / ("graph-" + stage)),
                                          "DO_NOT_TRACK": "1"})
            checks.append({"stage": stage, "command": [jac_cli.JAC, *args], **dataclasses.asdict(result)})
            if result.timed_out or result.mem_capped or result.launch_error or result.infra_error:
                raise RuntimeError("Pinned Jac verification infrastructure failed")
            return result.returncode
        baseline_check = execute("baseline_check", ["check", "broken.jac"])
        baseline_run = execute("baseline_run", ["run", "verify.jac"])
        (workspace / "broken.jac").write_text(final)
        repaired_check = execute("repaired_check", ["check", "broken.jac"])
        repaired_run = execute("repaired_run", ["run", "verify.jac"])
        extra = execute("additional_inputs", ["run", "extra_checks.jac"])
    passed = baseline_check == 0 and baseline_run == 1 and repaired_check == repaired_run == extra == 0
    return {"case": name, "category": name, "status": "PASS" if passed else "FAIL",
            "student_kind": "scripted_failure_fixture", "teacher_model": entry["teacher_model"],
            "teacher_read_before_edit": True, "teacher_edit_sequence": edits[0]["sequence"],
            "journal_sha256": sha(journal), "original_source_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "final_source_sha256": sha(folder / "broken.jac"), "additional_check": EXTRA[name],
            "checks": checks, "sft_approved": False,
            "student_context_note": "Student failures were scripted; Teacher read source before editing. Student-compatible target/context requires separate review."}


def audit(snapshot: Path, out: Path) -> dict:
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite {out}")
    manifest = json.loads((snapshot / "MANIFEST.json").read_text())
    expected = {e["path"]: e["sha256"] for e in manifest["files"]}
    base = snapshot / PILOT
    for path in base.rglob("*"):
        if path.is_file() and expected.get(str(path.relative_to(snapshot))) != sha(path):
            raise ValueError("Pilot source differs from immutable snapshot manifest")
    jac_cli.JAC = str(PINNED_JAC)
    version = jac_cli.execute(["--version"], timeout=30)
    if not version.ok or "jac 0.34.28 " not in version.stdout:
        raise RuntimeError("Pinned Jac 0.34.28 unavailable")
    source = base / "pilot_results.json"
    entries = json.loads(source.read_text())
    if {e["case"] for e in entries} != set(EXTRA):
        raise ValueError("Pilot cases differ from the reviewed set")
    results = [run_case(snapshot, entry, expected) for entry in entries]
    out.mkdir(parents=True)
    report = {"status": "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL",
              "jac_version": version.stdout.strip(), "pilot_results_sha256": sha(source),
              "snapshot_manifest_sha256": sha(snapshot / "MANIFEST.json"),
              "cases": results, "sft_approved": False, "training_started": False}
    (out / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    return report

# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    cli.add_argument("--out-dir", type=Path, default=OUT)
    args = cli.parse_args()
    result = audit(args.snapshot, args.out_dir)
    print(json.dumps({"status": result["status"], "cases": [
        {"case": r["case"], "status": r["status"], "exit_codes": [c["returncode"] for c in r["checks"]]}
        for r in result["cases"]]}, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
