"""Verify generated files and independent acceptance checks before SFT export."""

import argparse, hashlib, json, shutil, sys, tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli
from dataset.revdev.checkpoint import workspace_files

# Functions ===============================================
def validate(run: Path, jac: Path) -> dict:
    metadata = json.loads((run / "run.json").read_text())
    workspace = Path(metadata["workspace"])
    evidence = []
    issues = []
    if metadata["status"] != "teacher_finished_unvalidated":
        issues.append("teacher_not_finished")
    plan = json.loads((workspace / ".jaccoder/build_plan.json").read_text())
    for row in plan["files"]:
        path = workspace / row["path"]
        if not path.is_file():
            issues.append("missing:" + row["path"])
        elif path.suffix == ".jac" and "NotImplementedError" in path.read_text():
            issues.append("stub:" + row["path"])
    verification = Path(tempfile.mkdtemp(prefix="revdev-acceptance-"))
    shutil.copytree(workspace, verification, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".jac", "node_modules", "__pycache__"))
    acceptance = Path(__file__).parent / "fixtures/mindcraft_acceptance.jac"
    shutil.copyfile(acceptance, verification / "revdev_acceptance.jac")
    for command in (["check", "main.jac"], ["test", "revdev_acceptance.jac"]):
        result = jac_cli.execute(command, jac=str(jac), cwd=verification, timeout=120,
                                 env={"JAC_TEST_NATIVE": "1", "JAC_TEST_JOBS": "0"})
        evidence.append({"command": command, **vars(result)})
        if not result.ok or result.timed_out:
            issues.append("failed:" + " ".join(command))
    # Fullstack client execution is an additional gate; this command checks compilation only.
    result = {"status": "checks_passed_pending_fullstack" if not issues else "rejected",
              "issues": issues, "evidence": evidence, "verification_workspace": str(verification),
              "workspace_files": workspace_files(workspace),
              "acceptance_sha256": hashlib.sha256(acceptance.read_bytes()).hexdigest(),
              "fullstack": "pending"}
    (run / "validation.json").write_text(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--jac", type=Path, required=True)
    parser.add_argument("--accept-browser", type=Path)
    args = parser.parse_args()
    if args.accept_browser:
        result = json.loads((args.run / "validation.json").read_text())
        replay = json.loads((args.run / "replay.json").read_text())
        browser = json.loads(args.accept_browser.read_text())
        workspace = Path(json.loads((args.run / "run.json").read_text())["workspace"])
        if result["issues"] or replay["status"] != "passed" or browser["status"] != "passed":
            raise ValueError("All acceptance, replay and browser gates must pass")
        if workspace_files(workspace) != result["workspace_files"]:
            raise ValueError("Workspace changed after acceptance checks")
        for path, digest in browser["source_sha256"].items():
            if hashlib.sha256((workspace / path).read_bytes()).hexdigest() != digest:
                raise ValueError("Browser verified a different source version: " + path)
        result.update(status="accepted", fullstack=browser, replay=str(args.run / "replay.json"))
        (args.run / "validation.json").write_text(json.dumps(result, indent=2))
    else:
        result = validate(args.run, args.jac)
    print(json.dumps({k: result[k] for k in ("status", "issues", "verification_workspace")}, indent=2))

# Run =====================================================
if __name__ == "__main__":
    main()
