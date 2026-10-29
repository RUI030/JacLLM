"""Build a compiler-backed private reference manifest from one Jac repository."""

import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile, tomllib
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

sys.path.append(str(Path(__file__).resolve().parents[2]))
from dataset.parser.repo import DROP_DIRS, iter_repo_files, keep_path
from utils.jac_cli import execute

# Setting =================================================
BRIDGE       = Path(__file__).with_suffix(".jac")
DEFAULT_JAC  = "jac"
CHECK_TIMEOUT = 120
EXTRACTOR_VERSION = "m1.0"
BUILTINS     = {"print", "len", "range", "str", "int", "float", "bool", "list", "dict", "set", "getattr", "isinstance", "super"}


# Functions ===============================================
def sha256(data: bytes) -> str:
    """Return a hex SHA-256 for exact file bytes."""
    return hashlib.sha256(data).hexdigest()


def git_value(repo: Path, *args: str) -> str | None:
    """Read one Git value when the source copy retains its history."""
    if not (repo / ".git").exists():
        return None
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=10)
    return result.stdout.strip() if result.returncode == 0 else None


def safe_origin(repo: Path) -> str | None:
    """Keep repository provenance without URL credentials."""
    origin = git_value(repo, "remote", "get-url", "origin")
    if not origin:
        return None
    parsed = urlsplit(origin)
    if parsed.scheme and "@" in parsed.netloc:
        return urlunsplit((parsed.scheme, parsed.netloc.rsplit("@", 1)[-1],
                           parsed.path, "", ""))
    if parsed.scheme:
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return origin


def root_version(repo: Path) -> str | None:
    """Read the repository's declared Jac version, if present."""
    config = repo / "jac.toml"
    if not config.is_file():
        return None
    return tomllib.loads(config.read_text(encoding="utf-8")).get("project", {}).get("jac-version")


def excluded_paths(repo: Path) -> list[dict]:
    """Summarize skipped source paths without enumerating generated trees."""
    excluded = []
    for directory, dirs, files in os.walk(repo):
        root = Path(directory)
        for name in list(dirs):
            if name in DROP_DIRS:
                excluded.append({"path": (root / name).relative_to(repo).as_posix(),
                                 "kind": "directory", "reason": "generated_or_dependency_tree"})
                dirs.remove(name)
        for name in files:
            path = root / name
            if not keep_path(path, repo):
                excluded.append({"path": path.relative_to(repo).as_posix(),
                                 "kind": "file", "reason": "filtered_by_repo_policy"})
    return sorted(excluded, key=lambda item: item["path"])


def compiler_rows(repo: Path, jac_files: list[str], jac: str) -> dict:
    """Invoke the pinned Jac AST bridge through the shared Jac CLI wrapper."""
    with tempfile.TemporaryDirectory(prefix="revdev-extract-") as tmp:
        request = Path(tmp) / "request.json"
        output = Path(tmp) / "ast.json"
        source_copy = Path(tmp) / "source"
        shutil.copytree(repo, source_copy, ignore=shutil.ignore_patterns(".git", ".jac", "node_modules", "dist", "build", "__pycache__"))
        request.write_text(json.dumps({"repo": str(source_copy), "files": [{"path": p} for p in jac_files]}), encoding="utf-8")
        result = execute(["run", str(BRIDGE), str(request), str(output)], timeout=CHECK_TIMEOUT, cwd=source_copy, jac=jac)
        if not result.ok or not output.is_file():
            raise RuntimeError(f"Jac AST bridge failed (exit={result.returncode}): {result.text()[:2000]}")
        return json.loads(output.read_text(encoding="utf-8"))


def import_target(source: str, import_row: dict, item: dict, known: set[str]) -> tuple[str | None, str]:
    """Resolve only local Jac paths or selected assets proven by the file list."""
    raw = import_row["from_path"] or item["path"] or import_row.get("from_string") or ""
    if not raw:
        return None, "empty_import_path"
    level = int(import_row.get("from_level") or 0)
    if raw.startswith("./") or raw.startswith("../"):
        base = Path(source).parent
        candidate = (base / raw).as_posix()
        candidates = [candidate]
    else:
        base = Path(source).parent if level else Path(".")
        for _ in range(max(level - 1, 0)):
            base = base.parent
        dotted = raw.lstrip(".").replace(".", "/")
        candidates = [(base / dotted).as_posix()]
        if level == 0:
            candidates.append((Path(source).parent / dotted).as_posix())
    paths = []
    for candidate in candidates:
        paths.extend([candidate, candidate + ".jac", candidate + "/__init__.jac"])
    for candidate in paths:
        normalized = Path(candidate).as_posix().removeprefix("./")
        if normalized in known:
            return normalized, "jac" if normalized.endswith(".jac") else "asset"
    return None, "missing_local" if level or raw.startswith("./") or raw.startswith("../") else "external_or_missing"


def strongly_connected(nodes: list[str], edges: list[dict]) -> list[list[str]]:
    """Return deterministic import cycles using Tarjan's algorithm."""
    graph = {node: set() for node in nodes}
    for edge in edges:
        if edge["kind"] == "import" and edge.get("to_file") in graph:
            graph[edge["from_file"]].add(edge["to_file"])
    index, stack, on_stack, number, low, cycles = 0, [], set(), {}, {}, []

    def visit(node: str) -> None:
        nonlocal index
        number[node] = low[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for other in sorted(graph[node]):
            if other not in number:
                visit(other)
                low[node] = min(low[node], low[other])
            elif other in on_stack:
                low[node] = min(low[node], number[other])
        if low[node] == number[node]:
            group = []
            while True:
                other = stack.pop()
                on_stack.remove(other)
                group.append(other)
                if other == node:
                    break
            if len(group) > 1 or node in graph[node]:
                cycles.append(sorted(group))

    for node in sorted(nodes):
        if node not in number:
            visit(node)
    return sorted(cycles)


def baseline(repo: Path, jac: str) -> dict:
    """Run a fresh check in a disposable copy so raw source stays untouched."""
    config = repo / "jac.toml"
    entry = tomllib.loads(config.read_text(encoding="utf-8")).get("project", {}).get("entry-point") if config.is_file() else None
    if not entry:
        return {"state": "unavailable", "reason": "no_entry_point"}
    with tempfile.TemporaryDirectory(prefix="revdev-baseline-") as tmp:
        target = Path(tmp) / "project"
        shutil.copytree(repo, target, ignore=shutil.ignore_patterns(".git", ".jac", "node_modules", "dist", "build", "__pycache__"))
        result = execute(["check", entry], timeout=CHECK_TIMEOUT, cwd=target, jac=jac)
    return {
        "state": "passed" if result.ok else "failed",
        "command": [jac, "check", entry], "exit_code": result.returncode,
        "stdout": result.stdout, "stderr": result.stderr,
        "duration_ms": round(result.ms), "timed_out": result.timed_out,
        "launch_error": result.launch_error,
    }


def validate_manifest(manifest: dict, repo: Path) -> None:
    """Reject any accepted edge without a real source span or target."""
    paths = {item["path"] for item in manifest["files"] if item["selected"]}
    symbol_ids = {item["id"] for item in manifest["symbols"]}
    for edge in manifest["dependencies"]:
        if edge["from_file"] not in paths or edge["to_file"] not in paths:
            raise ValueError(f"Dependency points outside selected files: {edge}")
        if edge.get("to_symbol") and edge["to_symbol"] not in symbol_ids:
            raise ValueError(f"Dependency points to missing symbol: {edge}")
        span = edge.get("span") or {}
        lines = (repo / edge["from_file"]).read_text(encoding="utf-8").splitlines()
        line, column = span.get("line", 0), span.get("column", 0)
        if not 1 <= line <= len(lines) or not 1 <= column <= len(lines[line - 1]) + 1:
            raise ValueError(f"Dependency lacks source evidence: {edge}")


def build_manifest(repo: Path, repo_key: str, jac: str, check: bool = True) -> dict:
    """Extract files, AST evidence, conservative edges, cycles and baseline."""
    repo = repo.resolve()
    declared_version = root_version(repo)
    version = execute(["--version"], timeout=10, jac=jac)
    if not version.ok:
        raise RuntimeError(f"Could not identify Jac executable {jac}: {version.text()}")
    actual_version = version.stdout.strip() or version.stderr.strip()
    exact = re.fullmatch(r"(?:==)?(\d+\.\d+\.\d+)", declared_version.strip()) if declared_version else None
    installed = re.search(r"\b(\d+\.\d+\.\d+)\b", actual_version)
    if exact and (installed is None or exact.group(1) != installed.group(1)):
        raise ValueError(f"Repo requires Jac {exact.group(1)}, but {jac} reports {actual_version}")
    selected = list(iter_repo_files(repo))
    files = [{"path": p.relative_to(repo).as_posix(), "sha256": sha256(p.read_bytes()),
              "size": p.stat().st_size, "kind": p.suffix.lstrip(".") or p.name,
              "selected": True, "reason": "kept_by_repo_policy"} for p in selected]
    known = {f["path"] for f in files}
    jac_files = [f["path"] for f in files if f["kind"] == "jac"]
    compiler = compiler_rows(repo, jac_files, jac)
    rows = compiler["files"]
    symbols, imports, calls, errors = [], [], [], []
    for row in rows:
        path = row["path"]
        if "error" in row:
            errors.append({"file": path, "reason": "parse_error", "detail": row["error"]})
            continue
        for sym in row["symbols"]:
            sym = {**sym, "file": path}
            sym["id"] = sha256(f'{path}:{sym["span"].get("line")}:{sym["kind"]}:{sym["name"]}'.encode())[:16]
            symbols.append(sym)
        imports.extend({**imp, "file": path} for imp in row["imports"])
        calls.extend({**call, "file": path} for call in row["calls"])
    by_file_name = {}
    for sym in symbols:
        by_file_name.setdefault((sym["file"], sym["name"]), []).append(sym)
    dependencies, unresolved, import_bindings = [], list(errors), {}
    for imp in imports:
        source = imp["file"]
        items = imp["items"] or [{}]
        for item in items:
            target, target_kind = import_target(source, imp, item, known)
            evidence = item.get("span") or imp["span"]
            expression = imp["from_path"] or item.get("path") or imp.get("from_string")
            if target is None:
                unresolved.append({"file": source, "span": evidence, "expression": expression,
                                   "symbol": item.get("name") or None, "reason": target_kind})
                continue
            candidates = [s for s in by_file_name.get((target, item.get("name")), [])
                          if not s.get("owner")] if item.get("name") else []
            to_symbol = candidates[0]["id"] if len(candidates) == 1 else None
            dependencies.append({"kind": "import" if target_kind == "jac" else "asset",
                                 "from_file": source, "to_file": target, "to_symbol": to_symbol,
                                 "span": evidence, "expression": expression,
                                 "imported_name": item.get("name") or None,
                                 "resolution": "ast_path", "confidence": "compiler_ast"})
            if item.get("name") and to_symbol:
                import_bindings[(source, item.get("alias") or item["name"])] = (target, to_symbol)
            if item.get("name") and not to_symbol and target_kind == "jac":
                unresolved.append({"file": source, "span": evidence, "expression": expression,
                                   "symbol": item["name"], "reason": "symbol_not_found_in_target"})
    for sym in symbols:
        if sym["kind"] != "impl" or not sym["file"].endswith(".impl.jac"):
            continue
        owner = sym["file"].removesuffix(".impl.jac") + ".jac"
        declared = by_file_name.get((owner, sym["name"]), [])
        if owner in known and len(declared) == 1:
            dependencies.append({"kind": "annex", "from_file": sym["file"], "to_file": owner,
                                 "to_symbol": declared[0]["id"], "span": sym["span"],
                                 "expression": sym["name"], "resolution": "annex_pair",
                                 "confidence": "structural"})
        else:
            unresolved.append({"file": sym["file"], "span": sym["span"],
                               "expression": sym["name"], "reason": "annex_declaration_not_found"})
    for call in calls:
        name = "".join(call["target"].split())
        if not name or name in BUILTINS:
            continue
        source = call["file"]
        owner = source.removesuffix(".impl.jac") + ".jac" if source.endswith(".impl.jac") else source
        binding = import_bindings.get((source, name)) or import_bindings.get((owner, name))
        local = [s for s in (by_file_name.get((source, name), []) or by_file_name.get((owner, name), []))
                 if not s.get("owner")]
        if binding:
            target, symbol_id = binding
        elif len(local) == 1:
            target, symbol_id = source, local[0]["id"]
        else:
            unresolved.append({"file": source, "span": call["span"], "expression": name,
                               "reason": "dynamic_or_unresolved_call"})
            continue
        dependencies.append({"kind": "call", "from_file": source, "to_file": target,
                             "to_symbol": symbol_id, "span": call["span"],
                             "expression": name, "resolution": "ast_name_binding",
                             "confidence": "syntactic"})
    for name, refs in compiler.get("compiler_references", {}).items():
        candidates = [sym for sym in symbols if sym["name"] == name and sym["kind"] != "impl"]
        if len(candidates) != 1:
            continue
        target = candidates[0]
        has_matching_def = any(ref["role"] == "def" and ref["file"] == target["file"]
                               and ref["line"] == target["span"]["line"] for ref in refs)
        if not has_matching_def:
            continue
        for ref in refs:
            if ref["role"] != "use" or ref["file"] != target["file"]:
                continue
            dependencies.append({"kind": "symbol_use", "from_file": ref["file"],
                                 "to_file": target["file"], "to_symbol": target["id"],
                                 "span": {"line": ref["line"], "column": ref["column"],
                                          "end_line": ref["line"], "end_column": ref["column"] + len(name)},
                                 "expression": name, "resolution": "code_intelligence_unique_def",
                                 "confidence": "compiler_symbol"})
    tree_hash = sha256("\n".join(f'{f["path"]}:{f["sha256"]}' for f in files).encode())
    commit = git_value(repo, "rev-parse", "HEAD")
    manifest = {
        "schema_version": "1",
        "reference": {"reference_id": f"{repo_key}@{commit or tree_hash[:16]}",
                      "repo_key": repo_key, "commit": commit,
                      "origin": safe_origin(repo),
                      "tree_sha256": tree_hash, "local_modifications": bool(git_value(repo, "status", "--porcelain"))},
        "toolchain": {"jac_version": actual_version,
                      "declared_jac_version": declared_version,
                      "exact_version_matched": True if exact else None,
                      "parser_mode": "JacProgram.parse_str",
                      "bridge": "script/dataset/revdev/extract.jac", "extractor_version": EXTRACTOR_VERSION},
        "files": files, "excluded_paths": excluded_paths(repo),
        "symbols": symbols, "dependencies": dependencies,
        "compiler_references": compiler.get("compiler_references", {}),
        "code_intelligence_error": compiler.get("code_intelligence_error") or None,
        "unresolved_dependencies": unresolved, "cycles": strongly_connected(jac_files, dependencies),
        "baseline": baseline(repo, jac) if check else {"state": "pending"},
    }
    validate_manifest(manifest, repo)
    return manifest


def main() -> None:
    """Extract one repo into a private manifest JSON artifact."""
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path)
    parser.add_argument("--repo-key", required=True)
    parser.add_argument("--jac", default=DEFAULT_JAC)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-check", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest(args.repo, args.repo_key, args.jac, check=not args.no_check)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(manifest["files"]), "symbols": len(manifest["symbols"]),
                      "dependencies": len(manifest["dependencies"]),
                      "unresolved": len(manifest["unresolved_dependencies"]),
                      "cycles": len(manifest["cycles"]), "baseline": manifest["baseline"]["state"]}))


# Run =====================================================
if __name__ == "__main__":
    main()
