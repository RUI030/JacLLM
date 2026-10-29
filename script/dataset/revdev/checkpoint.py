"""Snapshot and restore a JacCoder workspace only at a completed tool boundary."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


# Setting =================================================
EXCLUDE_DIRS = {".git", ".jac", ".pytest_cache", "node_modules", "__pycache__"}
PLAN_PATH = ".jaccoder/build_plan.json"


# Functions ===============================================
def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def workspace_files(root: Path) -> list[dict]:
    """Hash source and plan files; generated caches are rebuilt on restore."""
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in EXCLUDE_DIRS for part in path.relative_to(root).parts):
            continue
        rel = path.relative_to(root).as_posix()
        files.append({"path": rel, "sha256": digest(path.read_bytes()), "size": path.stat().st_size})
    return files


def tree_digest(files: list[dict]) -> str:
    return digest("\n".join(f'{f["path"]}:{f["sha256"]}' for f in files).encode())


def plan_state(root: Path) -> tuple[str | None, list[dict]]:
    plan_file = root / PLAN_PATH
    if not plan_file.is_file():
        return None, [{"issue": "plan_missing", "path": PLAN_PATH}]
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    issues = []
    for row in plan.get("files", []):
        rel = row.get("path", "")
        if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            issues.append({"issue": "unsafe_plan_path", "path": rel})
        elif row.get("status") == "done" and not (root / rel).is_file():
            issues.append({"issue": "done_file_missing", "path": rel})
    return digest(plan_file.read_bytes()), issues


def save(workspace: Path, destination: Path, *, run_id: str, after_event_id: str,
         segment_index: int, reference_id: str, harness_schema_hash: str,
         environment_fingerprint: dict, completed_work: list[str],
         remaining_work: list[str]) -> dict:
    """Copy a finished workspace and record hashes; never infer implementation from plan status."""
    workspace = workspace.resolve()
    destination = destination.resolve()
    if not workspace.is_dir() or destination == workspace or workspace in destination.parents:
        raise ValueError("Checkpoint destination must be outside the workspace")
    if destination.exists():
        raise FileExistsError(destination)
    plan_hash, issues = plan_state(workspace)
    if issues:
        raise ValueError(f"Cannot checkpoint inconsistent plan: {issues}")
    plan = json.loads((workspace / PLAN_PATH).read_text(encoding="utf-8"))
    scaffold_only = [row["path"] for row in plan.get("files", [])
                     if row.get("status") == "done" and row["path"].endswith(".jac")
                     and "NotImplementedError" in (workspace / row["path"]).read_text(encoding="utf-8")]
    files = workspace_files(workspace)
    tree_hash = tree_digest(files)
    checkpoint_id = digest(f"{run_id}:{after_event_id}:{tree_hash}".encode())[:16]
    snapshot = destination / "workspace"
    shutil.copytree(workspace, snapshot, ignore=shutil.ignore_patterns(*EXCLUDE_DIRS))
    if workspace_files(snapshot) != files:
        shutil.rmtree(destination)
        raise RuntimeError("Checkpoint copy hash mismatch")
    metadata = {
        "schema_version": "1", "checkpoint_id": checkpoint_id, "run_id": run_id,
        "after_event_id": after_event_id, "segment_index": segment_index,
        "workspace_snapshot": "workspace", "workspace_tree_sha256": tree_hash,
        "files": files, "plan_path": PLAN_PATH, "plan_sha256": plan_hash,
        "plan_consistency": {
            "state": "scaffold_only" if scaffold_only else "file_presence_passed",
            "implementation_state": "unverified",
            "issues": [{"issue": "done_file_has_stub", "path": path} for path in scaffold_only],
        },
        "completed_work": completed_work, "remaining_work": remaining_work,
        "environment_fingerprint": environment_fingerprint,
        "harness_schema_hash": harness_schema_hash, "reference_id": reference_id,
        "excluded_generated_dirs": sorted(EXCLUDE_DIRS),
    }
    (destination / "checkpoint.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def restore(checkpoint: Path, destination: Path) -> dict:
    """Restore into an absent path, refusing a changed or incomplete snapshot."""
    checkpoint = checkpoint.resolve()
    destination = destination.resolve()
    metadata = json.loads((checkpoint / "checkpoint.json").read_text(encoding="utf-8"))
    source = checkpoint / metadata["workspace_snapshot"]
    files = workspace_files(source)
    if files != metadata["files"] or tree_digest(files) != metadata["workspace_tree_sha256"]:
        raise ValueError("Checkpoint files do not match metadata")
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copytree(source, destination)
    if workspace_files(destination) != files:
        shutil.rmtree(destination)
        raise RuntimeError("Restored workspace hash mismatch")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    make = sub.add_parser("save")
    make.add_argument("workspace", type=Path)
    make.add_argument("destination", type=Path)
    make.add_argument("--run-id", required=True)
    make.add_argument("--after-event-id", required=True)
    make.add_argument("--segment-index", type=int, default=0)
    make.add_argument("--reference-id", required=True)
    make.add_argument("--harness-schema-hash", required=True)
    make.add_argument("--environment-json", type=Path, required=True)
    make.add_argument("--completed", action="append", default=[])
    make.add_argument("--remaining", action="append", default=[])
    recover = sub.add_parser("restore")
    recover.add_argument("checkpoint", type=Path)
    recover.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.action == "save":
        result = save(args.workspace, args.destination, run_id=args.run_id,
                      after_event_id=args.after_event_id, segment_index=args.segment_index,
                      reference_id=args.reference_id, harness_schema_hash=args.harness_schema_hash,
                      environment_fingerprint=json.loads(args.environment_json.read_text()),
                      completed_work=args.completed, remaining_work=args.remaining)
    else:
        result = restore(args.checkpoint, args.destination)
    print(json.dumps({"checkpoint_id": result["checkpoint_id"], "tree_sha256": result["workspace_tree_sha256"]}))


# Run =====================================================
if __name__ == "__main__":
    main()
