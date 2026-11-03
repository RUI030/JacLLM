"""Rank hackathon repos by checked cross-file slices usable for revdev."""
import json, re, sys
from pathlib import Path, PurePosixPath as P

ROOT = Path("/home/imrui/Documents/Jaseci/JacLLM")
IMP = re.compile(r'^\s*(?:import\s+from\s+|import\s+|include\s+)([\.\w]+)', re.M)

def resolve(src, mod, files):
    mod = mod.lstrip(".") if mod.startswith(".") else mod
    rel = mod.replace(".", "/") + ".jac"
    for base in (P(src).parent, P("")):
        cand = str(base / rel)
        if cand in files: return cand
    hits = [f for f in files if f.endswith("/" + rel) or f == rel]
    return hits[0] if len(hits) == 1 else None

def analyze(files: dict, failed: set):
    src = {f: c for f, c in files.items() if not f.endswith(".impl.jac") and "/ui/" not in f}
    for f, c in files.items():  # impl annexes merge into parent module
        if f.endswith(".impl.jac"):
            parent = re.sub(r"(\.impl)?\.impl\.jac$|\.impl\.jac$", ".jac", f).replace("/impl/", "/")
            if parent in src: src[parent] += "\n" + c
    deps = {f: {d for m in IMP.findall(c) if (d := resolve(f, m, src)) and d != f} for f, c in src.items()}
    ok = {f for f in src if f not in failed}
    closed = {}
    def is_closed(f, seen=()):
        if f in closed: return closed[f]
        if f not in ok or f in seen: return f in ok
        closed[f] = all(is_closed(d, seen + (f,)) for d in deps[f])
        return closed[f]
    good = [f for f in src if is_closed(f)]
    importers = [f for f in good if deps[f]]
    edges = sum(len(deps[f]) for f in good)
    def depth(f, seen=()):
        return 0 if not deps[f] or f in seen else 1 + max(depth(d, seen + (f,)) for d in deps[f])
    return {"modules": len(src), "checked_closed": len(good), "importers": len(importers),
            "edges": edges, "max_depth": max((depth(f) for f in good), default=0),
            "top_importers": sorted(importers, key=lambda f: -len(deps[f]))[:3]}

def a2tech():
    meta = json.loads((ROOT / "JacLLM/dataset/raw/repo/meta.json").read_text())["repos"]
    for key, v in meta.items():
        if "A2Tech" not in key: continue
        d = ROOT / "JacLLM/dataset/raw/repo" / key
        files = {str(p.relative_to(d)): p.read_text(errors="ignore") for p in d.rglob("*.jac")
                 if not any(x in p.parts for x in ("node_modules", ".jac", "jaseci"))}
        r = analyze(files, set(v["jac_check"]["failed_files"]))
        u = v["jac_usage"]
        yield {"pool": "A2Tech", "repo": key.split("/")[1], "title": v["source"]["title"],
               "kind": u["kind"], "pin": v["source"]["jac_version_pin"],
               "check": f'{v["jac_check"]["passed"]}/{v["jac_check"]["passed"]+v["jac_check"]["failed"]}',
               "byllm": u["byllm"]["by_llm"], "osp": u["osp"]["walker"] + u["osp"]["node"], **r}

def nonsf():
    by = {}
    for line in open(ROOT / "jac-data-gen/data/jachacks_nonsf_jac_files_checked.jsonl"):
        x = json.loads(line); by.setdefault((x["source"], x["dirname"], x.get("title")), {})[x["file_path"]] = x["jac"]
    for (source, repo, title), files in by.items():
        r = analyze(files, set())
        yield {"pool": source.replace("jachacks-", ""), "repo": repo, "title": title, "kind": "",
               "pin": None, "check": "all", "byllm": len(re.findall(r"by llm", "".join(files.values()))),
               "osp": len(re.findall(r"^\s*(?:walker|node)\s", "".join(files.values()), re.M)), **r}

rows = list(a2tech()) + list(nonsf())
json.dump(rows, open(sys.argv[1], "w"), indent=1, ensure_ascii=False)
