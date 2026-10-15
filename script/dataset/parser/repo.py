"""Repo-level helpers: file walking and Jac scaffold extraction."""

from __future__ import annotations

import json, re
from pathlib import Path
from typing import Iterator

# Files/dirs to keep or drop when walking a repo =============
DROP_DIRS: frozenset[str] = frozenset({
    ".jac", ".git", "node_modules", "__pycache__",
    "dist", "build", ".next", ".venv", "venv",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".turbo",
})
KEEP_EXTS: frozenset[str] = frozenset({
    ".jac", ".md", ".toml", ".json", ".py",
    ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".txt", ".yaml", ".yml",
})
DROP_EXTS: frozenset[str] = frozenset({
    ".lock", ".pyc", ".pyo", ".so", ".env",
})
KEEP_NAMES: frozenset[str] = frozenset({
    "README", "LICENSE", "Makefile",
})


def keep_path(path: Path, repo_root: Path) -> bool:
    """True iff `path` is dev-authored source we want in training."""
    rel = path.relative_to(repo_root)
    if any(part in DROP_DIRS for part in rel.parts):
        return False
    if path.suffix in DROP_EXTS:
        return False
    if path.suffix in KEEP_EXTS:
        return True
    return path.stem in KEEP_NAMES and path.suffix == ""


def iter_repos(raw_dir: Path) -> Iterator[tuple[str, Path]]:
    """Yield `(group/name, repo_root)` for every repo under `raw_dir/<group>/<name>/`.

    Groups: `golden` (founder projects), `Rui`, `jaseci`, `JacHack<edition>`.
    """
    for group in sorted(p for p in Path(raw_dir).iterdir() if p.is_dir()):
        for repo in sorted(p for p in group.iterdir() if p.is_dir()):
            yield f"{group.name}/{repo.name}", repo


def iter_repo_files(repo_root: Path) -> Iterator[Path]:
    """Yield every source file under `repo_root` that survives keep_path()."""
    for path in sorted(repo_root.rglob("*")):
        if path.is_file() and keep_path(path, repo_root):
            yield path


# Jac scaffold extraction ====================================
# Strip the body of every `def`, `can`, `with entry`, and `impl` block. Leaves
# node/edge/obj/walker headers, `has` fields, docstrings, imports intact.

_STRIP_HEADS = re.compile(
    r"^(?P<lead>\s*)"
    r"(?P<head>(?:def(?::\w+)?|can|with\s+entry|impl)\b[^{;]*)"
    r"(?P<open>\{)",
    re.MULTILINE,
)


def _skip_over(text: str, i: int) -> int:
    """Skip past a string literal or comment starting at i. Return new index."""
    n = len(text)
    ch = text[i]
    if ch in ('"', "'"):
        # triple?
        if text[i:i+3] in ('"""', "'''"):
            quote = text[i:i+3]
            j = text.find(quote, i + 3)
            return n if j < 0 else j + 3
        # single-line quoted; honour backslash escapes
        j = i + 1
        while j < n:
            if text[j] == "\\":
                j += 2; continue
            if text[j] == ch:
                return j + 1
            j += 1
        return n
    if ch == "#" or text[i:i+2] == "//":
        j = text.find("\n", i)
        return n if j < 0 else j
    if text[i:i+2] == "/*":
        j = text.find("*/", i + 2)
        return n if j < 0 else j + 2
    return i + 1


def _find_matching_close(text: str, open_idx: int) -> int:
    """Given index of `{`, return index just past matching `}`. -1 if unbalanced."""
    n = len(text)
    depth = 0
    i = open_idx
    while i < n:
        ch = text[i]
        if ch in ('"', "'", "#") or text[i:i+2] in ("//", "/*"):
            i = _skip_over(text, i)
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def body_spans(source: str) -> list[tuple[int, int, int]]:
    """Return `(head_start, open_at, close)` for every strippable body, in order.

    Bodies nested inside another strippable body are not listed (they go with it).
    """
    spans: list[tuple[int, int, int]] = []
    cursor = 0
    for m in _STRIP_HEADS.finditer(source):
        head_start, open_at = m.start("head"), m.end("open") - 1
        if open_at < cursor:
            continue
        close = _find_matching_close(source, open_at)
        if close < 0:
            continue
        spans.append((head_start, open_at, close))
        cursor = close
    return spans


def strip_bodies(source: str, keep: set[int] | None = None) -> str:
    """Return `source` with every def/can/with-entry/impl body replaced by `{ ... }`.

    `keep`: indices into `body_spans(source)` whose bodies stay implemented.
    """
    out: list[str] = []
    cursor = 0
    for i, (_, open_at, close) in enumerate(body_spans(source)):
        if keep and i in keep:
            continue
        out.append(source[cursor:open_at])
        out.append("{ ... }")
        cursor = close
    out.append(source[cursor:])
    return "".join(out)


# Declaration index ==========================================
# Named top-level-ish declarations, used for codebase statistics and to find the
# file a symbol is defined in (tool-call trajectories read it as context).

_DECL_HEAD = re.compile(
    r"^[ \t]*(?:(?P<arch>node|edge|walker|obj|class|enum)(?::\w+)?|(?P<fn>def|can)(?::\w+)?|(?P<impl>impl))"
    r"\s+(?P<name>[\w.]+)",
    re.MULTILINE,
)


def decl_kind(m: re.Match) -> str:
    return m.group("arch") or m.group("fn") or "impl"


def declarations(source: str) -> list[dict]:
    """Every named declaration: `{kind, name, line, start, end}` (end = past its `}`, or line end).

    `name` is the last dotted part, so `impl Foo.bar` indexes as `bar` (kind `impl`).
    """
    decls = []
    for m in _DECL_HEAD.finditer(source):
        start = m.start()
        stop  = re.compile(r"[{;]").search(source, m.end())
        end   = source.find("\n", m.end())
        if stop and source[stop.start()] == "{":
            close = _find_matching_close(source, stop.start())
            if close > 0:
                end = close
        decls.append({
            "kind":  decl_kind(m),
            "name":  m.group("name").split(".")[-1],
            "line":  source.count("\n", 0, start) + 1,
            "start": start,
            "end":   len(source) if end < 0 else end,
        })
    return decls


def body_name(source: str, span: tuple[int, int, int]) -> str | None:
    """Name of the def/can/impl whose body is `span`; None for `with entry` and anonymous blocks."""
    m = _DECL_HEAD.match(source, source.rfind("\n", 0, span[0]) + 1)
    return m.group("name").split(".")[-1] if m and m.group("arch") is None else None


# Repo-level symbol lookup ===================================
IDENT = re.compile(r"\b[A-Za-z_]\w{2,}\b")


def jac_sources(repo_root: Path, exclude: set[str]) -> dict[str, str]:
    """`{rel path: source}` for every Jac file of a repo, minus meta.json's `exclude_files`."""
    out = {}
    for path in iter_repo_files(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        if path.suffix != ".jac" or rel in exclude:
            continue
        try:
            out[rel] = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    return out


def symbol_index(sources: dict[str, str]) -> dict[str, list[dict]]:
    """`{name: [{file, kind, line, start, end}, ...]}` over all Jac files of one repo."""
    index: dict[str, list[dict]] = {}
    for rel, source in sources.items():
        for d in declarations(source):
            index.setdefault(d["name"], []).append({"file": rel, **{k: d[k] for k in ("kind", "line", "start", "end")}})
    return index


def cross_refs(body: str, rel: str, index: dict[str, list[dict]]) -> list[str]:
    """Names used in `body` that are declared exactly once, in another file of the repo (first-use order)."""
    seen = []
    for name in IDENT.findall(body):
        defs = index.get(name, [])
        if len(defs) == 1 and defs[0]["file"] != rel and name not in seen:
            seen.append(name)
    return seen


def load_meta(path: str | Path) -> dict:
    """raw/repo/meta.json (jac-data-gen): whitelist and per-repo `exclude_files`."""
    return json.loads(Path(path).read_text())
