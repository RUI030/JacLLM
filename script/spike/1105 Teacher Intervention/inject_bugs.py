"""Debugging rows from injected bugs: a .jac file that passed acceptance, broken in one way the student actually got
stuck on (analyze.py / the teacher diagnoses), with the real tool results, and the edit that restores it.

Each candidate runs through the harness tools in a copy of the episode's final workspace. Compile-time kinds: the
write_code of the broken file must fail `jac check`. Runtime kinds (import paths, `class` for `obj`) pass `jac check`,
so a `jac test` of the workspace's tests must fail after the write and pass after the restoring edit_code. Kinds that
are easy and plentiful (semicolons, docstrings) are capped so they do not crowd out the import mistakes, which were
the most common real cause. Rows have the same shape as mine_fixes.py.

Import errors (an unknown name) get a trained evidence turn first, the module list and find_symbol, and the fix
cites what it shows. When the file uses a name that is defined nowhere (misnamed: every use and the import renamed),
find_symbol finds nothing for it, and the next turn is a grep_search of the imported module for definitions that start
like it: the lookup for a name only partly known. The cases: the import is missing (drop_import, drop_name), names a symbol that does not exist
(wrong_name), uses a path that does not resolve (import_path), or the name has no definition at all (drop_def: a
definition deleted from the module another file imports it from), in which case the agent reads that module, writes
the definition, and checks the importing file again. A row is kept only if the evidence says exactly that.

    python inject_bugs.py [--episodes <dir>] [--out <file.jsonl>] [--workers 4]
"""

import argparse, collections, difflib, json, random, re, shutil, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from spike_utils import OUT_ROOT, WS, load_task
from mine_fixes import IMPORT, MAX_FILE, at, call, check_text, definitions_like, evidence_turn, make_row, module_files
from export import scrubbed
from workspace import SKIP_DIRS, Workspace, jac_cli

# Setting =================================================
SEED     = 1106
PER_FILE = {"drop_import": 3, "drop_name": 3, "wrong_name": 2, "misnamed": 2, "import_path": 3, "drop_def": 2, "obj_to_class": 2,
            "docstring_in_def": 2, "missing_semi": 2, "module_semi": 2, "return_type": 2, "jsx_close": 2}   # per file
CAP      = {"missing_semi": 40, "module_semi": 40, "docstring_in_def": 60, "drop_def": 40}   # rows per kind, whole set
RUNTIME  = {"import_path", "obj_to_class"}                                       # pass jac check, fail jac test
UNKNOWN  = ["`{name}` has an unknown type here: it is not imported, or not defined where I expect.",
            "The checker cannot resolve `{name}` in this file, so either the import is wrong or the name is missing.",
            "`{name}` is unknown here. It may be missing from an import, or defined somewhere else."]
NOTES    = {   # visible text of the fixing turn (a list: one is picked per row)
    "drop_import":      UNKNOWN,
    "drop_name":        UNKNOWN,
    "wrong_name":       UNKNOWN,
    "misnamed":         UNKNOWN,
    "import_path":      "`{bad}` passes `jac check` but does not resolve when the tests run.",
    "obj_to_class":     "`{name}` must be an `obj`, not a `class`: a `class` gets no constructor for its `has` fields.",
    "docstring_in_def": "In Jac a docstring goes before the declaration, not inside its body, so the parser stops at it. I'll move it above the def.",
    "missing_semi":     "The statement on line {line} is missing its closing `;`.",
    "module_semi":      "A `;` after a top-level block is not allowed at module level. Remove it.",
    "return_type":      "The declared return type of `{name}` does not match what it returns. Restore `-> {type}`.",
    "jsx_close":        "The `<{name}>` element is never closed. Add the missing `</{name}>`.",
}
CITED    = {   # the fix's text from the evidence turn: {hit} is the definition of {name} it found
    "drop_import": "find_symbol shows `{name}` defined at {hit}, and this file has no import from `{module}`, so the import "
                   "is missing. I'll add it back.",
    "drop_name":   "find_symbol shows `{name}` defined at {hit}, but the import from `{module}` does not list it, so I'll "
                   "add it there.",
    "wrong_name":  "find_symbol shows `{name}` defined at {hit}, and `{bad}` is not defined anywhere, so the import from "
                   "`{module}` names the wrong symbol. I'll import `{name}` instead.",
    "misnamed":    "The search shows `{name}` defined at {hit}, and nothing defines `{bad}`, so `{bad}` is a misspelling "
                   "of `{name}`. I'll rename it everywhere in this file.",
    "import_path": "find_symbol shows `{name}` defined at {hit}, so the module is `{module}`: `{good}`.",
}
FIXES    = {   # the fix's text when the module is not a workspace file (no evidence turn: stdlib, npm)
    "drop_import": "Add the import back.", "drop_name": "Add it to that import.", "import_path": "Import the module as `{good}`."}
LINE_IMPORT = re.compile(r"import from ([\w.]+) \{\s*([\w, ]+?)\s*\}\s*;?$")
TOP_DEF  = re.compile(r"(def(?::\w+)?|obj|node|edge|walker|enum)\s+(\w+)\b")


# Functions ===============================================
def mutations(text: str, rng: random.Random) -> list[tuple[str, str, dict]]:
    """(kind, broken text, note fields) for every applicable mutation, at most PER_FILE[kind] of each kind."""
    lines, out = text.split("\n"), []
    swap_line = lambda i, new: "\n".join(lines[:i] + ([new] if new is not None else []) + lines[i + 1:])
    def pick(kind, cands):
        for c in rng.sample(cands, min(PER_FILE[kind], len(cands))):
            out.append((kind, *c))
    body = "\n".join(l for l in lines if not l.lstrip().startswith("import"))
    used = lambda n: re.search(rf"\b{n}\b", body)
    imports = [(i, m) for i, l in enumerate(lines) if (m := LINE_IMPORT.match(l))]
    pick("drop_import", [(swap_line(i, None), {"name": n, "module": m.group(1)}) for i, m in imports
                         for n in [m.group(2).split(",")[0].strip()] if used(n)])
    pick("drop_name", [(swap_line(i, lines[i].replace(m.group(2), ", ".join(x for x in names if x != n))),
                        {"name": n, "module": m.group(1)})
                       for i, m in imports for names in [[x.strip() for x in m.group(2).split(",")]] if len(names) > 1
                       for n in names if used(n)])
    variant = lambda n: n + ("Node" if n[0].isupper() else "_item")
    in_braces = lambda l, n: l[:l.index("{")] + re.sub(rf"\b{n}\b", variant(n), l[l.index("{"):], count=1)
    pick("wrong_name", [(swap_line(i, in_braces(lines[i], n)),
                         {"name": n, "bad": variant(n), "module": m.group(1)})
                        for i, m in imports for n in [x.strip() for x in m.group(2).split(",")] if used(n)
                        and not re.search(rf"\b{variant(n)}\b", text)])
    pick("misnamed", [(re.sub(rf"\b{n}\b", variant(n), text), {"name": n, "bad": variant(n), "module": m.group(1)})
                      for i, m in imports for n in [x.strip() for x in m.group(2).split(",")] if used(n)
                      and not re.search(rf"\b{variant(n)}\b", text)])
    pick("import_path", [(swap_line(i, lines[i].replace(f"from {mod} ", f"from {bad} ", 1)),
                          {"bad": f"import from {bad}", "good": f"import from {mod}", "module": mod,
                           "name": m.group(2).split(",")[0].strip()})
                         for i, m in imports for mod in [m.group(1)] if not mod.startswith(".") and mod != "styles.css"
                         and "css" not in mod for bad in (f"{mod}.jac", f"..{mod}")])
    pick("obj_to_class", [(swap_line(i, l.replace("obj ", "class ", 1)), {"name": m.group(1)})
                          for i, l in enumerate(lines) if (m := re.match(r"obj (\w+)\b", l))])
    doc = lambda m: f'"""{m.group(2).replace("_", " ").capitalize()}."""'
    pick("docstring_in_def", [("\n".join(lines[:i + 1] + [re.match(r"\s*", lines[i + 1]).group(0) + doc(m)] + lines[i + 1:]),
                               {"target": "\n".join(lines[:i] + [m.group(1) + doc(m)] + lines[i:])})   # fixed: moved above
                              for i, l in enumerate(lines[:-1]) if (m := re.match(r"(\s*)def(?::\w+)?\s+(\w+)\(.*\{\s*$", l))
                              and lines[i + 1].strip() and not lines[i + 1].strip().startswith('"""')
                              and not (i and lines[i - 1].strip().startswith('"""'))])
    pick("missing_semi", [(swap_line(i, l.rstrip()[:-1]), {"line": i + 1})
                          for i, l in enumerate(lines) if re.match(r"\s+(return |\w+ = |\w+\.\w+\()", l) and l.rstrip().endswith(";")])
    pick("module_semi", [(swap_line(i, "};"), {}) for i, l in enumerate(lines) if l == "}"])
    swap = {"str": "int", "int": "str", "bool": "str", "float": "str"}
    pick("return_type", [(swap_line(i, l[:m.start(2)] + swap[m.group(2)] + l[m.end(2):]), {"name": m.group(1), "type": m.group(2)})
                         for i, l in enumerate(lines) if (m := re.match(r"\s*def(?::\w+)?\s+(\w+)\(.*\)\s*->\s*(str|int|bool|float)\s*\{", l))])
    pick("jsx_close", [(swap_line(i, None), {"name": m.group(1)})
                       for i, l in enumerate(lines) if (m := re.fullmatch(r"\s*</(\w+)>\s*", l))])
    return out


def restoring_edit(broken: str, good: str) -> tuple[str, str]:
    """(old_string, new_string): the changed lines plus enough context to be unique in the broken text."""
    b, g = broken.split("\n"), good.split("\n")
    ops = [o for o in difflib.SequenceMatcher(None, b, g, autojunk=False).get_opcodes() if o[0] != "equal"]
    i1, i2, j1, j2 = ops[0][1], ops[-1][2], ops[0][3], ops[-1][4]
    for pad in range(1, 12):
        lo, hib, hig = max(0, i1 - pad), min(len(b), i2 + pad), min(len(g), j2 + pad)
        old, new = "\n".join(b[lo:hib]), "\n".join(g[lo:hig])
        if broken.count(old) == 1:
            return old, new
    return broken, good


def tests_of(ws: Workspace) -> list[Path]:
    """The test files acceptance runs, if they pass on the unbroken workspace."""
    return [t for t in ws.test_targets() if not ws.run_command(f"jac test {t.relative_to(ws.root)}").failed]


def candidates_of(ep: Path) -> list[dict]:
    """Every verified (broken file, results, fix) in one episode's final workspace."""
    rng, rows = random.Random(f"{SEED}:{ep.name}"), []
    summary = json.loads((ep / "summary.json").read_text())
    task = load_task(summary["task"].removesuffix("_v1"))
    with tempfile.TemporaryDirectory(prefix="inject-") as d:
        root = Path(d) / "workspace"
        shutil.copytree(ep / "workspace", root, ignore=shutil.ignore_patterns(*SKIP_DIRS))
        ws = Workspace(root)
        for p in ws.scratch_files():               # probe files left by older runs are not part of the app
            p.unlink()
        files, tests = ws.jac_files(), None
        for p in files:
            good = p.read_text()
            if len(good) > MAX_FILE or ws.jac_errors(p):
                continue                           # the source itself must pass
            path = f"{WS}/{p.relative_to(root)}"
            for kind, broken, fields in mutations(good, rng):
                bad, probe = ws.write_code(path, broken), None
                if kind in RUNTIME:
                    tests = tests_of(ws) if tests is None else tests
                    if bad.failed or not tests:
                        p.write_text(good)
                        continue
                    for t in tests:
                        res = ws.run_command(f"jac test {t.relative_to(root)}")
                        if res.failed:
                            probe = (f"jac test {t.relative_to(root)}", res.text)
                            break
                    if probe is None:
                        p.write_text(good)
                        continue
                elif not (bad.failed and bad.kind == "jac_errors"):
                    p.write_text(good)
                    continue
                target = fields.pop("target", good)       # what the fix writes: the original, or a corrected form
                if kind == "misnamed":                     # the name is wrong at every use: rename it throughout
                    fix_call = call("call_fix", "edit_code", file_path=path, old_string=fields["bad"],
                                    new_string=fields["name"], replace_all=True)
                    fixed = ws.edit_code(path, fields["bad"], fields["name"], True)
                    fixed.failed = fixed.failed or p.read_text() != good
                else:
                    old, new = restoring_edit(broken, target)
                    fix_call = call("call_fix", "edit_code", file_path=path, old_string=old, new_string=new)
                    fixed = ws.edit_code(path, old, new)
                ok = not fixed.failed and (probe is None or not ws.run_command(probe[0]).failed)
                p.write_text(good)
                if not ok:
                    continue
                text = NOTES[kind] if isinstance(NOTES[kind], str) else rng.choice(NOTES[kind])
                note, before = text.format(**({**fields, "name": fields["bad"]} if kind == "misnamed" else fields)), []
                if kind in CITED:
                    local = any((root / f).is_file() for f in module_files(path, fields["module"]))
                    if not local and kind in FIXES:
                        note = f"{note} {FIXES[kind].format(**fields)}"
                    elif not local:
                        continue
                    else:
                        p.write_text(broken)       # the evidence is gathered on the workspace as the failure left it
                        if kind == "misnamed":     # the used name has no definition: search its module by prefix
                            bad_name = fields["bad"]
                            turn, res, found = evidence_turn(root, [bad_name], f"{note} {check_text([bad_name])}")
                            mod = next(f for f in sorted(module_files(path, fields["module"])) if (root / f).is_file())
                            g_call, g_text, g_hits = definitions_like(root, fields["name"], f"{WS}/{mod}")
                            p.write_text(good)
                            hit = next((h[:3] for h in g_hits if h[3] == fields["name"]), None)
                            if found[bad_name] is not None or hit is None or len(g_hits) > 3:
                                continue           # the evidence does not show this cause: no row
                            search = {"role": "assistant", "weight": 1, "tool_calls": [g_call], "content":
                                      f"find_symbol finds no definition of `{bad_name}`, so the name itself is wrong. "
                                      f"Let me search `{WS}/{mod}`, the module it is imported from, for definitions "
                                      f"whose name starts with `{fields['name']}`."}
                            note, before = CITED[kind].format(hit=at(hit), **fields), [(turn, res), (search, [g_text])]
                        else:
                            names = [fields["name"]] + ([fields["bad"]] if kind == "wrong_name" else [])
                            turn, res, found = evidence_turn(root, names, f"{note} {check_text(names)}")
                            p.write_text(good)
                            hit = found[fields["name"]]
                            if not isinstance(hit, tuple) or hit[1].removeprefix(WS + "/") not in \
                                    module_files(path, fields["module"]) or (kind == "wrong_name" and found[fields["bad"]]):
                                continue           # the evidence does not show this cause: no row
                            note, before = CITED[kind].format(hit=at(hit), **fields), [(turn, res)]
                b = {"content": broken, "result": bad.text}
                fix = {"role": "assistant", "content": note, "tool_calls": [fix_call]}
                row = make_row(ep, task, path, b, fix, [fixed.text], "injected", probe, before)
                row["meta"].update(task_type="jac_fix_injected", mutation=kind)
                rows.append(scrubbed(row, root))
        rows += [scrubbed(r, root) for r in dropped_defs(ep, task, ws, files, rng)]
    return rows


def top_blocks(text: str) -> list[tuple[str, int, int]]:
    """(name, first line, end line exclusive) of each top-level definition whose block closes with a `}` at column 0,
    with a one-line docstring right above it."""
    lines, out = text.split("\n"), []
    for i, l in enumerate(lines):
        if (m := TOP_DEF.match(l)) and l.rstrip().endswith("{"):
            j = next((k for k in range(i + 1, len(lines)) if lines[k] == "}"), None)
            if j is not None:
                start = i - 1 if i and re.fullmatch(r'""".*"""', lines[i - 1].strip()) else i
                out.append((m.group(2), start, j + 1 + (j + 1 < len(lines) and not lines[j + 1].strip())))
    return out


def dropped_defs(ep: Path, task: dict, ws: Workspace, files: list[Path], rng: random.Random) -> list[dict]:
    """drop_def rows: a definition deleted from the module another file imports it from. The importing file's
    write fails `jac check`, or (an unresolved import is only warning W1101) passes it while a test fails; the agent
    checks the evidence (no definition anywhere), reads the module, writes the definition back, and reruns the
    failing check or test."""
    root, rows, tests = ws.root, [], None
    sources = {p: p.read_text() for p in files if not p.name.endswith((".test.jac", ".impl.jac"))}
    every = "\n".join(p.read_text(errors="replace") for p in files)
    for mod, good in sources.items():
        if len(good) > MAX_FILE:
            continue
        mod_path = f"{WS}/{mod.relative_to(root)}"
        users = {n: q for q, t in sources.items() if q != mod for m, names in IMPORT.findall(t)
                 for n in [x.split(" as ")[0].strip() for x in names.split(",")]
                 if f"{mod.relative_to(root)}" in module_files(f"{WS}/{q.relative_to(root)}", m)}
        blocks = [b for b in top_blocks(good) if b[0] in users and not re.search(rf"\bimpl\s+{b[0]}\b", every)]
        for name, i, j in rng.sample(blocks, min(PER_FILE["drop_def"], len(blocks))):
            q = users[name]
            q_path, q_text = f"{WS}/{q.relative_to(root)}", sources[q]
            if len(q_text) > MAX_FILE:
                continue
            lines = good.split("\n")
            broken = "\n".join(lines[:i] + lines[j:])
            if tests is None:
                tests = tests_of(ws)               # on the unbroken workspace
            mod.write_text(broken)
            try:
                bad, probe = ws.write_code(q_path, q_text), None
                if not bad.failed:                 # only W1101 for the import: the tests show it
                    probe = next(((f"jac test {t.relative_to(root)}", r.text) for t in tests
                                  if (r := ws.run_command(f"jac test {t.relative_to(root)}")).failed), None)
                    if probe is None:
                        continue
                elif bad.kind != "jac_errors":
                    continue
                if not re.search(rf"\b{name}\b", bad.text + (probe[1] if probe else "")):
                    continue                       # the failure must name what is missing
                note = f"`{name}` does not resolve here: it is not imported, or not defined where I expect."
                turn, res, found = evidence_turn(root, [name], f"{note} {check_text([name])}")
                if found[name] is not None:
                    continue                       # the evidence must show no definition
                read = {"role": "assistant", "weight": 1, "content":
                        f"find_symbol finds no definition of `{name}` in the project, and the module list has "
                        f"`{mod_path}`, the module this file imports it from. So `{name}` was never defined there. "
                        "Let me read that module before adding it.", "tool_calls": [call("call_r", "read_file",
                        file_path=mod_path, offset=0, limit=2000)]}
                shown = ws.read_file(mod_path).text
                old, new = restoring_edit(broken, good)
                fix = {"role": "assistant", "content": f"I'll define `{name}` in `{mod_path}`, matching how it is used.",
                       "tool_calls": [call("call_fix", "edit_code", file_path=mod_path, old_string=old, new_string=new)]}
                fixed = ws.edit_code(mod_path, old, new)
                cmd = probe[0] if probe else f"jac check {q.relative_to(root)}"
                verify = ws.run_command(cmd)
                if fixed.failed or verify.failed:
                    continue
                again = {"role": "assistant", "weight": 1, "tool_calls": [call("call_v", "run_command", command=cmd)],
                         "content": f"Now `{name}` is defined. Let me run `{cmd}` again."}
                b = {"content": q_text, "result": bad.text}
                row = make_row(ep, task, q_path, b, fix, [fixed.text], "injected", probe,
                               [(turn, res), (read, [shown])], [(again, [verify.text])])
                row["meta"].update(task_type="jac_fix_injected", mutation="drop_def", file=mod_path)
                rows.append(row)
            finally:
                mod.write_text(good)
                q.write_text(q_text)
    return rows


def capped(rows: list[dict]) -> list[dict]:
    """At most CAP[kind] rows of a capped kind, sampled evenly across episodes."""
    rng, out, by = random.Random(SEED), [], collections.defaultdict(list)
    for r in rows:
        by[r["meta"]["mutation"]].append(r)
    for kind, rs in by.items():
        out += rng.sample(rs, CAP[kind]) if kind in CAP and len(rs) > CAP[kind] else rs
    return out


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episodes", type=Path, default=OUT_ROOT / "sets/all",
                    help="training episodes only: never the held-out comparison runs")
    ap.add_argument("--out", type=Path, default=OUT_ROOT / "sft/debug_injected/train.jsonl")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    eps = [ep for ep in sorted(a.episodes.iterdir())
           if (ep / "summary.json").exists() and json.loads((ep / "summary.json").read_text())["end"] == "success"]
    found = []
    for i in range(0, len(eps), a.workers):        # jac test leaves a database per test block (~4 GB per
        jac_cli.start_pg()                         # episode): purge after each round of workers, no jac running
        try:
            with ThreadPoolExecutor(a.workers) as pool:
                found += [r for rs in pool.map(candidates_of, eps[i:i + a.workers]) for r in rs]
        finally:
            jac_cli.purge_pg()
    rows = capped(found)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"{len(found)} verified, {len(rows)} kept after caps, from {len(eps)} episodes -> {a.out}")
    print("found", dict(collections.Counter(r["meta"]["mutation"] for r in found)))
    print("kept ", dict(collections.Counter(r["meta"]["mutation"] for r in rows)))
    print(collections.Counter(c for r in rows for c in r["meta"]["error_codes"]).most_common(12))
