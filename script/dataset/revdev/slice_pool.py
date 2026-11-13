"""Rank hackathon repos by checked cross-file slices usable for revdev."""

import argparse, json, re
from pathlib import Path, PurePosixPath

# Setting =================================================
ROOT      = Path(__file__).resolve().parents[3]
REPO_DIR  = ROOT / "dataset/raw/repo"
NONSF_JAC = ROOT.parent / "jac-data-gen/data/jachacks_nonsf_jac_files_checked.jsonl"
SKIP_DIRS = ("node_modules", ".jac", "jaseci")
IMPORT_RE = re.compile(r'^\s*(?:import\s+from\s+|import\s+|include\s+)([\.\w]+)', re.M)

# Functions ===============================================
def resolve(importer: str, module: str, files: dict[str, str]) -> str | None:
    """Map an import line's module to a file in the repo, or None if it is not local."""
    rel = module.lstrip(".").replace(".", "/") + ".jac"
    for base in (PurePosixPath(importer).parent, PurePosixPath("")):
        candidate = str(base / rel)
        if candidate in files:
            return candidate
    hits = [f for f in files if f.endswith("/" + rel) or f == rel]
    return hits[0] if len(hits) == 1 else None


def analyze(files: dict[str, str], failed: set[str]) -> dict:
    """Count modules that pass check together with every local module they import.

    A "closed" module passes `jac check` and so do its local imports,
    transitively; only closed modules can form a slice. Impl annexes are folded
    into their parent module and `/ui/` files are ignored.
    """
    sources = {f: c for f, c in files.items() if not f.endswith(".impl.jac") and "/ui/" not in f}
    for path, content in files.items():
        if path.endswith(".impl.jac"):
            parent = re.sub(r"(\.impl)?\.impl\.jac$", ".jac", path).replace("/impl/", "/")
            if parent in sources:
                sources[parent] += "\n" + content
    deps = {f: {d for m in IMPORT_RE.findall(c) if (d := resolve(f, m, sources)) and d != f}
            for f, c in sources.items()}
    passing = {f for f in sources if f not in failed}
    closed: dict[str, bool] = {}

    def is_closed(path: str, seen: tuple = ()) -> bool:
        if path in closed:
            return closed[path]
        if path not in passing or path in seen:
            return path in passing
        closed[path] = all(is_closed(d, seen + (path,)) for d in deps[path])
        return closed[path]

    def depth(path: str, seen: tuple = ()) -> int:
        if not deps[path] or path in seen:
            return 0
        return 1 + max(depth(d, seen + (path,)) for d in deps[path])

    good = [f for f in sources if is_closed(f)]
    importers = [f for f in good if deps[f]]
    return {"modules": len(sources), "checked_closed": len(good), "importers": len(importers),
            "edges": sum(len(deps[f]) for f in good),
            "max_depth": max((depth(f) for f in good), default=0),
            "top_importers": sorted(importers, key=lambda f: -len(deps[f]))[:3]}


def a2tech_rows():
    """Rows for A2Tech repos cloned under dataset/raw/repo, using their recorded check results."""
    meta = json.loads((REPO_DIR / "meta.json").read_text())["repos"]
    for key, repo in meta.items():
        if "A2Tech" not in key:
            continue
        repo_dir = REPO_DIR / key
        files = {str(p.relative_to(repo_dir)): p.read_text(errors="ignore")
                 for p in repo_dir.rglob("*.jac") if not any(x in p.parts for x in SKIP_DIRS)}
        check, usage = repo["jac_check"], repo["jac_usage"]
        yield {"pool": "A2Tech", "repo": key.split("/")[1], "title": repo["source"]["title"],
               "kind": usage["kind"], "pin": repo["source"]["jac_version_pin"],
               "check": f'{check["passed"]}/{check["passed"] + check["failed"]}',
               "byllm": usage["byllm"]["by_llm"], "osp": usage["osp"]["walker"] + usage["osp"]["node"],
               **analyze(files, set(check["failed_files"]))}


def nonsf_rows():
    """Rows for JacHacks repos from the jac-data-gen sweep, whose files all passed check."""
    repos: dict[tuple, dict[str, str]] = {}
    for line in NONSF_JAC.open():
        row = json.loads(line)
        repos.setdefault((row["source"], row["dirname"], row.get("title")), {})[row["file_path"]] = row["jac"]
    for (source, repo, title), files in repos.items():
        text = "".join(files.values())
        yield {"pool": source.replace("jachacks-", ""), "repo": repo, "title": title, "kind": "",
               "pin": None, "check": "all", "byllm": text.count("by llm"),
               "osp": len(re.findall(r"^\s*(?:walker|node)\s", text, re.M)), **analyze(files, set())}

# Run =====================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path, help="JSON file to write the ranked rows to")
    args = parser.parse_args()
    rows = list(a2tech_rows()) + list(nonsf_rows())
    args.out.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
