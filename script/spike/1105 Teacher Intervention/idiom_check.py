"""Is the Jac idiomatic, or Python / React written with braces? `jac check` accepts much of both. Two sources:

- `jac check --lint` (the language's own rules, kebab names such as [mutable-default]) on whole workspaces;
- RULES below, each taken from a skill's "write Jac, not X" guidance, on any Jac text (a workspace file, or the code
  in a training row's write_code content / edit_code new_string).

    python idiom_check.py --workspaces <ws> [<ws> ...]      # lint + rules per workspace
    python idiom_check.py --rows <train.jsonl> [...]         # rules on the trained (weight 1) code of each row
"""

import argparse, collections, json, re, sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli

# Setting =================================================
JSX   = re.compile(r"->\s*JsxElement|return\s*\(?\s*<[A-Za-z]|</\w+>")
LINT  = re.compile(r"\[([a-z][a-z0-9-]+)\]\s*$", re.M)
SKIP  = {".jac", "node_modules", "__pycache__", ".git"}
RULES = [   # (name, applies to client code only, pattern, the skill's idiom)
    ("react-hook",       True,  r"\buse(State|Effect)\s*\(",
     "jac-cl-components: state is `has x: T = v;`, mount effects are `async can with entry`"),
    ("map-lambda",       True,  r"\.map\(\s*lambda\b",
     "jac-cl-components: lists render with a `{for x in items { <li>{x}</li> }}` slot"),
    ("lambda-handler",   True,  r"\bon[A-Z]\w*=\{\s*lambda\b",
     "jac-cl-components: `onClick={handle}` with `def handle(e: MouseEvent) { ... }`"),
    ("mutate-state",     True,  None,
     "jac-cl-components: `has` state re-renders only on rebinding (`xs = xs + [x];`), not on .append/[i]="),
    ("js-syntax",        False, r"===|!==|\bnull\b|\bundefined\b|\bconst\s+\w+\s*=|\bfunction\s+\w+\s*\(|&&|\|\|",
     "jac-cl-components / jac-core-cheatsheet: `==`, `None`, typed assignment, `def`, `and`/`or`"),
    ("python-enum",      False, r"\bclass\s+\w+\s*\(\s*(?:\w+\.)?(?:Str|Int)?Enum\s*\)",
     "jac-core-cheatsheet: `enum Color { RED, GREEN }`"),
    ("class-for-obj",    False, r"(?m)^\s*class\s+\w+\s*(?:\{|\(\s*\)\s*\{)",
     "jac-python-interop: default to `obj` for your own types; `class` only for Python metaclass bases"),
    ("dunder-main",      False, r"__name__\s*==\s*[\"']__main__",
     "jac-core-cheatsheet: `with entry:__main__ { ... }`"),
    ("python-id",        False, r"(?<![\w.])id\(\s*\w",
     "jac-sv-persistence: look nodes up with `jid()` / `jobj()`, never Python `id()`"),
    ("any-type",         False, r"(?::|->)\s*any\b",
     "jac-types: do not fall back to `any`; type the field, use `T | None`, or cast at the boundary"),
]


# Functions ===============================================
def mutated_state(text: str) -> list[str]:
    """`has` fields of a client component that are changed in place."""
    fields = set(re.findall(r"(?m)^\s*has\s+(\w+)\s*:", text))
    hits = re.findall(r"\b(\w+)\s*(?:\.(?:append|extend|insert|pop|remove|sort|clear|update)\(|\[[^\]]+\]\s*=[^=])", text)
    return sorted({h for h in hits if h in fields})


def rule_hits(text: str, client: bool | None = None) -> collections.Counter:
    """Rule name -> occurrences in one piece of Jac text. `client` None: decide from the text (JSX present)."""
    client = bool(JSX.search(text)) if client is None else client
    code = re.sub(r'"""(?:.|\n)*?"""|"(?:\\.|[^"\\\n])*"|#[^\n]*', '""', text)   # strings and comments say nothing
    out = collections.Counter()
    for name, client_only, pattern, _ in RULES:
        if client_only and not client:
            continue
        n = len(mutated_state(code)) if name == "mutate-state" else len(re.findall(pattern, code))
        if n:
            out[name] += n
    return out


def lint(root: Path, files: list[Path]) -> collections.Counter:
    res = jac_cli.execute(["check", "--lint", *[str(f.relative_to(root)) for f in files]], timeout=300, cwd=root,
                          merge_stderr=True)
    return collections.Counter(LINT.findall(res.stdout))


def workspace_report(root: Path) -> dict:
    files = [p for p in sorted(root.rglob("*.jac")) if not SKIP & set(p.relative_to(root).parts)]
    rules = collections.Counter()
    for p in files:
        rules += rule_hits(p.read_text(errors="replace"))
    return {"files": len(files), "rules": dict(rules), "lint": dict(lint(root, files)) if files else {}}


def trained_code(row: dict) -> list[str]:
    """The Jac a row trains: write_code content and edit_code new_string of weight-1 turns, .jac files only."""
    out = []
    for m in row["messages"]:
        if m["role"] != "assistant" or not m.get("weight"):
            continue
        for c in m.get("tool_calls") or []:
            a = c["function"]["arguments"]
            a = json.loads(a) if isinstance(a, str) else a
            if str(a.get("file_path", "")).endswith(".jac"):
                out.append(a.get("content") or a.get("new_string") or "")
    return out


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspaces", nargs="*", type=Path, default=[])
    ap.add_argument("--rows", nargs="*", type=Path, default=[])
    a = ap.parse_args()
    for ws in a.workspaces:
        print(json.dumps({"workspace": str(ws), **workspace_report(ws)}))
    for f in a.rows:
        rows = [json.loads(l) for l in f.open()]
        total, with_hit, snippets = collections.Counter(), collections.Counter(), 0
        for r in rows:
            hits = collections.Counter()
            for code in trained_code(r):
                snippets += 1
                hits += rule_hits(code)
            total += hits
            with_hit.update(hits.keys())
        print(f"== {f}: {len(rows)} rows, {snippets} trained .jac writes/edits")
        for name, n in total.most_common():
            print(f"  {name:15s} {n:5d} hits in {with_hit[name]:4d} rows   ({next(r[3] for r in RULES if r[0] == name)})")
