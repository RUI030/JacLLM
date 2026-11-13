"""Independent end-to-end check of the app a jac_coder run built: start it the way the harness preview does
(`jac start --dev`, jac 0.34.28), drive it with Playwright (system Chrome), and record what a user would see.

The harness's own browser_validate can pass a page that shows Vite's error overlay, so this check does not trust it.
Per run it copies artifacts/<scenario>/1/project_snapshot to <run>/e2e/app, links node_modules from a harness project,
runs the scenario's scenarios/<name>/e2e.json steps, and writes <run>/e2e/{report.json, step_NN.png, server.log}.

e2e.json: {"steps": [step, ...]}, one key per step, run in order, stopping at the first failure:
    {"goto": "/path"}                       open a path
    {"expect_text": "text" | ["a", "b"]}    every text is visible somewhere on the page (case-insensitive)
    {"absent_text": "text"}                 text is not on the page
    {"click": "regex"}                      the first link, button, checkbox, then element whose name/text matches
    {"click_link": "regex"}                 the first link whose href matches (for items whose names the model chose)
    {"fill": {"nth": 0, "value": "x"}}      type into the nth visible text input / textarea
    {"fill": {"label": "regex", "value": "x"}}   type into the field whose label matches
    {"choose": {"label": "regex", "option": "text"}}   open the select whose label matches, pick the option
    {"check": 0}                            click the nth visible checkbox
    {"press": "Enter"}                      key press on the focused element
    {"expect_url": "regex"}                 the current path (and query) matches
    {"reload": true}                        reload the page
    {"viewport": [390, 844]}                resize the page (e.g. to check the phone layout)
    {"full_page": true}                     no action; this step's screenshot covers the whole page
Every page load also fails on: a blank body, Vite's error overlay, an uncaught page error (and, with --console-errors,
any console.error output such as React warnings, which the harness's browser_validate reports as page errors).

Needs the e2e venv (`python -m venv ~/.venvs/jacllm-e2e && ~/.venvs/jacllm-e2e/bin/pip install playwright`) and
google-chrome on PATH.

    ~/.venvs/jacllm-e2e/bin/python script/eval/agent/e2e_check.py <run dir> [<run dir> ...]
    # any project dir (e.g. a spike workspace on jac 0.36.1, which installs its own node_modules): open "/", or
    # run the steps of --steps <e2e.json>
    ~/.venvs/jacllm-e2e/bin/python script/eval/agent/e2e_check.py --project <dir> --out <dir> --jac ~/.local/bin/jac
"""

import argparse, json, os, re, shutil, signal, socket, subprocess, time, urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

# Setting =================================================
ROOT      = Path(__file__).resolve().parent.parent.parent.parent
SCENARIOS = Path(__file__).resolve().parent / "scenarios"
JAC       = Path.home() / ".jacbin_pinned/jac"
HARNESS   = ROOT.parent / "jacBuilder/evaluation/verification_runner/.local_projects/eval-harness"
READY_S   = 300                # a 0.36 project installs its npm packages on first start
SETTLE_MS = 1500
NODE_MODULES: Path | None = None   # --node-modules: linked instead of a harness project's (e.g. one with extra fonts)
CONSOLE_ERRORS = False             # --console-errors: console.error output (React warnings) also fails a step, as in browser_validate
CONSOLE_KNOWN = ("Failed to load resource",          # this checker's own setup: /favicon.ico 404, fonts via /@fs/ 403
                 "Overlay")                          # 0.34.28's installed DialogOverlay/AlertDialogOverlay take no ref


# Functions ===============================================
def free_port() -> int:
    """A free port whose +1 neighbour (jac's API port) is free as well."""
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port + 1)) != 0:
                return port


def node_modules() -> Path:
    if NODE_MODULES:
        return NODE_MODULES
    for p in sorted(HARNESS.glob("*/.jac/client/node_modules")):
        if (p / "vite").exists():
            return p.resolve()
    raise SystemExit(f"no harness project with node_modules under {HARNESS}")


def start_app(app: Path, port: int, log: Path, jac: Path) -> subprocess.Popen:
    if jac == JAC:                       # 0.34.28 projects from the harness: reuse its installed node_modules
        (app / ".jac/client").mkdir(parents=True, exist_ok=True)
        link = app / ".jac/client/node_modules"
        if not link.exists():
            link.symlink_to(node_modules())
    env = {**os.environ, "PATH": f"{jac.parent}:{os.environ['PATH']}"}
    return subprocess.Popen([str(jac), "start", "main.jac", "-p", str(port), "--dev"], cwd=app, env=env,
                            stdout=log.open("w"), stderr=subprocess.STDOUT, start_new_session=True)


def wait_ready(url: str, proc: subprocess.Popen) -> bool:
    end = time.time() + READY_S
    while time.time() < end and proc.poll() is None:
        try:
            if urllib.request.urlopen(url, timeout=5).status == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def page_problems(page, errors: list[str]) -> list[str]:
    """Blank page, Vite error overlay, uncaught errors since the last call."""
    out = [f"page error: {e}" for e in errors]
    errors.clear()
    overlay = page.evaluate("() => { const o = document.querySelector('vite-error-overlay');"
                            " return o && o.shadowRoot ? o.shadowRoot.textContent : null; }")
    if overlay:
        out.append("vite error overlay: " + " ".join(overlay.split(":host")[0].split())[:300])
    elif not page.inner_text("body").strip():
        out.append("blank page")
    return out


def click(page, name: str) -> None:
    rx = re.compile(name, re.I)
    for loc in (page.get_by_role("link", name=rx), page.get_by_role("button", name=rx),
                page.get_by_role("checkbox", name=rx), page.get_by_text(rx)):
        if loc.count():
            loc.first.click()
            return
    raise AssertionError(f"nothing clickable named {name!r}")


def run_step(page, base: str, step: dict) -> None:
    (kind, arg), = step.items()
    if kind == "goto":
        page.goto(base + arg, wait_until="networkidle")
    elif kind == "reload":
        page.reload(wait_until="networkidle")
    elif kind == "click":
        click(page, arg)
    elif kind == "click_link":
        hrefs = [h for h in page.eval_on_selector_all("a[href]", "as => as.map(a => a.getAttribute('href'))")
                 if re.search(arg, h)]
        assert hrefs, f"no link with href matching {arg!r}"
        page.locator(f'a[href="{hrefs[0]}"]').first.click()
    elif kind == "fill" and "label" in arg:
        field = page.get_by_label(re.compile(arg["label"], re.I)).first
        field.fill(arg["value"])
        field.focus()
    elif kind == "fill":
        boxes = page.locator("input:visible:not([type=checkbox]):not([type=radio]):not([type=submit]), textarea:visible")
        assert boxes.count() > arg["nth"], f"only {boxes.count()} visible text inputs"
        boxes.nth(arg["nth"]).fill(arg["value"])
        boxes.nth(arg["nth"]).focus()
    elif kind == "choose":
        page.get_by_label(re.compile(arg["label"], re.I)).first.click()
        page.get_by_role("option", name=arg["option"]).first.click()
    elif kind == "viewport":
        page.set_viewport_size({"width": arg[0], "height": arg[1]})
    elif kind == "full_page":
        pass
    elif kind == "check":
        boxes = page.get_by_role("checkbox").locator("visible=true")  # native inputs and role=checkbox buttons (shadcn)
        assert boxes.count() > arg, f"only {boxes.count()} visible checkboxes"
        boxes.nth(arg).click()
    elif kind == "press":
        page.keyboard.press(arg)
    elif kind == "expect_text":
        body = page.inner_text("body").lower()
        missing = [t for t in ([arg] if isinstance(arg, str) else arg) if t.lower() not in body]
        assert not missing, f"not on the page: {missing}"
    elif kind == "absent_text":
        assert arg.lower() not in page.inner_text("body").lower(), f"still on the page: {arg!r}"
    elif kind == "expect_url":
        path = re.sub(r"^https?://[^/]+", "", page.url)
        assert re.search(arg, path), f"url {path!r} does not match {arg!r}"
    else:
        raise ValueError(f"unknown step {step}")


def check_run(run: Path) -> dict:
    snaps = sorted(run.glob("artifacts/*/1/project_snapshot"))
    if not snaps:
        return {"run": str(run), "verdict": "no_snapshot"}
    scenario = snaps[0].parent.parent.name
    spec = json.loads((SCENARIOS / scenario / "e2e.json").read_text())
    return check_app(snaps[0], spec["steps"], run / "e2e", JAC, {"run": str(run.relative_to(ROOT)), "scenario": scenario})


def check_app(src: Path, steps: list[dict], out: Path, jac: Path, report: dict) -> dict:
    """Copy src to out/app, start it, run the steps; writes out/report.json."""
    shutil.rmtree(out, ignore_errors=True)
    app = out / "app"
    shutil.copytree(src, app, symlinks=True, ignore=shutil.ignore_patterns("node_modules", ".jac", ".pytest_cache"))
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    proc = start_app(app, port, out / "server.log", jac)
    report = {**report, "steps": [], "verdict": "pass"}
    try:
        if not wait_ready(base + "/", proc):
            report["verdict"] = "server_not_ready"
            report["server_tail"] = (out / "server.log").read_text(errors="replace")[-1500:]
            return report
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            if CONSOLE_ERRORS:
                page.on("console", lambda m: m.type == "error" and not any(k in m.text for k in CONSOLE_KNOWN)
                        and errors.append("console.error: " + m.text[:300]))
            for n, step in enumerate(steps):
                rec = {"n": n, "step": step}
                try:
                    run_step(page, base, step)
                    page.wait_for_timeout(SETTLE_MS)
                    problems = page_problems(page, errors)
                    assert not problems, "; ".join(problems)
                    rec["ok"] = True
                except Exception as e:
                    rec.update(ok=False, error=str(e).splitlines()[0][:400])
                    report["verdict"] = "fail"
                page.screenshot(path=str(out / f"step_{n:02d}.png"), full_page="full_page" in step)
                rec["shot"] = f"step_{n:02d}.png"
                report["steps"].append(rec)
                if not rec["ok"]:
                    break
            browser.close()
        return report
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=30)
        shutil.rmtree(app / ".jac", ignore_errors=True)
        (out / "report.json").write_text(json.dumps(report, indent=1) + "\n")


# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("runs", nargs="*", type=Path)
    cli.add_argument("--project", type=Path, help="check this project dir instead of runs (opens / unless --steps)")
    cli.add_argument("--steps", type=Path, help="with --project: an e2e.json to run")
    cli.add_argument("--out", type=Path, help="with --project: where the copy, screenshots and report go")
    cli.add_argument("--jac", type=Path, default=JAC)
    cli.add_argument("--node-modules", type=Path, help="node_modules to link into 0.34.28 projects")
    cli.add_argument("--console-errors", action="store_true", help="fail a step on console.error output too")
    a = cli.parse_args()
    NODE_MODULES = a.node_modules.resolve() if a.node_modules else None
    CONSOLE_ERRORS = a.console_errors
    if a.project:
        steps = json.loads(a.steps.read_text())["steps"] if a.steps else [{"goto": "/"}]
        r = check_app(a.project.resolve(), steps, a.out.resolve(), a.jac, {"project": str(a.project)})
        print(r["verdict"], a.project, next((s["error"] for s in r["steps"] if not s["ok"]), ""))
    for run in a.runs:
        r = check_run(run.resolve())
        failed = next((s for s in r.get("steps", []) if not s["ok"]), None)
        print(f"{r['verdict']:16s} {run}" + (f"  step {failed['n']} {failed['step']}: {failed['error']}" if failed else ""))
