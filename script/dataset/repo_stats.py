"""Codebase statistics for dataset/raw/repo: per-repo Jac size, declarations, fillable bodies, cross-file references."""

import argparse, json, sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from dataset.parser.repo import body_name, body_spans, cross_refs, iter_repos, jac_sources, load_meta, symbol_index

# Setting =================================================
DS_ROOT  = f"{Path(__file__).resolve().parent}/../../dataset"
IN_DIR   = f"{DS_ROOT}/raw/repo"
OUT_PATH = f"{DS_ROOT}/raw/repo/stats.json"

BODY_LINE_BINS = [2, 5, 10, 20, 40, 60, 100]   # body line-count upper bounds; last bucket = ">last"

# Functions ===============================================
def bin_label(n: int) -> str:
    lo = 0
    for hi in BODY_LINE_BINS:
        if n <= hi:
            return f"{lo + 1}-{hi}" if lo else f"<={hi}"
        lo = hi
    return f">{BODY_LINE_BINS[-1]}"


def repo_stats(sources: dict[str, str]) -> dict:
    """Size, declaration kinds, fillable-body length histogram and cross-file reference counts of one repo."""
    index  = symbol_index(sources)
    kinds  = Counter(d["kind"] for defs in index.values() for d in defs)
    bodies = Counter()
    named  = with_refs = 0
    for rel, source in sources.items():
        for span in body_spans(source):
            body = source[span[1]:span[2]]
            bodies[bin_label(body.count("\n"))] += 1
            if body_name(source, span):
                named     += 1
                with_refs += bool(cross_refs(body, rel, index))
    return {
        "jac_files":         len(sources),
        "jac_lines":         sum(s.count("\n") + 1 for s in sources.values()),
        "jac_chars":         sum(len(s) for s in sources.values()),
        "declarations":      dict(sorted(kinds.items())),
        "bodies":            sum(bodies.values()),
        "named_bodies":      named,
        "bodies_cross_file": with_refs,
        "body_lines":        {b: bodies[b] for b in [bin_label(n) for n in [*BODY_LINE_BINS, BODY_LINE_BINS[-1] + 1]]},
    }


def collect(in_dir=IN_DIR, out_path=OUT_PATH) -> dict:
    """Write `{repos: {group/name: stats}, total: stats-sums}` to `out_path` and print a table."""
    meta  = load_meta(Path(in_dir) / "meta.json")
    repos = {}
    for key, root in iter_repos(Path(in_dir), include_excluded=True):
        st = repo_stats(jac_sources(root, set(meta["exclude_files"].get(key, []))))
        st["whitelisted"] = meta["repos"].get(key, {}).get("whitelist", {}).get("ok")
        repos[key] = st
    total = Counter()
    for st in repos.values():
        total.update({k: v for k, v in st.items() if isinstance(v, int) and not isinstance(v, bool)})
    out = {"repos": repos, "total": dict(total)}
    Path(out_path).write_text(json.dumps(out, indent=2) + "\n")

    print(f"{'repo':60} {'files':>5} {'lines':>6} {'bodies':>6} {'xfile':>5}")
    for key, st in repos.items():
        print(f"{key[:60]:60} {st['jac_files']:5} {st['jac_lines']:6} {st['bodies']:6} {st['bodies_cross_file']:5}")
    print(f"{'TOTAL':60} {total['jac_files']:5} {total['jac_lines']:6} {total['bodies']:6} {total['bodies_cross_file']:5}")
    print(f"Wrote {out_path}")
    return out

# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--in-dir", default=IN_DIR)
    cli.add_argument("--out", default=OUT_PATH)
    args = cli.parse_args()
    collect(args.in_dir, args.out)
