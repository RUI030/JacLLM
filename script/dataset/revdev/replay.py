"""Replay recorded JacCoder calls in a clean workspace and compare source hashes."""

import argparse, json, re, sys, tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli
from dataset.revdev.checkpoint import workspace_files

# Functions ===============================================
def replay(run: Path, harness: Path, jac: Path, continue_report: bool = False) -> dict:
    run = run.resolve()
    root = Path(tempfile.mkdtemp(prefix="revdev-replay-"))
    workspace = root / "workspace"
    workspace.mkdir()
    original_roots = []
    outcomes = []
    output_paths = {}
    if continue_report:
        previous = json.loads((run / "replay.json").read_text())
        if not all(o.get("diagnostic_status_matches") and o["exit_code"] == 0 for o in previous["outcomes"]):
            raise ValueError("Cannot continue a replay with mismatched execution statuses")
        workspace = Path(previous["workspace"])
        root = workspace.parent
        current = [f for f in workspace_files(workspace) if not f["path"].startswith((".jaccoder/tool-results/", "dist/"))]
        if current != previous["actual"]:
            raise ValueError("Prior replay workspace was modified")
        outcomes = previous["outcomes"]
    done = {o["step"] for o in outcomes}
    for step in sorted(run.glob("step-*")):
        if not (step / "result.json").exists():
            continue
        observed = json.loads((step / "result.json").read_text())
        if not observed.get("executed", True):
            continue
        call = json.loads((step / "call.json").read_text())
        old_root = call["workspace"]
        if old_root not in original_roots:
            original_roots.append(old_root)
        if step.name in done:
            prior_result = json.loads((root / (step.name + ".result.json")).read_text())
            output_paths.update(zip(re.findall(r"\.jaccoder/tool-results/[^\s\]]+\.txt", observed["content"]),
                                    re.findall(r"\.jaccoder/tool-results/[^\s\]]+\.txt", prior_result["content"])))
            continue
        arguments = json.dumps(call["args"])
        for previous in sorted(original_roots, key=len, reverse=True):
            arguments = arguments.replace(previous, str(workspace))
        for original, replacement in output_paths.items():
            arguments = arguments.replace(original, replacement)
        replay_call = {**call, "workspace": str(workspace), "args": json.loads(arguments)}
        call_path = root / (step.name + ".call.json")
        result_path = root / (step.name + ".result.json")
        call_path.write_text(json.dumps(replay_call))
        execution = jac_cli.execute(["run", str(Path(__file__).with_name("dispatch.jac"))],
            jac=str(jac), cwd=harness, timeout=150,
            env={"REVDEV_CALL": str(call_path), "REVDEV_RESULT": str(result_path), "JACCODER_WEB_MODE": "1",
                 "REVDEV_JAC": observed.get("runtime_binary", "/home/imrui/.local/bin/jac" if call["name"] == "run_command" else str(jac))})
        (root / (step.name + ".execution.json")).write_text(json.dumps(vars(execution), indent=2))
        outcomes.append({"step": step.name, "tool": call["name"], "exit_code": execution.returncode})
        if not execution.ok or not result_path.exists():
            break
        replayed = json.loads(result_path.read_text())
        old_paths = re.findall(r"\.jaccoder/tool-results/[^\s\]]+\.txt", observed["content"])
        new_paths = re.findall(r"\.jaccoder/tool-results/[^\s\]]+\.txt", replayed["content"])
        output_paths.update(zip(old_paths, new_paths))
        signals = ("SYNTAX ERRORS", "TYPE ERRORS", "FAILED", "[ERROR]")
        outcomes[-1]["diagnostic_status_matches"] = all((s in observed["content"]) == (s in replayed["content"]) for s in signals)
    final = Path(json.loads((run / "run.json").read_text())["workspace"])
    generated = (".jaccoder/tool-results/", "dist/")
    expected = [f for f in workspace_files(final) if not f["path"].startswith(generated)]
    actual = [f for f in workspace_files(workspace) if not f["path"].startswith(generated)]
    result = {"status": "passed" if expected == actual and all(o["exit_code"] == 0 and o.get("diagnostic_status_matches") for o in outcomes) else "failed",
              "excluded_comparison": "Timestamped tool-result logs and generated dist archives are retained but not byte-compared. Log paths were mapped to actual replay outputs; build diagnostic status is compared.",
              "workspace": str(workspace), "outcomes": outcomes, "expected": expected, "actual": actual}
    (run / "replay.json").write_text(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "harness", "jac"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--continue-report", action="store_true")
    args = parser.parse_args()
    result = replay(args.run, args.harness, args.jac, args.continue_report)
    print(json.dumps({"status": result["status"], "calls": len(result["outcomes"]), "workspace": result["workspace"]}))

# Run =====================================================
if __name__ == "__main__":
    main()
