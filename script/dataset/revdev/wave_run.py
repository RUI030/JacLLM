"""Run a batch of backend revdev recipes through teacher, acceptance, replay and export.

Teacher runs go in parallel; validation and replay run one at a time; export runs
last and serially because every export rewrites the unified revdev dataset. Each
stage is skipped when its evidence already exists, so a rerun only redoes what
failed. A failure stops that app, never the batch; `wave.json` collects outcomes.
"""

import argparse, json, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Setting =================================================
ROOT = Path(__file__).resolve().parents[3]
RECIPES = ROOT / "script/dataset/revdev/recipes"
SCRIPTS = ROOT / "script/dataset/revdev"
PROMPT = ROOT / "dataset/raw/revdev/Mindcraft/m3/private/teacher_prompt_v1"
HARNESS = ROOT.parent / "jacBuilder"
JAC = Path.home() / ".local/bin/jac"
HARNESS_JAC = ROOT / "output/runtime/jac-v0.34.27/jac-0.34.27-linux-x86_64"

# Functions ===============================================
def stage(run: Path, name: str, command: list[str]) -> bool:
    logs = run.parent / "wave_logs"
    logs.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with open(logs / f"{run.name}.{name}.log", "w") as log:
        code = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
    print(json.dumps({"run": str(run.relative_to(ROOT)), "stage": name, "exit": code,
                      "seconds": round(time.time() - started)}), flush=True)
    return code == 0


def read(path: Path) -> dict:
    return json.loads(path.read_text()) if path.is_file() else {}


def teacher(slug: str, run: Path, max_steps: int, attempts: int = 3) -> str:
    """A crash (malformed teacher JSON, CLI error) leaves no executed call, so resume it."""
    recipe = RECIPES / slug
    for attempt in range(attempts):
        status = read(run / "run.json").get("status")
        if status == "teacher_finished_unvalidated":
            return "teacher_finished"
        if status in ("step_limit", "execution_interrupted"):
            return status
        resume = ["--continue-run"] if (run / "run.json").is_file() else []
        stage(run, f"teacher{attempt}", [sys.executable, str(SCRIPTS / "claude_adapter.py"),
              "--prompt", str(PROMPT), "--task", str(recipe / "task.json"),
              "--plan", str(recipe / "plan.json"), "--out", str(run), "--harness", str(HARNESS),
              "--jac", str(JAC), "--harness-jac", str(HARNESS_JAC), "--max-steps", str(max_steps), *resume])
    status = read(run / "run.json").get("status", "teacher_not_started")
    return "teacher_finished" if status == "teacher_finished_unvalidated" else status


def gate(slug: str, run: Path) -> str:
    """Independent acceptance, clean replay, then the backend accept gate."""
    if read(run / "validation.json").get("status") == "accepted":
        return "accepted"
    acceptance = RECIPES / slug / "reference_acceptance.jac"
    if read(run / "validation.json").get("status") != "checks_passed_pending_fullstack":
        stage(run, "validate", [sys.executable, str(SCRIPTS / "validate.py"), "--run", str(run),
              "--jac", str(JAC), "--acceptance", str(acceptance)])
        validation = read(run / "validation.json")
        if validation.get("status") != "checks_passed_pending_fullstack":
            return "rejected_acceptance:" + ",".join(validation.get("issues", ["no_validation"]))
    if read(run / "replay.json").get("status") != "passed":
        stage(run, "replay", [sys.executable, str(SCRIPTS / "replay.py"), "--run", str(run),
              "--harness", str(HARNESS), "--jac", str(JAC), "--harness-jac", str(HARNESS_JAC)])
        if read(run / "replay.json").get("status") != "passed":
            return "rejected_replay"
    stage(run, "accept", [sys.executable, str(SCRIPTS / "validate.py"), "--run", str(run),
          "--jac", str(JAC), "--accept-backend"])
    return read(run / "validation.json").get("status", "rejected_accept")


def export(slug: str, run: Path) -> str:
    if (run / "export.json").is_file():
        return "exported"
    provenance = read(RECIPES / slug / "provenance.json")
    ok = stage(run, "export", [sys.executable, str(SCRIPTS / "export.py"), "--run", str(run),
               "--name", slug, "--split-group", provenance["split_group"], "--split", "train"])
    return "exported" if ok else "export_failed"

# Run =====================================================
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slugs", nargs="+")
    parser.add_argument("--wave", type=Path, default=ROOT / "dataset/raw/revdev/wave1")
    parser.add_argument("--run-name", default="teacher_v1")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-steps", type=int, default=60)
    parser.add_argument("--no-export", action="store_true")
    args = parser.parse_args()
    runs = {slug: args.wave.resolve() / slug / "runs" / args.run_name for slug in args.slugs}
    for run in runs.values():
        run.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(args.workers) as pool:
        status = dict(zip(runs, pool.map(lambda s: teacher(s, runs[s], args.max_steps), runs)))
    for slug, run in runs.items():
        if status[slug] == "teacher_finished":
            status[slug] = gate(slug, run)
    if not args.no_export:
        for slug, run in runs.items():
            if status[slug] == "accepted":
                status[slug] = export(slug, run)
    report = read(args.wave.resolve() / "wave.json")
    report.update({slug: {"run": str(runs[slug].relative_to(ROOT)), "status": status[slug],
                          "steps": read(runs[slug] / "run.json").get("steps")} for slug in runs})
    (args.wave.resolve() / "wave.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
