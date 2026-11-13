"""Continue a scenario in fresh jac_coder sessions, each one starting from the project the previous session left.

A session of a small model often ends in a loop or at the context limit before the app works. This runs the same
scenario again as a NEW session (no chat history) on the half-built project, up to --sessions times in total, and stops
when the browser flow passes. Between two sessions:
- the project snapshot is committed to <chain>/history (git), one commit per session, so `git log -p` in that folder
  shows what each session changed;
- the snapshot becomes a jacBuilder template (assets/templates/chain-<scenario>.jacpack, empty.jacpack with the
  snapshot's files and jac.toml) for the next session's `jac create --use`; it is removed after that session;
- the next request is a handoff note plus the scenario's own request. The note says what the browser shows now. It
  comes from e2e_check.py's report with the flow's expected texts left out, so the flow itself is not given away.
Needs the served model up (serve.sh), like run_jaccoder.sh. One run at a time.

    python script/eval/agent/continue_run.py <model> <scenario> [--sessions 3] [--from <run dir used as session 1>]

Output: output/eval/agent/<scenario>/chain-<model>_<MM-DD_HH-MM>/ with history/ (git), chain.json (one entry per
session: run, harness verdict, browser verdict, commit) and session_N/scenario/ (the request that session got).
The runs are ordinary run dirs next to it.
"""

import argparse, json, os, re, shutil, subprocess, time, tomllib
from pathlib import Path

# Setting =================================================
HERE        = Path(__file__).resolve().parent
ROOT        = HERE.parents[2]
SCENARIOS   = HERE / "scenarios"
OUT         = ROOT / "output/eval/agent"
TEMPLATES   = ROOT.parent / "jacBuilder/assets/templates"
E2E_PYTHON  = Path.home() / ".venvs/jacllm-e2e/bin/python"
UNIT        = "jacllm-jh-run"                    # the unit name the pipelines use for one jac_coder run
LIMITS      = ["-p", "MemoryMax=12G", "-p", "MemorySwapMax=0", "-p", "RuntimeMaxSec=5400"]
E2E_MAX_S   = 900
SKIP_PARTS  = {".git", ".jac", "node_modules", "dist", "screenshots"}
VERDICT     = re.compile(r"stage 1/1 [a-z]+ \(([A-Z_]+)\)")
HANDOFF     = """This project was started in an earlier session for the request below, and it is not finished.
Do not start over. First list the files and read what is already written, then fix or finish it.

Where it stands now: {state}

The request:
{request}"""


# Functions ===============================================
def sh(*cmd, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], text=True, capture_output=True, **kw)


def snapshot_of(run: Path, scenario: str) -> Path:
    return run / "artifacts" / scenario / "1" / "project_snapshot"


def harness_verdict(run: Path) -> str:
    logs = [run / "run.log", run.parent / f"{run.name}.log"]
    found = [m for f in logs if f.exists() for m in VERDICT.findall(f.read_text(errors="replace"))]
    return found[-1] if found else "no-verdict"


def browser_check(run: Path) -> dict:
    """e2e_check.py's report for the run: {"verdict": pass|fail|server_not_ready|missing, "steps": [...]}."""
    report = run / "e2e/report.json"
    if not report.exists():
        try:
            sh(E2E_PYTHON, HERE / "e2e_check.py", run, timeout=E2E_MAX_S)
        except subprocess.TimeoutExpired:
            pass
    return json.loads(report.read_text()) if report.exists() else {"verdict": "missing", "steps": []}


def state_note(report: dict) -> str:
    """What the browser shows, without the flow's expected texts."""
    failed = next((s for s in report.get("steps", []) if not s.get("ok")), None)
    if report["verdict"] in ("server_not_ready", "missing") or failed is None:
        return "the app's server does not start."
    if failed["n"] == 0:
        error = re.sub(r"/\S*/e2e/app/", "", failed.get("error", "")).split("Click outside")[0][:400]
        return f"the page does not render. The browser shows: {error}"
    return "the page opens, but it does not yet do what the request asks."


def commit(history: Path, snapshot: Path, message: str) -> str:
    if not snapshot.is_dir():
        raise SystemExit(f"no project snapshot at {snapshot}")
    history.mkdir(parents=True, exist_ok=True)
    if not (history / ".git").exists():
        sh("git", "init", "-q", cwd=history)
    for p in history.iterdir():                  # the folder becomes exactly the snapshot, .git aside
        if p.name != ".git":
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    shutil.copytree(snapshot, history, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", ".jac", ".jac-*", "node_modules"))
    sh("git", "add", "-A", cwd=history)
    sh("git", "-c", "user.name=continue_run", "-c", "user.email=continue_run@local", "commit", "-q", "--allow-empty",
       "-m", message, cwd=history)
    return sh("git", "rev-parse", "--short", "HEAD", cwd=history).stdout.strip()


def make_pack(snapshot: Path, name: str) -> Path:
    """empty.jacpack with the snapshot's text files and its jac.toml as the config."""
    pack = json.loads((TEMPLATES / "empty.jacpack").read_text())
    pack.update(name=name, description=f"continue_run.py: {snapshot}", is_default_for_kind=False)
    try:
        pack["config"] = tomllib.loads((snapshot / "jac.toml").read_text())
    except (OSError, tomllib.TOMLDecodeError):
        pass                                     # a jac.toml the model broke: the template's config stands in
    files = {k: v for k, v in pack["files"].items() if k.startswith("dist/")}
    for p in sorted(snapshot.rglob("*")):
        parts = p.relative_to(snapshot).parts
        if not p.is_file() or parts == ("jac.toml",) or any(x in SKIP_PARTS or x.startswith(".jac-") for x in parts):
            continue
        try:
            files["/".join(parts)] = p.read_text()
        except UnicodeDecodeError:
            continue
    pack["files"] = files
    out = TEMPLATES / f"{name}.jacpack"
    out.write_text(json.dumps(pack, indent=2))
    return out


def session(model: str, scenario: str, template: str, scenario_dir: Path) -> Path:
    """One jac_coder run under the usual limits; returns its run dir."""
    runs = lambda: {p for p in (OUT / scenario).glob(f"jaccoder-{model}_*") if p.is_dir()}
    before = runs()
    sh("systemctl", "--user", "reset-failed", UNIT)
    sh("systemd-run", "--user", "--wait", "--unit", UNIT, *LIMITS, f"--working-directory={ROOT}",
       f"--setenv=TEMPLATE={template}", f"--setenv=SCENARIO_DIR={scenario_dir}",
       "bash", HERE / "run_jaccoder.sh", model, scenario)
    sh("pkill", "-u", str(os.getuid()), "-f", "agent-browser")
    time.sleep(5)
    new = sorted(runs() - before)
    if not new:
        raise SystemExit(f"no run dir appeared for {scenario}")
    return new[-1]


def chain(model: str, scenario: str, sessions: int, first: Path | None) -> None:
    base = SCENARIOS / scenario
    request = (base / "stage_1.md").read_text().strip()
    home = OUT / scenario / f"chain-{model}_{time.strftime('%m-%d_%H-%M')}"
    log = []
    run, report = first, None
    for n in range(1, sessions + 1):
        if n > 1 or run is None:
            if n == 1:
                template, scenario_dir = "empty", base
            else:
                template = f"chain-{scenario}"
                make_pack(snapshot_of(run, scenario), template)
                scenario_dir = home / f"session_{n}" / "scenario"
                scenario_dir.mkdir(parents=True)
                (scenario_dir / "manifest.json").write_text((base / "manifest.json").read_text())
                (scenario_dir / "stage_1.md").write_text(HANDOFF.format(state=state_note(report), request=request) + "\n")
            try:
                run = session(model, scenario, template, scenario_dir)
            finally:
                (TEMPLATES / f"chain-{scenario}.jacpack").unlink(missing_ok=True)
        report = browser_check(run)
        entry = {"session": n, "run": run.name, "harness": harness_verdict(run), "browser": report["verdict"],
                 "state": state_note(report) if report["verdict"] != "pass" else "the browser flow passes."}
        entry["commit"] = commit(home / "history", snapshot_of(run, scenario),
                                 f"session {n}: {run.name} | harness {entry['harness']} | browser {entry['browser']}")
        log.append(entry)
        home.mkdir(parents=True, exist_ok=True)
        (home / "chain.json").write_text(json.dumps({"model": model, "scenario": scenario, "sessions": log}, indent=1))
        print(json.dumps(entry), flush=True)
        if report["verdict"] == "pass":
            break


# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("model")
    cli.add_argument("scenario")
    cli.add_argument("--sessions", type=int, default=3, help="sessions in total, the first one included")
    cli.add_argument("--from", dest="first", type=Path, help="an existing run dir to use as session 1")
    args = cli.parse_args()
    chain(args.model, args.scenario, args.sessions, args.first.resolve() if args.first else None)
