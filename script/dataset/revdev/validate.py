"""Verify generated files and independent acceptance checks before SFT export."""

import argparse, hashlib, json, shutil, sys, tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli
from dataset.revdev.checkpoint import workspace_files
from dataset.revdev.plan_md import validate_rendered

# Functions ===============================================
def validate(run: Path, jac: Path, *, acceptance: Path | None = None,
             acceptance_target: str = "revdev_acceptance.jac",
             test_target: str = "revdev_acceptance.jac", ui_only: bool = False) -> dict:
    metadata = json.loads((run / "run.json").read_text())
    workspace = Path(metadata["workspace"])
    evidence = []
    issues = []
    if metadata["status"] != "teacher_finished_unvalidated":
        issues.append("teacher_not_finished")
    plan = json.loads((workspace / ".jaccoder/build_plan.json").read_text())
    if metadata.get("plan_format", "").startswith("markdown_mermaid_"):
        markdown_path = workspace / "docs/plan.md"
        if not markdown_path.is_file():
            issues.append("missing:docs/plan.md")
        else:
            try:
                validate_rendered(markdown_path.read_text(), plan,
                                  module_only=metadata["plan_format"] == "markdown_mermaid_v2")
            except ValueError as exc:
                issues.append("invalid:docs/plan.md:" + str(exc))
    for row in plan["files"]:
        path = workspace / row["path"]
        if not path.is_file():
            issues.append("missing:" + row["path"])
        elif path.suffix == ".jac" and "NotImplementedError" in path.read_text():
            issues.append("stub:" + row["path"])
    verification = Path(tempfile.mkdtemp(prefix="revdev-acceptance-"))
    shutil.copytree(workspace, verification, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".jac", "node_modules", "__pycache__"))
    if ui_only:
        if acceptance:
            raise ValueError("UI-only acceptance uses the reference browser flow, not Jac tests")
        commands = (["check", "main.jac"], ["build", "main.jac"])
    else:
        acceptance = acceptance or Path(__file__).parent / "fixtures/mindcraft_acceptance.jac"
        for relative in (acceptance_target, test_target):
            if Path(relative).is_absolute() or ".." in Path(relative).parts:
                raise ValueError("Acceptance paths must stay inside verification workspace")
        target = verification / acceptance_target
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(acceptance, target)
        commands = (["check", "main.jac"], ["test", test_target])
    for command in commands:
        result = jac_cli.execute(command, jac=str(jac), cwd=verification, timeout=120,
                                 env={"JAC_TEST_NATIVE": "1", "JAC_TEST_JOBS": "0"})
        evidence.append({"command": command, **vars(result)})
        if not result.ok or result.timed_out:
            issues.append("failed:" + " ".join(command))
    # Fullstack client execution is an additional gate; this command checks compilation only.
    result = {"status": "checks_passed_pending_fullstack" if not issues else "rejected",
              "issues": issues, "evidence": evidence, "verification_workspace": str(verification),
              "workspace_files": workspace_files(workspace),
              "acceptance_sha256": hashlib.sha256(acceptance.read_bytes()).hexdigest() if acceptance else None,
              "acceptance_mode": "reference_browser" if ui_only else "jac_test",
              "fullstack": "pending"}
    (run / "validation.json").write_text(json.dumps(result, indent=2))
    return result


def accept_backend(run: Path) -> dict:
    """Accept a backend-only run after independent tests and clean replay."""
    result = json.loads((run / "validation.json").read_text())
    replay = json.loads((run / "replay.json").read_text())
    workspace = Path(json.loads((run / "run.json").read_text())["workspace"])
    plan = json.loads((workspace / ".jaccoder/build_plan.json").read_text())
    if result["status"] != "checks_passed_pending_fullstack" or result["issues"]:
        raise ValueError("Independent backend acceptance checks must pass")
    if replay["status"] != "passed":
        raise ValueError("Clean-workspace replay must pass")
    if workspace_files(workspace) != result["workspace_files"]:
        raise ValueError("Workspace changed after acceptance checks")
    if plan.get("ui", {}).get("pages") or any(
        row.get("layer") in {"page", "client", "frontend"} for row in plan["files"]
    ):
        raise ValueError("Backend acceptance cannot certify a planned UI")
    if any("JsxElement" in path.read_text() for path in workspace.rglob("*.jac")
           if ".jac" not in path.parts and ".jaccoder" not in path.parts):
        raise ValueError("Backend acceptance cannot certify client JSX")
    result.update(status="accepted",
                  fullstack={"status": "not_applicable", "kind": "backend_only",
                             "evidence": "independent Jac check/test and clean replay"},
                  replay=str(run / "replay.json"))
    (run / "validation.json").write_text(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--jac", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path)
    parser.add_argument("--acceptance-target", default="revdev_acceptance.jac")
    parser.add_argument("--test-target", default="revdev_acceptance.jac")
    parser.add_argument("--ui-only", action="store_true",
                        help="Use Jac check/build and require the same scripted browser flow on reference and generated UI")
    gate = parser.add_mutually_exclusive_group()
    gate.add_argument("--accept-browser", type=Path)
    gate.add_argument("--accept-backend", action="store_true")
    parser.add_argument("--reference-browser", type=Path)
    args = parser.parse_args()
    if args.accept_backend:
        result = accept_backend(args.run)
    elif args.accept_browser:
        result = json.loads((args.run / "validation.json").read_text())
        replay = json.loads((args.run / "replay.json").read_text())
        browser = json.loads(args.accept_browser.read_text())
        workspace = Path(json.loads((args.run / "run.json").read_text())["workspace"])
        if result["issues"] or replay["status"] != "passed" or browser["status"] != "passed":
            raise ValueError("All acceptance, replay and browser gates must pass")
        if result.get("acceptance_mode") == "reference_browser":
            if not args.reference_browser:
                raise ValueError("UI-only acceptance requires --reference-browser")
            reference = json.loads(args.reference_browser.read_text())
            if (reference.get("status") != "passed" or reference.get("scenario") != "scripted"
                    or browser.get("scenario") != "scripted" or not reference.get("spec_sha256")
                    or reference["spec_sha256"] != browser.get("spec_sha256")):
                raise ValueError("Reference and generated UI must pass the same scripted browser flow")
            result["reference_browser"] = reference
        if workspace_files(workspace) != result["workspace_files"]:
            raise ValueError("Workspace changed after acceptance checks")
        for path, digest in browser["source_sha256"].items():
            if hashlib.sha256((workspace / path).read_bytes()).hexdigest() != digest:
                raise ValueError("Browser verified a different source version: " + path)
        result.update(status="accepted", fullstack=browser, replay=str(args.run / "replay.json"))
        (args.run / "validation.json").write_text(json.dumps(result, indent=2))
    else:
        result = validate(args.run, args.jac, acceptance=args.acceptance,
                          acceptance_target=args.acceptance_target, test_target=args.test_target,
                          ui_only=args.ui_only)
    print(json.dumps({k: result[k] for k in ("status", "issues", "verification_workspace")}, indent=2))

# Run =====================================================
if __name__ == "__main__":
    main()
