"""JacHammer-format SFT rows from the reference UI apps, each replayed through the real JacHammer harness (jac 0.34.28).

For every app under output/sft/jac_ui_build/<batch>/apps/ and its hand-written text (text/<app>.text.json: the user
request, plan and write reasoning, journal, final reply, core browser flow), a spec is built, jacBuilder's
verification_runner runs jac_coder against dataset/parser/harness_replay.py (the scripted model), and the logged
session becomes prod-64k-shaped rows (one main-agent row, one planner row) with the harness's own screenshots.
Needs jacBuilder next to this repo with [byllm.compaction] ctx_window raised so the session is not compacted.

    python script/dataset/sft/ui_apps.py [app ...]            # replay (all apps by default), then write rows
    python script/dataset/sft/ui_apps.py --rows-only          # rewrite rows from the existing runs
"""

import argparse, base64, hashlib, json, os, re, subprocess, sys, time, tomllib, uuid
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from dataset.parser.harness_replay import TEMPLATE_UI, imports_of, project_files, write_order

# Setting =================================================
DS_NAME      = "ui_apps_harness_v1"
SOURCE       = "harness-replay"
TASK_TYPE    = "trajectory"
ROOT         = Path(__file__).resolve().parents[3]
APPS_DIR     = ROOT / "output/sft/jac_ui_build"                  # not under dataset/: moved there once reviewed
BATCHES      = ("ui_apps_v1", "ui_apps_v2")
TEXT_DIR     = APPS_DIR / "text"
OUT_DIR      = APPS_DIR / DS_NAME                                 # train.jsonl, img/, runs/<app>/
REPLAY       = ROOT / "script/dataset/parser/harness_replay.py"
JACBUILDER   = ROOT.parent / "jacBuilder"
HARNESS_DIR  = JACBUILDER / "evaluation/verification_runner/.local_projects/eval-harness"
JAC_BIN      = Path.home() / ".jacbin_pinned"                     # jac 0.34.28, what the harness runs projects on
AGENT_BIN    = Path.home() / "miniforge3/envs/jaccoder/bin"       # agent-browser
PORT         = 8080
MEMORY_MAX   = "8G"
APP_TYPES    = {"dashboard", "landing", "saas", "ecommerce", "blog", "portfolio", "tool"}   # planner schema (jac_coder/core/nodes.jac)
NAV_PATTERNS = {"sidebar", "topnav", "bottomnav", "none"}
PURPOSES     = {"capture", "browse", "monitor", "focus", "persuade", "workspace"}
RESULT_FOR   = re.compile(r"^\[Tool result for (\w+) \(id (\S+?)\)\]")
PRIM_ERR     = re.compile(r"page error.*?\n\s+at (\w+) \([^)]*?/compiled/(components/ui/\w+)\.js", re.S)
FLAG         = re.compile(r"page error|BLOCKED|ERRORS:|error\[|\[plugin:|Failed to|LOOP DETECTED|could not open")


# Functions ===============================================
def apps() -> dict[str, Path]:
    return {p.name: p for b in BATCHES for p in sorted((APPS_DIR / b / "apps").iterdir())}


def layer(f: str) -> str:
    if f.startswith("services/"):
        return "service"
    if f.startswith("lib/"):
        return "util"
    if f == "main.jac":
        return "shell"
    return "layout" if f == "pages/layout.jac" else "page" if f.startswith("pages/") else "component"


def exports(text: str) -> list[str]:
    return re.findall(r"^(?:def|walker|node|obj|edge|glob)(?::\w+)?\s+(\w+)", text, re.M)


def route_of(f: str) -> str:
    """pages/ file -> URL, as jac's route scanner maps it."""
    p = re.sub(r"\([^)]*\)/", "", f[len("pages/"):-len(".jac")])
    p = re.sub(r"(^|/)index$", "", p)
    p = re.sub(r"\[\.\.\.\w+\]", "*", p)
    return "/" + re.sub(r"\[(\w+)\]", r":\1", p)


def build_spec(app: Path, text: dict) -> dict:
    """The replay spec: request, shadcn/retheme pre-flight, write order, build_plan.json, reasoning, browser flow."""
    files = project_files(app)
    order = write_order(files)
    own = set(order)
    shad = tomllib.loads(files["jac.toml"])["jac-shadcn"]
    ui = sorted(p.stem.replace("_", "-") for p in (app / "components/ui").glob("*.jac") if p.stem not in TEMPLATE_UI)
    ui = ["sonner" if u == "sonner-toast" else u for u in ui]
    assert text["app_type"] in APP_TYPES and text["nav_pattern"] in NAV_PATTERNS, (text["app_type"], text["nav_pattern"])
    if any(f.startswith("pages/") for f in order):
        routes = [(f, Path(f).stem, route_of(f)) for f in order if f.startswith("pages/") and f != "pages/layout.jac"]
    else:                                        # manual Router: <Route path=... element={<X/>}>, redirects left out
        routes = [(path, comp, path) for f in order
                  for path, comp in re.findall(r'<Route\s+path="([^"]+)"\s+element=\{<(\w+)', files[f]) if comp != "Navigate"]
    for key, _, _ in routes:
        assert key in text["titles"] and text["screen_kind"].get(key) in PURPOSES, f"titles/screen_kind for {key}"
    for s in text["browser"]:                    # browser_do: every line before the last must be input
        assert all("click" not in a for a in s.get("do", [])[:-1]), f"click before the last line: {s}"
    plan = {
        "schema_version": "1",
        "ui": {"app_type": text["app_type"], "nav_pattern": text["nav_pattern"],
               "pages": [{"name": n, "route": r, "title": text["titles"][k], "purpose": text["screen_kind"][k]} for k, n, r in routes],
               "primitive_components": ["button", "card"] + ui,
               "style": shad["style"], "base_color": shad["baseColor"], "theme": shad["theme"], "font": shad["font"],
               "radius": shad["radius"], "menu_accent": shad["menuAccent"], "design_rationale": text["design_rationale"],
               "auth_required": text.get("auth", False), "backend_required": any(f.startswith("services/") for f in order),
               "ai_required": False},
        "files": [{"path": f, "layer": layer(f), "purpose": text["why"][f], "exports": exports(files[f]),
                   "imports_from_plan": sorted({e for d in imports_of(f, files[f], own) for e in exports(files[d])}
                                               & set(re.findall(r"\w+", files[f]))),
                   "write_order": i + 1, "status": "pending"} for i, f in enumerate(order)],
        "write_order": order,
        "dependency_graph": {f: imports_of(f, files[f], own) for f in order},
        "remove_from_template": ["frontend.cl.jac"],
        "verify": text["verify"],
    }
    return {"request": text["request"], "shadcn": ui, "retheme": shad, "order": order,
            "why": {f: text.get("write_reasoning", {}).get(f, text["why"][f]) for f in order},
            "plan_json": json.dumps(plan, indent=2), "plan_summary": text["plan_summary"],
            "plan_reasoning": text["plan_reasoning"], "plan_call_reasoning": text["plan_call_reasoning"],
            "journal": text["journal"], "final": text["final"], "browser": text["browser"]}


def replay(name: str, app: Path) -> Path:
    """One app through verification_runner with harness_replay.py as the model; returns the run dir."""
    run = OUT_DIR / "runs" / name
    subprocess.run(["rm", "-rf", str(run)], check=True)
    (run / "scenario").mkdir(parents=True)
    spec = build_spec(app, json.loads((TEXT_DIR / f"{name}.text.json").read_text()))
    (run / "spec.json").write_text(json.dumps(spec, indent=1))
    (run / "scenario/stage_1.md").write_text(spec["request"] + "\n")
    (run / "scenario/manifest.json").write_text(json.dumps({"scenario_id": f"ui_{name}", "sentinel": False,
                                                            "stages": ["stage_1.md"]}, indent=2))
    server = subprocess.Popen([sys.executable, str(REPLAY), "--app", str(app), "--spec", str(run / "spec.json"),
                               "--out", str(run), "--port", str(PORT)])
    time.sleep(1)
    env = {**os.environ, "PATH": f"{JAC_BIN}:{AGENT_BIN}:{os.environ['PATH']}", "AGENT_BROWSER_ARGS": "--no-sandbox",
           "OPENAI_API_KEY": "replay", "OPENAI_BASE_URL": f"http://127.0.0.1:{PORT}/v1",
           "OPENAI_API_BASE": f"http://127.0.0.1:{PORT}/v1",   # jac 0.34.28 ignores [byllm.model] base_url
           "JACCODER_TRACK_COST": "1", "JACCODER_WEB_MODE": "1", "JACCODER_AUTONOMOUS_MODE": "1"}
    try:
        with (run / "run.log").open("w") as log:
            subprocess.run(["systemd-run", "--user", "--quiet", "--collect", "--wait", "--pipe", f"--unit=ui-replay-{name}-{int(time.time())}",
                            "-p", f"MemoryMax={MEMORY_MAX}", "-p", "MemorySwapMax=0", "--same-dir",
                            *[f"--setenv={k}={v}" for k, v in env.items() if k in ("PATH", "AGENT_BROWSER_ARGS", "HOME") or k.startswith(("OPENAI", "JACCODER"))],
                            "bwrap", "--unshare-pid", "--die-with-parent", "--dev-bind", "/", "/", "--proc", "/proc",
                            "jac", "run", "evaluation/verification_runner/runner.jac", "--",
                            "--scenario", str(run / "scenario"), "--output-dir", str(run / "runner"),
                            "--run-id", f"replay-{name}", "--model", "openai/local", "--template", "empty", "--trigger", "manual"],
                           cwd=JACBUILDER, env=env, stdout=log, stderr=subprocess.STDOUT)
    finally:
        server.terminate()
        server.wait()
    return run


def sub_all(x, pairs: list[tuple[str, str]]):
    if isinstance(x, str):
        for a, b in pairs:
            x = x.replace(a, b)
        return x
    if isinstance(x, list):
        return [sub_all(v, pairs) for v in x]
    return {k: sub_all(v, pairs) for k, v in x.items()} if isinstance(x, dict) else x


def parse_sse(s: str) -> dict:
    out = {"content": "", "reasoning": "", "calls": {}}
    for line in s.splitlines():
        if not line.startswith("data: {"):
            continue
        for ch in json.loads(line[6:]).get("choices", []):
            d = ch.get("delta", {})
            out["content"] += d.get("content") or ""
            out["reasoning"] += d.get("reasoning_content") or ""
            for t in d.get("tool_calls") or []:
                e = out["calls"].setdefault(t["index"], {"id": "", "name": "", "args": ""})
                e["id"] = t.get("id") or e["id"]
                e["name"] += t.get("function", {}).get("name") or ""
                e["args"] += t.get("function", {}).get("arguments") or ""
    return out


def save_image(url: str, img_dir: Path) -> str:
    raw = base64.b64decode(url.split(",", 1)[1])
    path = img_dir / (hashlib.sha256(raw).hexdigest() + ".png")
    path.write_bytes(raw)
    return str(path.relative_to(ROOT))


def note_primitive_errors(msgs: list[dict]) -> None:
    """A page error raised inside an installed shadcn primitive (components/ui/) is not the app's code: the reply
    after it says so instead of moving on silently (the scripted turn did not see it coming)."""
    for i, m in enumerate(msgs):
        text = m["content"] if isinstance(m["content"], str) else m["content"][0]["text"]
        hit = PRIM_ERR.search(text) if m["role"] == "tool" else None
        nxt = next((x for x in msgs[i + 1:] if x["role"] == "assistant"), None)
        if hit and nxt is not None:
            nxt["reasoning_content"] = (f"The page error is React's ref warning from {hit.group(1)} in the installed "
                                        f"{hit.group(2)}.jac primitive, not from this app's code, and the step itself "
                                        f"worked. Moving on. " + nxt["reasoning_content"])


def unify_final(msgs: list[dict]) -> list[dict]:
    """finish_tool's final_output becomes the plain-text reply, as clean.py does; what follows it goes."""
    for i, m in enumerate(msgs):
        fin = [t for t in m.get("tool_calls", []) if t["function"]["name"] == "finish_tool"]
        if m["role"] == "assistant" and fin:
            m["content"] = (m["content"] + "\n\n" if m["content"] else "") + json.loads(fin[0]["function"]["arguments"])["final_output"]
            m["tool_calls"] = [t for t in m["tool_calls"] if t not in fin]
            if not m["tool_calls"]:
                del m["tool_calls"]
            return msgs[:i + 1]
    return msgs


def conversation(calls: list[dict], img_dir: Path) -> tuple[list[dict], str]:
    """One agent session (its last request plus the reply to it) as training messages; screenshots move into the
    tool message they belong to, as in prod rows."""
    req = calls[-1]["request"]
    msgs = []
    for m in req["messages"]:
        c = m.get("content")
        hit = m["role"] == "user" and isinstance(c, list) and c and RESULT_FOR.match(c[0].get("text", ""))
        if hit:
            prev = next(x for x in reversed(msgs) if x.get("tool_call_id") == hit.group(2))
            text = [{"type": "text", "text": prev["content"]}] if isinstance(prev["content"], str) else prev["content"]
            prev["content"] = text + [{"type": "image", "image": save_image(p["image_url"]["url"], img_dir)}
                                      for p in c if p.get("type") == "image_url"]
            continue
        out = {"role": m["role"], "content": "".join(p.get("text", "") for p in c if p.get("type") == "text")
               if isinstance(c, list) else c or ""}
        if m["role"] == "assistant":
            out["reasoning_content"] = m.get("reasoning_content") or ""
            if m.get("tool_calls"):
                out["tool_calls"] = [{"id": t["id"], "type": "function", "function": t["function"]} for t in m["tool_calls"]]
            out["weight"] = 1
        if m["role"] == "tool":
            out["tool_call_id"] = m["tool_call_id"]
        msgs.append(out)
    r = parse_sse(calls[-1]["response"])
    last = {"role": "assistant", "content": r["content"], "reasoning_content": r["reasoning"], "weight": 1}
    if r["calls"]:
        last["tool_calls"] = [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["args"]}}
                              for c in r["calls"].values()]
    msgs.append(last)
    note_primitive_errors(msgs)
    return unify_final(msgs), json.dumps(req["tools"])


def app_rows(name: str, run: Path, img_dir: Path) -> list[dict]:
    """The main and planner rows of one run, with the local project path and preview URL made prod-shaped."""
    calls = [json.loads(l) for l in (run / "calls.jsonl").open()]
    main = [c for c in calls if c["role"] == "main"]
    root = re.search(r"Working directory: ([^\s\\']+)", json.dumps(main[0]["request"]["messages"][1])).group(1)
    pairs = [(root, f"/app/.jachome/.jac-ide/projects/{uuid.uuid4()}/prj_{uuid.uuid4().hex}"),
             (str(HARNESS_DIR), "/app/.jachome/.jac-ide/projects")]
    port = re.search(r"Page: http://localhost:(\d+)", json.dumps(main[-1]["request"]))
    if port:
        pairs.append((f"http://localhost:{port.group(1)}", f"https://preview-jac-sbx-{uuid.uuid4().hex}.jachammer.app"))
    sessions, planner = {"main": main}, []
    for c in calls:
        if c["role"] == "planner":
            if len(c["request"]["messages"]) <= 2:
                planner.append([])
            planner[-1].append(c)
    sessions |= {f"planner{i}" if i else "planner": p for i, p in enumerate(planner)}
    rows = []
    for agent, session in sessions.items():
        msgs, tools = conversation(session, img_dir)
        msgs = sub_all(msgs, pairs)
        tool_texts = [m["content"] if isinstance(m["content"], str) else m["content"][0]["text"] for m in msgs if m["role"] == "tool"]
        rows.append({"messages": msgs, "tools": tools, "meta": {
            "source": SOURCE, "format": "trajectory", "class": "agent", "task_type": TASK_TYPE,
            "fp": f"ui-replay-{name}#{agent}", "app": name, "agent": agent.rstrip("0123456789"),
            "images": sum(1 for m in msgs if isinstance(m["content"], list) for p in m["content"] if p["type"] == "image"),
            "trainable_replies": sum(1 for m in msgs if m["role"] == "assistant" and m.get("weight")),
            "flagged_results": sum(1 for t in tool_texts if FLAG.search(t))}})
    return rows


def produce(names: list[str], rows_only: bool) -> None:
    img_dir = OUT_DIR / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    found = apps()
    for name in names:
        if not rows_only:
            run = replay(name, found[name])
            problems = [l for l in (run / "replay.log").read_text().splitlines() if l.startswith("!!")]
            print(f"{name}: {len(problems)} problem(s)" + "".join(f"\n  {p[:200]}" for p in problems))
    rows = [r for name in found if (OUT_DIR / "runs" / name / "calls.jsonl").exists()
            for r in app_rows(name, OUT_DIR / "runs" / name, img_dir)]
    with (OUT_DIR / "train.jsonl").open("w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    for r in rows:
        m = r["meta"]
        print(f'{m["fp"]:34s} replies {m["trainable_replies"]:3d} images {m["images"]:2d} flagged {m["flagged_results"]}')
    print(f"{len(rows)} rows -> {OUT_DIR / 'train.jsonl'}")


# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("apps", nargs="*", help="app names (default: all)")
    cli.add_argument("--rows-only", action="store_true", help="only rewrite rows from existing runs")
    a = cli.parse_args()
    produce(a.apps or list(apps()), a.rows_only)
