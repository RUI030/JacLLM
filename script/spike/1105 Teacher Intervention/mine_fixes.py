"""Debugging rows mined from episodes: a broken .jac file and its `jac check` errors -> the call that fixed it.

For every file whose write/edit failed `jac check` and was later written or edited so that it passed, one short row:
the task, the failing state as a write_code (weight 0), its error result, then the fixing turn (weight 1, the
student's or the teacher's; visible text and tool calls, no reasoning: the student's reasoning referred to context
the row does not have) and its OK result. File contents are replayed from the journal, so an edit_code fix applies to
exactly the text shown.

A fix that adds a name imported from another workspace module first gets an evidence turn (weight 1): list_files of
the .jac modules and find_symbol for each added name (a known symbol name: the tool's own description says to use
it before grep), run on the replayed workspace. The row is kept only if every
name has one definition, in the module the fix imports it from, so the trained edit follows from a checked location
rather than a guess. An edit fix then cites that location; a whole-file rewrite keeps its own text.

    python mine_fixes.py [--episodes <dir>] [--out <file.jsonl>]
"""

import argparse, collections, hashlib, json, re, tempfile
from pathlib import Path

from spike_utils import OUT_ROOT, WS, JAC_VERSION, SUPPORT, load_task, prompt, tools
from export import CJK, scrubbed
from workspace import SCRATCH, Workspace, jac_cli

# Setting =================================================
SOURCE    = "spike-teacher-intervention"
TASK_TYPE = "jac_fix"
MAX_FILE  = 12000              # chars: a broken file longer than this makes a long row; skip it
MAX_LOOKUPS = 3                # find_symbol calls in one lookup turn
IMPORT    = re.compile(r"import from (\.*[\w.]*)\s*\{([^}]*)\}")
DEFINED   = re.compile(r"(?m)^(\w+) (\w+) \(([^:\s]+):(\d+)\)$")    # find_symbol: "obj Post (models.jac:7)"
DEF_KINDS = "def|obj|node|edge|walker|enum|class|glob"                 # top-level definitions a grep_search looks for
GREPPED   = re.compile(r"(?m)^(\S+?\.jac):(\d+):(\w+)(?::\w+)?\s+(\w+)")   # grep_search: "<path>:7:obj Post {"
SAID      = ["Let me check the module list and where {said} {be} defined.",   # evidence turn text, one per name set
             "I'll list the .jac modules and look up {said} with find_symbol.",
             "First the module list, then find_symbol for {said}."]


# Functions ===============================================
def args_of(call: dict) -> dict:
    a = call["function"]["arguments"]
    return json.loads(a) if isinstance(a, str) else a


def abs_path(p: str) -> str:
    return p if p.startswith("/") else f"{WS}/" + p.removeprefix("./")


def tool_texts(ep: Path) -> dict[str, str]:
    """tool_call_id -> full tool result text (the journal keeps only 4,000 chars)."""
    out = {}
    for f in ep.glob("messages_build_s*.json"):
        for m in json.loads(f.read_text()):
            if m["role"] == "tool":
                out[m["tool_call_id"]] = m["content"]
    return out


def turn_of(journal: list[dict]) -> dict[str, dict]:
    """tool_call_id -> the assistant message that made it."""
    out = {}
    for r in journal:
        if r["kind"] == "turn":
            for c in r["message"].get("tool_calls", []):
                out[c["id"]] = r["message"]
    return out


def imported(text: str) -> set[tuple[str, str]]:
    """(module, name) of every `import from m { a, b as c }` in a file."""
    return {(m, n.split(" as ")[0].strip()) for m, names in IMPORT.findall(text)
            for n in names.split(",") if n.strip()}


def module_files(importer: str, module: str) -> set[str]:
    """Workspace-relative .jac paths `module` can mean in /workspace/<importer>: relative to the importing file's
    directory, or to the project root when it has no leading dots."""
    dots = len(module) - len(module.lstrip("."))
    parts = [x for x in module.lstrip(".").split(".") if x]
    here = Path(importer).relative_to(WS).parent
    if dots > 1 and dots - 2 >= len(here.parents):
        return set()                    # climbs above /workspace
    bases = [here.parents[dots - 2] if dots > 1 else here] if dots else [here, Path()]
    return {str(b.joinpath(*parts)).removeprefix("./") + ext for b in bases for ext in (".jac", ".cl.jac", ".sv.jac")}


def call(i: str, tool: str, **args) -> dict:
    return {"id": i, "type": "function", "function": {"name": tool, "arguments": json.dumps(args)}}


def evidence_turn(root: Path, names: list[str], content: str) -> tuple[dict, list[str], dict[str, tuple | None]]:
    """The trained check before an import fix: the module list (list_files) and find_symbol for each name, run on the
    workspace at `root`. Returns the turn, its results, and name -> (kind, workspace file, line) of its definition,
    None when find_symbol finds no definition."""
    ws = Workspace(root)
    calls = [call("call_e0", "list_files", directory=WS, pattern="**/*.jac")]
    calls += [call(f"call_e{i + 1}", "find_symbol", name=n, directory=WS) for i, n in enumerate(names)]
    results = [ws.list_files(WS, "**/*.jac").text] + [ws.find_symbol(n, WS).text for n in names]
    found = {}
    for n, out in zip(names, results[1:]):
        hits = [(k, f"{WS}/{f}", int(ln)) for k, name, f, ln in DEFINED.findall(out) if name == n]
        found[n] = hits[0] if len(hits) == 1 else None if not hits else "ambiguous"
    results = [ws.shown(t) for t in results]   # `root` is often a temp replay dir (before 2026-11-07 it showed as /tmp/mine-*)
    return {"role": "assistant", "content": content, "tool_calls": calls, "weight": 1}, results, found


def definitions_like(root: Path, stem: str, path: str) -> tuple[dict, str, list[tuple]]:
    """grep_search of one module for top-level definitions whose name starts with `stem`: the lookup when the exact
    name has no definition (find_symbol found nothing), so only part of the name is known. Returns the call, its
    result, and (kind, workspace file, line, name) per hit."""
    ws = Workspace(root)
    pattern = rf"^({DEF_KINDS})(:\w+)?\s+{stem}\w*\b"
    folder, name = path.rsplit("/", 1)             # grep of a directory names the file on every match line
    text = ws.grep_search(pattern, folder, name).text
    hits = [(k, f"{WS}/" + Path(f).resolve().relative_to(ws.root).as_posix(), int(ln), n)
            for f, ln, k, n in GREPPED.findall(text) if Path(f).name == name]
    return call("call_g", "grep_search", pattern=pattern, path=folder, file_pattern=name), ws.shown(text), hits


def check_text(names: list[str]) -> str:
    said = " and ".join(f"`{n}`" for n in names)
    pick = SAID[int(hashlib.sha1(said.encode()).hexdigest(), 16) % len(SAID)]
    return pick.format(said=said, be="is" if len(names) == 1 else "are")


def lookup_turn(root: Path, importer: str, pairs: list[tuple[str, str]],
                content: str = "") -> tuple[dict, list[str], dict] | None | bool:
    """The evidence turn for names a fix imports from workspace modules (mined rows). None when no name comes from a
    workspace module (nothing to look up); False when the evidence does not confirm every module (a guessed
    import) or there are more than MAX_LOOKUPS names; else (turn, results, name -> (kind, file, line))."""
    local = sorted((m, n) for m, n in pairs if any((root / f).is_file() for f in module_files(importer, m)))
    if not local:
        return None
    if len(local) > MAX_LOOKUPS:
        return False
    names = [n for _, n in local]
    text = f"{content.strip()} {check_text(names)}" if content.strip() else check_text(names)
    turn, results, found = evidence_turn(root, names, text)
    for m, n in local:
        hit = found[n]
        if not isinstance(hit, tuple) or hit[1].removeprefix(WS + "/") not in module_files(importer, m):
            return False
    return turn, results, found


def at(hit: tuple) -> str:
    """(kind, file, line) -> "`/workspace/models.jac:11` (node)"."""
    return f"`{hit[1]}:{hit[2]}` ({hit[0]})"


def located(found: dict[str, tuple]) -> str:
    """Visible text of an import fix after the evidence turn: where find_symbol found each name."""
    said = [f"`{n}` defined at {at(h)}" for n, h in found.items()]
    them = "it" if len(said) == 1 else "them"
    return "find_symbol shows " + (" and ".join(said) if len(said) < 3 else "; ".join(said)) + f", so I'll import {them} from there."


def replayed(files: dict[str, str], path: str, content: str, d: Path) -> Path:
    """Write the replayed .jac files (with `path` as `content`) under d/workspace; returns that root."""
    root = d / "workspace"
    for f, text in {**files, path: content}.items():
        if f.endswith(".jac") and f.startswith(WS + "/"):
            q = root / Path(f).relative_to(WS)
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_text(text)
    return root


def rows_of(ep: Path) -> list[dict]:
    summary = json.loads((ep / "summary.json").read_text())
    journal = [json.loads(l) for l in (ep / "journal.jsonl").read_text().splitlines()]
    texts, turns = tool_texts(ep), turn_of(journal)
    task = load_task(summary["task"].removesuffix("_v1")) if (Path(__file__).parent / "tasks" /
                                                               f"{summary['task'].removesuffix('_v1')}.json").exists() else None
    files: dict[str, str] = {}          # replayed workspace .jac contents (only what tool calls wrote)
    broken: dict[str, dict] = {}        # path -> the last failing write/edit on it: content shown + its call/result
    rows, root = [], (ep / "workspace").resolve()
    for r in journal:
        if r["kind"] != "tool_result":
            continue
        call, a = r["call"], args_of(r["call"])
        name = call["function"]["name"]
        if name not in ("write_code", "edit_code") or "file_path" not in a:
            continue
        path = abs_path(a["file_path"])
        before = files.get(path)
        if name == "write_code":
            files[path] = a.get("content", "")
        elif r["fail_kind"] not in ("edit_mismatch", "not_found", "noop_edit", "bad_call") and before is not None:
            old, new = a.get("old_string", ""), a.get("new_string", "")
            files[path] = before.replace(old, new) if a.get("replace_all") else before.replace(old, new, 1)
        if not path.endswith(".jac") or not path.startswith(WS + "/"):
            continue
        if r["failed"] and r["fail_kind"] == "jac_errors":
            result = texts.get(call["id"], r.get("text", ""))
            # the row shows this state as a write_code, so its result reads as one: "OK: x.jac (N lines)"
            result = re.sub(r"^OK: (\S+) \(\d+ edits?\)", lambda m: f"OK: {m.group(1)} ({len(files[path].splitlines())} lines)",
                            result)
            broken[path] = {"content": files[path], "result": result}
            continue
        if r["failed"] or path not in broken:
            continue
        if SCRATCH.match(Path(path).name) or "scratch" in Path(path).parts[:-1]:
            broken.pop(path)
            continue                    # a probe file the task ends by deleting; its fix teaches nothing lasting
        b, fix = broken.pop(path), turns.get(call["id"])
        if fix is None or len(b["content"]) > MAX_FILE:
            continue
        if name == "edit_code" and a.get("old_string", "") not in b["content"]:
            continue                    # replay drifted from the real file; the row would not apply
        fix_calls = fix.get("tool_calls", [])
        results = [texts.get(c["id"]) for c in fix_calls]
        if any(t is None for t in results) or any("Fix errors before continuing" in t or t.startswith("Error")
                                                  for t in results):
            continue                    # every call of the fixing turn must have passed
        by = "teacher" if call["id"].startswith("teacher_") else "student"
        added = imported(files[path]) - imported(b["content"])
        lookup = None
        if added:
            with tempfile.TemporaryDirectory(prefix="mine-") as d:
                rewrite = any(c["function"]["name"] == "write_code" for c in fix.get("tool_calls", []))
                lookup = lookup_turn(replayed(files, path, b["content"], Path(d)), path, list(added),
                                     "" if rewrite else fix.get("content", ""))
            if lookup is False:
                continue                # a workspace import the evidence does not confirm
            if lookup and not rewrite:  # the diagnosis moves to the evidence turn; the fix cites what it found
                fix = {**fix, "content": located(lookup[2])}
        rows.append(make_row(ep, task, path, b, fix, results, by, before=[lookup[:2]] if lookup else []))
    return [scrubbed(r, root) for r in rows]


def make_row(ep: Path, task: dict | None, path: str, b: dict, fix: dict, results: list[str], by: str,
             probe: tuple[str, str] | None = None, before: list[tuple[dict, list[str]]] = (),
             after: list[tuple[dict, list[str]]] = ()) -> dict:
    """`probe`: (command, output) of a run_command after the write that showed the failure (a runtime bug that
    passes `jac check`), as one more context turn before the fix. `before` / `after`: more trained turns with their
    results, between the failure and the fix (the evidence turn, a read) and after it (a verifying check)."""
    user = {"task": {k: v for k, v in (task or {}).items() if k != "source"}, "workspace": WS,
            "jac_version": JAC_VERSION, "support_files": SUPPORT}
    shown_write = {"id": "call_w", "type": "function",
                   "function": {"name": "write_code", "arguments": json.dumps({"file_path": path, "content": b["content"]})}}
    target = {"role": "assistant", "content": fix.get("content", ""), "tool_calls": fix["tool_calls"], "weight": 1}
    messages = [
        {"role": "system", "content": prompt("student_system.md")},
        {"role": "user", "content": json.dumps(user)},
        {"role": "assistant", "content": "", "tool_calls": [shown_write], "weight": 0},
        {"role": "tool", "tool_call_id": "call_w", "content": b["result"]},
        *([{"role": "assistant", "content": "", "weight": 0, "tool_calls": [{"id": "call_p", "type": "function",
            "function": {"name": "run_command", "arguments": json.dumps({"command": probe[0]})}}]},
           {"role": "tool", "tool_call_id": "call_p", "content": probe[1]}] if probe else []),
        *[m for turn, res in before for m in (turn, *answers(turn, res))],
        target, *answers(fix, results),
        *[m for turn, res in after for m in (turn, *answers(turn, res))],
    ]
    codes = sorted(set(re.findall(r"\b(E\d{4})\b", b["result"] + (probe[1] if probe else ""))))
    fp = hashlib.sha1((b["content"] + json.dumps(fix["tool_calls"], sort_keys=True)).encode()).hexdigest()[:16]
    return {"messages": messages, "tools": json.dumps(tools()),
            "meta": {"source": SOURCE, "format": "trajectory", "class": "fullstack", "task_type": TASK_TYPE,
                     "fp": fp, "episode": ep.name, "file": path, "fixed_by": by, "error_codes": codes,
                     "lookup": bool(before)}}


def answers(turn: dict, results: list[str]) -> list[dict]:
    return [{"role": "tool", "tool_call_id": c["id"], "content": t} for c, t in zip(turn["tool_calls"], results)]


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episodes", type=Path, default=OUT_ROOT / "sets/all",
                    help="training episodes only: never the held-out comparison runs")
    ap.add_argument("--out", type=Path, default=OUT_ROOT / "sft/debug_mined/train.jsonl")
    a = ap.parse_args()
    jac_cli.start_pg()                  # find_symbol runs `jac run` (CLAUDE.md: postmaster outside any scope)
    rows, seen = [], set()
    for ep in sorted(a.episodes.iterdir()):
        if not (ep / "summary.json").exists():
            continue
        for r in rows_of(ep):
            text = json.dumps(r["messages"], ensure_ascii=False)
            if r["meta"]["fp"] in seen or CJK.search(text):
                continue
            seen.add(r["meta"]["fp"])
            rows.append(r)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    by = collections.Counter(r["meta"]["fixed_by"] for r in rows)
    codes = collections.Counter(c for r in rows for c in r["meta"]["error_codes"])
    print(f"{len(rows)} rows -> {a.out}\nfixed by {dict(by)}, with a lookup turn {sum(r['meta']['lookup'] for r in rows)}"
          f"\ntop codes {codes.most_common(10)}")
