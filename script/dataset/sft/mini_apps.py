"""JacHammer-format SFT rows from the mini apps: one-screen apps whose point is the wiring (main.jac imports the server
module, the component uses `sv import`, server calls are awaited, a walker is spawned and never called).

Same route as dataset/sft/ui_apps.py takes for the reference UI apps, through the real harness on jac 0.34.28; only the
batches, the text folder and the output folder differ. A batch is output/sft/jac_ui_build/mini_apps_v*/ with
apps/<name>/ (own .jac files, jac.toml, styles/, lib/utils.jac, shadcn.txt), flows/<name>.json (browser flow) and
text/<name>.text.json (request, plan and write reasoning, journal, final reply, core browser steps).

The apps are written by a model that cannot run them, so nothing is used until it has passed here:
  --verify   each app gets the template's components/ui files, plus the ones in its shadcn.txt and what those import,
             from a verified app; then script/eval/agent/e2e_check.py runs its flow. One line per app in
             <batch>/verify.status ("<name>: pass" or the first failing step); report and screenshots in <batch>/e2e/.
  (default)  every app whose line says pass is replayed through jacBuilder's verification_runner (ui_apps.replay), and
             a replay with no check error, no blocked write and every file written becomes a main row and a planner
             row in output/sft/jac_ui_build/mini_apps_harness_v1/train.jsonl. Needs port 8080 free and jacBuilder's
             [byllm.compaction] ctx_window raised (see ui_apps.py). A run that already exists is not replayed again.

    python script/dataset/sft/mini_apps.py --verify
    python script/dataset/sft/mini_apps.py [--rows-only]
"""

import argparse, json, re, shutil, subprocess, sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from dataset.sft import ui_apps

# Setting =================================================
ROOT        = ui_apps.ROOT
APPS_DIR    = ui_apps.APPS_DIR
OUT_DIR     = APPS_DIR / "mini_apps_harness_v1"                               # train.jsonl, img/, runs/<app>/
UI_SOURCE   = APPS_DIR / "ui_apps_v1/apps/streaks/components/ui"              # shadcn files of a verified app
TEMPLATE    = APPS_DIR / "mini_apps_v1/apps/counter_fn"                       # the empty template's own css and cn()
TEMPLATE_FILES = ("styles/global.css", "lib/utils.jac")
E2E_PYTHON  = Path.home() / ".venvs/jacllm-e2e/bin/python"
E2E_CHECK   = ROOT / "script/eval/agent/e2e_check.py"
E2E_MAX_S   = 600
UI_IMPORT   = re.compile(r"^import from \.(\w+) ", re.M)
WROTE       = re.compile(r"^write (\S+): ", re.M)                           # replay.log: "write <file>: <result>"


# Functions ===============================================
def batches() -> list[Path]:
    return sorted(p for p in APPS_DIR.glob("mini_apps_v*") if (p / "apps").is_dir())


def passed(batch: Path) -> list[str]:
    status = batch / "verify.status"
    return [l.split(":")[0] for l in status.read_text().splitlines() if l.endswith(": pass")] if status.exists() else []


def add_ui_files(app: Path) -> list[str]:
    """Copy the template's css and cn(), then button, card, skeleton, the components in shadcn.txt and whatever those
    import. Returns the names it could not find."""
    for f in TEMPLATE_FILES:
        if not (app / f).exists():
            (app / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(TEMPLATE / f, app / f)
    ui = app / "components/ui"
    ui.mkdir(parents=True, exist_ok=True)
    todo = ["button", "card", "skeleton", *(app / "shadcn.txt").read_text().split()]
    missing = []
    while todo:
        name = todo.pop()
        if (ui / f"{name}.jac").exists():
            continue
        src = UI_SOURCE / f"{name}.jac"
        if not src.exists():
            missing.append(name)
            continue
        shutil.copy(src, ui)
        todo += UI_IMPORT.findall(src.read_text())
    return missing


def verify(batch: Path) -> None:
    lines = []
    for app in sorted(p for p in (batch / "apps").iterdir() if p.is_dir()):
        name, out = app.name, batch / "e2e" / app.name
        missing = add_ui_files(app)
        shutil.rmtree(out, ignore_errors=True)
        try:
            subprocess.run(["systemd-run", "--user", "-q", "--wait", "--pipe", "-p", "MemoryMax=4G", "-p", "MemorySwapMax=0",
                            f"--working-directory={ROOT}", str(E2E_PYTHON), str(E2E_CHECK), "--project", str(app),
                            "--steps", str(batch / "flows" / f"{name}.json"), "--out", str(out)],
                           capture_output=True, timeout=E2E_MAX_S)
        except subprocess.TimeoutExpired:
            pass
        report = out / "report.json"
        if not report.exists():
            result = "no report"
        else:
            r = json.loads(report.read_text())
            failed = next((s for s in r["steps"] if not s["ok"]), None)
            result = r["verdict"] if not failed else f"{r['verdict']} at step {failed['n']}: {failed.get('error', '')[:300]}"
        if missing:
            result += f" (no components/ui file for: {', '.join(missing)})"
        lines.append(f"{name}: {result}")
        print(lines[-1], flush=True)
    (batch / "verify.status").write_text("\n".join(lines) + "\n")


def clean(name: str, run: Path) -> str:
    """Empty when the replay is usable, else why not."""
    log = run / "replay.log"
    if not (run / "calls.jsonl").exists() or not log.exists():
        return "no calls.jsonl"
    problems = [l for l in log.read_text().splitlines() if l.startswith("!!")]
    if problems:
        return f"{len(problems)} problem(s): {problems[0][:200]}"
    return ""


def complete(row: dict, run: Path) -> bool:
    """Every file the replay wrote is still written in the row (a compacted session has lost its early writes). The
    replay skips a file that is already on disk unchanged (lib/utils.jac), so its log says what it wrote."""
    written = {json.loads(c["function"]["arguments"]).get("file_path", "").split("/prj_")[-1].split("/", 1)[-1]
               for m in row["messages"] if m["role"] == "assistant" for c in m.get("tool_calls") or []
               if c["function"]["name"] == "write_code"}
    return all(f in written for f in WROTE.findall((run / "replay.log").read_text()))


def produce(rows_only: bool) -> None:
    ui_apps.OUT_DIR = OUT_DIR
    img_dir = OUT_DIR / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    found = {name: batch / "apps" / name for batch in batches() for name in passed(batch)}
    rows = []
    for name, app in found.items():
        run = OUT_DIR / "runs" / name
        if not rows_only and not (run / "calls.jsonl").exists():
            ui_apps.TEXT_DIR = app.parents[1] / "text"
            ui_apps.replay(name, app)
        why = clean(name, run)
        if not why:
            pair = ui_apps.app_rows(name, run, img_dir)
            if not all(complete(r, run) for r in pair if r["meta"]["agent"] == "main"):
                why = "a file the replay wrote is missing from the row (compacted?)"
        print(f"{name}: {why or 'ok'}", flush=True)
        if not why:
            rows += pair
    with (OUT_DIR / "train.jsonl").open("w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    print(f"{len(rows)} rows from {len(rows) // 2} of {len(found)} verified apps -> {OUT_DIR / 'train.jsonl'}")
    if not rows:
        sys.exit("no rows: nothing to train on")


# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--verify", action="store_true", help="browser-check the apps of every batch")
    cli.add_argument("--rows-only", action="store_true", help="only rewrite rows from existing runs")
    a = cli.parse_args()
    if a.verify:
        for b in batches():
            verify(b)
    else:
        produce(a.rows_only)
