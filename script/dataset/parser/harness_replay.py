"""Scripted OpenAI-compatible model for JacHammer's jac_coder: replays a known-good build of one app through the real harness.

Only the assistant turns are scripted (from a spec built by dataset/sft/ui_apps.py); every tool result, check, preview
state and screenshot comes from the harness itself. Each exchange is appended to <out>/calls.jsonl and a progress log
to <out>/replay.log (lines starting "!!" are problems: a blocked write, a check error, a script error).

    python script/dataset/parser/harness_replay.py --app <app dir> --spec <spec.json> --out <dir> [--port 8080]
"""

import argparse, difflib, json, re, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Setting =================================================
TEMPLATE_UI = {"button", "card", "skeleton"}                       # primitives JacHammer's empty template ships
SKIP        = {".jac", "node_modules", "dist", ".pytest_cache", ".jaccoder"}
KEEP        = {"AGENTS.md", "README.md", ".gitignore"}             # template files the replay never rewrites
OVERLAY     = re.compile(r"\[plugin:|Failed to (fetch|resolve)|Can't resolve|vite-error-overlay")
REF         = re.compile(r'^\s*- (\w+) "((?:[^"\\]|\\.)*)"[^\n]*?\[[^\]\n]*?\bref=(e\d+)[^\]\n]*\]', re.M)
FIELD_ROLES = ("textbox", "searchbox", "combobox", "spinbutton")
CLICK_ROLES = ("link", "button", "checkbox", "tab", "radio", "switch", "option", "menuitem", "combobox")
SKILLS      = ("jac-cl-organization", "jac-fullstack-patterns")    # build step 5: loaded before the first file


# Functions ===============================================
def call(tool: str, **args) -> dict:
    return {"id": "call_" + uuid.uuid4().hex[:24], "type": "function",
            "function": {"name": tool, "arguments": json.dumps(args)}}


def reply(reasoning: str = "", content: str = "", calls=()) -> dict:
    return {"reasoning": reasoning, "content": content, "calls": list(calls)}


def sse(r: dict) -> str:
    """A reply as llama-server streams it (reasoning_content, then content, then tool calls)."""
    cid = "chatcmpl-" + uuid.uuid4().hex[:24]
    out = []
    def chunk(delta, finish=None, choices=True):
        body = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": "local",
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}] if choices else []}
        if not choices:
            body["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        out.append("data: " + json.dumps(body))
    chunk({"role": "assistant", "content": None})
    if r["reasoning"]:
        chunk({"reasoning_content": r["reasoning"]})
    if r["content"]:
        chunk({"content": r["content"]})
    for i, c in enumerate(r["calls"]):
        chunk({"tool_calls": [{"index": i, "id": c["id"], "type": "function", "function": c["function"]}]})
    chunk({}, "tool_calls" if r["calls"] else "stop")
    chunk({}, choices=False)
    out.append("data: [DONE]")
    return "\n\n".join(out) + "\n\n"


def text_of(m: dict) -> str:
    c = m.get("content")
    if isinstance(c, list):
        return "\n".join(p.get("text", "") for p in c if p.get("type") == "text")
    return c or ""


def last_tool_texts(req: dict) -> list[str]:
    """Tool results after the last assistant message."""
    out = []
    for m in reversed(req["messages"]):
        if m["role"] == "assistant":
            break
        if m["role"] == "tool":
            out.append(text_of(m))
    return out[::-1]


def role_of(req: dict) -> str:
    """main agent, planner subagent, or aux (the end-of-turn reflection, which has no tools)."""
    if not req.get("tools"):
        return "aux"
    return "planner" if "PlannerAgent" in text_of(req["messages"][0]) else "main"


def find_ref(snapshot: str, pattern: str, roles) -> str:
    rx = re.compile(pattern, re.I)
    items = REF.findall(snapshot)
    for role in roles:
        for r, name, ref in items:
            if r == role and rx.search(name):
                return ref
    raise LookupError(f"no {roles} named /{pattern}/ in snapshot:\n" + snapshot[:3000])


def project_files(app: Path) -> dict[str, str]:
    out = {}
    for p in sorted(app.rglob("*")):
        rel = p.relative_to(app)
        if p.is_file() and not (set(rel.parts) & SKIP) and rel.name not in KEEP:
            out[str(rel)] = p.read_text()
    return out


def imports_of(rel: str, text: str, files: set[str]) -> list[str]:
    """Project files this file imports (relative dotted imports and `import from services.x`)."""
    deps = []
    for m in re.finditer(r'^\s*(?:sv\s+)?import\s+(?:type\s+)?from\s+(\.*)([\w.]+)\s*\{', text, re.M):
        dots, mod = m.group(1), m.group(2)
        base = Path(rel).parent if dots else Path(".")
        for _ in range(max(len(dots) - 1, 0)):
            base = base.parent
        stem = base / Path(*mod.split("."))
        deps += [str(stem) + ext for ext in (".jac", ".cl.jac") if str(stem) + ext in files]
    return deps


def write_order(files: dict[str, str]) -> list[str]:
    """Leaf-first order of the app's own .jac files: services, lib, components, pages; main.jac last with a manual
    Router, but right after services and lib with file-based routing (it imports no component then, and the harness
    blocks a pages/ write while main.jac's app() takes no children)."""
    own = {f: t for f, t in files.items() if f.endswith(".jac") and not f.startswith("components/ui/")}
    deps = {f: [d for d in imports_of(f, t, set(own)) if d != f] for f, t in own.items()}
    file_routes = any(f.startswith("pages/") for f in own)
    def rank(f):
        if f == "main.jac":
            return 1.5 if file_routes else 4
        return (0 if f.startswith("services/") else 1 if f.startswith("lib/") else
                2 if f.startswith("components/") else 3 if f.startswith("pages/") else 4)
    order, done = [], set()
    def visit(f, stack=()):
        if f in done or f in stack:
            return
        for d in sorted(deps[f], key=rank):
            visit(d, stack + (f,))
        done.add(f)
        order.append(f)
    for f in sorted(own, key=lambda f: (rank(f), f.count("/"), f)):
        visit(f)
    return order


def hunks(before: str, after: str) -> list[tuple[str, str]]:
    """Unique find/replace pairs turning before into after; changes within 12 lines of each other become one edit."""
    a, b = before.splitlines(keepends=True), after.splitlines(keepends=True)
    groups = []
    for o in (o for o in difflib.SequenceMatcher(None, a, b).get_opcodes() if o[0] != "equal"):
        if groups and o[1] - groups[-1][2] <= 12:
            groups[-1] = ("replace", groups[-1][1], o[2], groups[-1][3], o[4])
        else:
            groups.append(o)
    out = []
    for _, i1, i2, j1, j2 in groups:
        lo, hi = i1, i2
        while not ("".join(a[lo:hi]) and before.count("".join(a[lo:hi])) == 1):
            lo, hi = max(lo - 1, 0), min(hi + 1, len(a))
        out.append(("".join(a[lo:hi]), "".join(a[lo:i1]) + "".join(b[j1:j2]) + "".join(a[i2:hi])))
    return out


def planner(spec: dict):
    """The plan_build subagent: look at the template, write build_plan.json, finish."""
    req = yield
    root = spec["root"]
    req = yield reply("Look at the template before planning.", calls=[call("list_files", directory=root)])
    req = yield reply("Check the template's jac.toml and entry point.",
                      calls=[call("read_file", file_path=f"{root}/jac.toml"), call("read_file", file_path=f"{root}/main.jac")])
    req = yield reply(spec["plan_reasoning"],
                      calls=[call("write_code", file_path=f"{root}/.jaccoder/build_plan.json", content=spec["plan_json"])])
    yield reply("The plan is written.", calls=[call("finish_tool", final_output=spec["plan_summary"])])


def main_agent(spec: dict, app: Path, log):
    """The main agent, following the harness system prompt's build steps 1-12."""
    req = yield
    root = re.search(r"Working directory: (\S+?)(?:\\n|\n)", text_of(req["messages"][1])).group(1)
    spec["root"] = root
    disk, final = Path(root), project_files(app)
    req = yield reply("Start by looking at what the workspace already has.", calls=[call("list_files", directory=root)])
    listing = last_tool_texts(req)[0]
    req = yield reply("A Jac project is already here, so I extend it. Read the config, the entry point and the client "
                      "entry it imports.",
                      calls=[call("read_file", file_path=f"{root}/{f}") for f in ("jac.toml", "main.jac", "frontend.cl.jac")])
    task = f"{spec['request']}\n\nDirectory listing:\n{listing}\n\njac.toml:\n{(disk / 'jac.toml').read_text()}"
    req = yield reply(spec["plan_call_reasoning"], calls=[call("plan_build", task=task)])
    req = yield reply("Before the first file, load the two guides build step 5 names: file layout and extensions, and how "
                      "main.jac wires routes, services and CSS on this release.",
                      calls=[call("load_jac_skill", name=s) for s in SKILLS])
    if spec["shadcn"]:                           # an app that only uses the template's button and card installs nothing
        req = yield reply("Pre-flight: install the shadcn components the plan uses.",
                          calls=[call("run_command", command="jac install --shadcn " + " ".join(spec["shadcn"]), workdir=root)])
    t = spec["retheme"]
    req = yield reply(f"Apply the theme from the plan: {t['style']} style, {t['baseColor']} base, {t['theme']} accent, {t['font']}.",
                      calls=[call("run_command", workdir=root, command=(
                          f"jac retheme --style {t['style']} --baseColor {t['baseColor']} --theme {t['theme']} "
                          f"--font {t['font']} --radius {t['radius']} --menuAccent {t['menuAccent']}"))])
    for old, new in hunks((disk / "jac.toml").read_text(), final["jac.toml"]):
        req = yield reply("Give the page its own title and description in jac.toml.",
                          calls=[call("edit_code", file_path=f"{root}/jac.toml", old_string=old, new_string=new)])
        log(f"jac.toml edit: {last_tool_texts(req)[0][:200]}")
    # retheme adds the font's npm package; without an install the preview shows Vite's "Can't resolve" overlay
    req = yield reply("jac.toml is final (retheme added the font package), so install the npm dependencies now.",
                      calls=[call("run_command", command="jac install", workdir=root, timeout=600)])
    if (disk / "styles/global.css").read_text() != final["styles/global.css"]:
        req = yield reply("Add the app's own styles on top of the regenerated theme.",
                          calls=[call("write_code", file_path=f"{root}/styles/global.css", content=final["styles/global.css"])])
    for f, text in final.items():
        if f.startswith("components/ui/") and (not (disk / f).exists() or (disk / f).read_text() != text):
            log(f"WARN ui file differs after install/retheme: {f}")
    for f in spec["order"]:
        if (disk / f).exists() and (disk / f).read_text() == final[f]:
            continue
        req = yield reply(spec["why"].get(f, f"Next in write_order: {f}."),
                          calls=[call("write_code", file_path=f"{root}/{f}", content=final[f])])
        r = last_tool_texts(req)[0]
        log(f"write {f}: {r.splitlines()[0][:160]}")
        if "ERRORS:" in r or "error[" in r or "BLOCKED" in r:
            log(f"!! check output for {f}:\n{r[:1500]}")
        if f == "main.jac" and (disk / "frontend.cl.jac").exists() and "frontend.cl.jac" not in final:
            req = yield reply("main.jac no longer imports the template's splash screen, so delete it.",
                              calls=[call("delete_code", file_path=f"{root}/frontend.cl.jac")])
    req = yield reply("All files are written. Check that the preview picked them up.",
                      calls=[call("preview_status", wait_seconds=60)])
    log("preview: " + last_tool_texts(req)[0][:300])
    req = yield reply("Validate the running app in the browser.", calls=[call("browser_validate", url="")])
    res = last_tool_texts(req)[0]
    log("validate:\n" + res[:4000])
    if OVERLAY.search(res):
        log("!! validate shows a build error overlay")
        req = yield reply("The page shows a build error instead of the app. The dependencies changed after the preview "
                          "started, so restart it.", calls=[call("preview_restart")])
        req = yield reply("Wait for the restarted preview.", calls=[call("preview_status", wait_seconds=45)])
        req = yield reply("Validate again.", calls=[call("browser_validate", url="")])
        res = last_tool_texts(req)[0]
        if OVERLAY.search(res):
            raise RuntimeError("still an error overlay after restart")
    req = yield from core_flow(spec, req, log)
    req = yield reply("The app renders. Record this turn in the journal.",
                      calls=[call("write_code", file_path=f"{root}/.jaccoder/agent_journal.md", content=spec["journal"])])
    yield reply("Done: hand the app back with what works and the next steps.",
                calls=[call("finish_tool", final_output=spec["final"])])


def core_flow(spec: dict, req: dict, log):
    """What the browser_validate coverage block asks for: open the flow's route, run the core flow once with browser_do."""
    snap = last_tool_texts(req)[0]
    base = re.search(r"Page: (https?://[^/\s]+)", snap).group(1)
    for step in spec["browser"]:
        if "open" in step:
            req = yield reply(step["why"], calls=[call("browser_open", url=base + step["open"])])
        else:
            for _ in range(3):                   # a snapshot can be taken before the page has rendered
                try:
                    for a in step["do"]:
                        find_ref(snap, a["fill"], FIELD_ROLES) if "fill" in a else find_ref(snap, a["click"], a.get("roles", CLICK_ROLES))
                    break
                except LookupError:
                    req = yield reply("The snapshot has no controls yet, the page is still loading. Read the page state again.",
                                      calls=[call("browser_state")])
                    snap = last_tool_texts(req)[0]
            lines = []
            for a in step["do"]:
                if "fill" in a:
                    lines.append(f'fill @{find_ref(snap, a["fill"], FIELD_ROLES)} {json.dumps(a["value"])}')
                else:                            # agent-browser clicks without scrolling; focus scrolls it into view
                    ref = find_ref(snap, a["click"], a.get("roles", CLICK_ROLES))
                    lines += [f"focus @{ref}", f"click @{ref}"]
            req = yield reply(step["why"], calls=[call("browser_do", command="\n".join(lines))])
        snap = last_tool_texts(req)[0]
        log(f"browser {step.get('open') or step['why'][:40]}:\n{snap[:2500]}")
    return req


class Replay:
    """One generator per agent session; requests are answered one at a time."""
    def __init__(self, spec: dict, app: Path, out: Path):
        self.spec, self.app = spec, app
        self.lock, self.gens = threading.Lock(), {}
        self.logf = (out / "replay.log").open("a")
        self.calls = (out / "calls.jsonl").open("a")

    def log(self, s: str) -> None:
        self.logf.write(s + "\n")
        self.logf.flush()

    def answer(self, req: dict) -> dict:
        role = role_of(req)
        if role == "aux":                        # TurnReflection, an internal quality log never trained on
            return reply(content=json.dumps({"issue": "", "root_cause": "", "resolution": "", "code_before": "",
                                             "code_after": "", "smoothness": 1.0, "category": "NONE"}))
        if role == "planner" and (role not in self.gens or len(req["messages"]) <= 3):
            self.gens[role] = planner(self.spec)
            next(self.gens[role])
        if role == "main" and role not in self.gens:
            self.gens[role] = main_agent(self.spec, self.app, self.log)
            next(self.gens[role])
        try:
            return self.gens[role].send(req)
        except StopIteration:                    # after finish_tool the harness asks once more for the final answer
            return reply(content=self.spec["plan_summary"] if role == "planner" else self.spec["final"])
        except (LookupError, RuntimeError, AttributeError) as e:
            self.log(f"!! script error: {e!r}")
            return reply(content=f"Stopping: {e}")


def serve(rp: Replay, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def send(self, data: bytes, kind: str):
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self.send(json.dumps({"data": [{"id": "local", "object": "model"}]}).encode(), "application/json")

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
            with rp.lock:
                body = sse(rp.answer(req))
                rp.calls.write(json.dumps({"ts": time.time(), "role": role_of(req), "request": req, "response": body}) + "\n")
                rp.calls.flush()
            self.send(body.encode(), "text/event-stream")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--app", type=Path, required=True)
    cli.add_argument("--spec", type=Path, required=True)
    cli.add_argument("--out", type=Path, required=True)
    cli.add_argument("--port", type=int, default=8080)
    a = cli.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    serve(Replay(json.loads(a.spec.read_text()), a.app.resolve(), a.out), a.port)
