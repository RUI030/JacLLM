"""Does a finished web app have a real frontend? `jac check` and `jac test` cannot tell: an app whose client modules
were never written, or that the runtime never mounts, still passes both. The checks follow the jac skills
(jac-fullstack-patterns, jac-codespaces) and run on a copy of the workspace:

1. entry      jac.toml `[project] entry-point` (default main.jac) exists
2. app        the entry module exports `def:pub app` (the runtime mounts that literal name), placed client by
              `jac check --placements`
3. compiles   `jac build --as source` emits frontend JS modules, and `node --check` accepts each one
4. elements   every lowercase JSX tag in the compiled JS is an HTML or SVG element; every capitalized one is imported
              or defined in its module
5. bundled    every .jac module that returns JSX is in the emitted frontend (imported, directly or not, by the entry)
6. routing    with file-based routing (a pages/ module returns JsxPage), `app` takes the router tree as a parameter and
              renders it (an `app` that ignores it drops every route silently), and no manual <Router> is mixed in
              (jac-cl-routing)

npm dependencies are only listed: the harness has no network, so their versions are not resolved here.

    python frontend_check.py <workspace> [<workspace> ...] [--json]
"""

import argparse, json, re, shutil, subprocess, sys, tempfile, tomllib
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli

# Setting =================================================
TIMEOUT  = 300
SKIP     = {".jac", "node_modules", "__pycache__", ".git", "dist"}
HTML     = set("""a abbr address area article aside audio b base bdi bdo blockquote body br button canvas caption cite
code col colgroup data datalist dd del details dfn dialog div dl dt em embed fieldset figcaption figure footer form h1 h2
h3 h4 h5 h6 head header hgroup hr html i iframe img input ins kbd label legend li link main map mark menu meta meter nav
noscript object ol optgroup option output p picture pre progress q rp rt ruby s samp script search section select slot
small source span strong style sub summary sup table tbody td template textarea tfoot th thead time title tr track u ul
var video wbr svg path circle rect line polyline polygon ellipse g text tspan defs use symbol marker clipPath mask
linearGradient radialGradient stop pattern image foreignObject""".split())
JSX_TAG  = re.compile(r'__jacJsx\(\s*(?:"([^"]+)"|([A-Za-z_$][\w$.]*))')
RETURNS_JSX = re.compile(r"->\s*Jsx(Element|Page|Layout)|return\s*\(?\s*<[A-Za-z]")
APP_PARAM = re.compile(r"(?m)^\s*def:pub\s+app\s*\(\s*(\w+)")
PLACED   = re.compile(r"(?m)^\s+(\w+) \((\w+)\)\s+(client|server|native|dual)\s*$")


# Functions ===============================================
def entry_of(root: Path) -> str:
    p = root / "jac.toml"
    try:
        project = tomllib.loads(p.read_text()).get("project", {}) if p.is_file() else {}
    except tomllib.TOMLDecodeError:
        project = {}
    return project.get("entry-point", "main.jac")


def npm_deps(root: Path) -> dict:
    try:
        return tomllib.loads((root / "jac.toml").read_text()).get("dependencies", {}) if (root / "jac.toml").is_file() else {}
    except tomllib.TOMLDecodeError:
        return {}


def placements(root: Path, entry: str) -> dict[str, str]:
    """name -> codespace of every declaration `jac check --placements` reports for the entry's program."""
    res = jac_cli.execute(["check", "--placements", entry], timeout=TIMEOUT, cwd=root, merge_stderr=True)
    return {name: space for name, _, space in PLACED.findall(res.stdout)}


def element_problems(js: Path) -> list[str]:
    text, out = js.read_text(errors="replace"), []
    for tag, comp in JSX_TAG.findall(text):
        if tag and tag[0].islower() and tag not in HTML and "-" not in tag:
            out.append(f"{js.stem}: <{tag}> is not an HTML or SVG element")
        name = (comp or "").split(".")[0]
        if name and name[0].isupper() and not re.search(
                rf"\bimport\b[^;]*\b{re.escape(name)}\b|\b(?:function|const|let|class)\s+{re.escape(name)}\b", text):
            out.append(f"{js.stem}: <{comp}> is neither imported nor defined")
    return sorted(set(out))


def routing_problems(root: Path, entry: str) -> list[str]:
    pages = root / "pages"
    routes = [p for p in pages.rglob("*.jac") if re.search(r"->\s*JsxPage", p.read_text(errors="replace"))] \
        if pages.is_dir() else []
    if not routes:
        return []
    out, text = [], (root / entry).read_text(errors="replace") if (root / entry).is_file() else ""
    m = APP_PARAM.search(text)
    if not m:
        out.append(f"pages/ has routes but `app` in {entry} takes no children parameter, so every route is dropped")
    elif not re.search(rf"\b{m.group(1)}\b", text[m.end():]):
        out.append(f"`app` in {entry} does not render its `{m.group(1)}` parameter, so every route is dropped")
    mixed = [str(p.relative_to(root)) for p in root.rglob("*.jac") if not SKIP & set(p.relative_to(root).parts)
             and "<Router" in p.read_text(errors="replace")]
    if mixed:
        out.append(f"pages/ routing mixed with a manual <Router> in {', '.join(mixed)}")
    return out


def check(workspace: Path) -> dict:
    """{check name: list of problems} plus facts, for one workspace."""
    src = workspace.resolve()
    with tempfile.TemporaryDirectory(prefix="fe-") as d:
        root = Path(d) / "app"
        shutil.copytree(src, root, ignore=shutil.ignore_patterns(*SKIP))
        entry = entry_of(root)
        r = {"entry": entry, "npm": npm_deps(root), "problems": {}}
        bad = lambda k, *msg: r["problems"].setdefault(k, []).extend(msg)
        if not (root / entry).is_file():
            # the rest is still checked on a module that exports `app`, to tell miswiring from a missing frontend
            other = next((p for p in sorted(root.rglob("*.jac")) if not SKIP & set(p.relative_to(root).parts)
                          and re.search(r"(?m)^\s*def:pub\s+app\s*(\(|->)", p.read_text(errors="replace"))), None)
            bad("entry", f"entry-point {entry} does not exist" + (f" (checked {other.relative_to(root)} instead)"
                                                                 if other else ""))
            if other is None:
                return r
            entry = r["checked_as_entry"] = str(other.relative_to(root))
            toml = root / "jac.toml"                # jac build reads the entry from jac.toml, so point it there
            text = toml.read_text() if toml.is_file() else ""
            text = re.sub(r'(?m)^entry-point\s*=.*$', f'entry-point = "{entry}"', text) if "entry-point" in text \
                else re.sub(r"(?m)^\[project\]\s*$", f'[project]\nentry-point = "{entry}"', text) if "[project]" in text \
                else f'[project]\nname = "app"\nversion = "0.1.0"\nentry-point = "{entry}"\n\n' + text
            toml.write_text(text)
        if not re.search(r"(?m)^\s*def:pub\s+app\s*(\(|->)", (root / entry).read_text(errors="replace")):
            bad("app", f"{entry} has no `def:pub app` (the runtime mounts the literal name `app`)")
        elif placements(root, entry).get("app") != "client":
            bad("app", f"`app` in {entry} is not placed client (no JSX in its body?)")
        bad("routing", *routing_problems(root, entry))
        res = jac_cli.execute(["build", "--as", "source", "-o", "out", entry], timeout=TIMEOUT, cwd=root,
                              merge_stderr=True)
        src = root / "out/frontend/src"                       # a module in a package is emitted under its folder
        js = sorted(p for p in src.rglob("*.js") if not p.name.startswith("__")) if src.is_dir() else []
        frontend_only = "no server-side Python to emit" in res.stdout   # the build still emitted the frontend
        if not js or not (res.ok or frontend_only):
            bad("compiles", "jac build --as source emitted no frontend JS"
                + (f": {res.stdout.strip().splitlines()[-1][:200]}" if res.stdout.strip() else ""))
        for p in js:
            n = subprocess.run(["node", "--check", str(p)], capture_output=True, text=True, timeout=60)
            if n.returncode:
                err = n.stderr.strip().splitlines()
                why = next((l for l in err if "Error" in l), "failed")
                code = err[1].strip() if len(err) > 1 else ""     # the offending JS line, after "<file>:<line>"
                bad("compiles", f"{p.name}: node --check: {why[:120]} at `{code[:80]}`")
            bad("elements", *element_problems(p))
        emitted = {p.relative_to(src).with_suffix("").as_posix() for p in js}
        jsx_mods = sorted(str(p.relative_to(root)) for p in root.rglob("*.jac")
                          if not SKIP & set(p.relative_to(root).parts) and not p.name.endswith((".test.jac", ".impl.jac"))
                          and not p.name.startswith("test_") and RETURNS_JSX.search(p.read_text(errors="replace")))
        if js:
            bad("bundled", *[f"{m} returns JSX but is not in the frontend bundle" for m in jsx_mods
                             if Path(m).with_suffix("").as_posix() not in emitted])
        r["js_modules"], r["jsx_modules"] = len(js), len(jsx_mods)
        r["problems"] = {k: v for k, v in r["problems"].items() if v}
        return r


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspaces", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    for w in a.workspaces:
        r = check(w)
        if a.json:
            print(json.dumps({"workspace": str(w), **r}))
            continue
        status = "OK" if not r["problems"] else "FAIL"
        print(f"{status:4s} {w}  entry={r['entry']} js={r.get('js_modules', 0)} jsx_modules={r.get('jsx_modules', 0)}")
        for k, v in r["problems"].items():
            for msg in v[:6]:
                print(f"     {k}: {msg}")
