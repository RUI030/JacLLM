"""Codex session archive (jac-coding-trajectories-dataset-*/partial/*/codex-*) -> trajectory JSONL (see README.md).

Input is a colleague's export, not live `~/.codex` logs: each folder has `metadata.json` and
`conversation.jsonl.zst` (kinds: message, tool_call, tool_result, reasoning, compaction, ...).
What the export does and does not have, measured on the 168 sessions (2026-10):
  - No system prompt and no tool schemas: `harness/codex.json` has them, captured from a live Codex
    request (Unsloth's fallback prompt, not the gpt-5.x/6 ones these sessions ran with). `sft/tool_use.py`
    reads it for trajectories without their own `tools`, so rows carry no system row.
  - Reasoning is encrypted or summary-only: dropped, counted.
  - Tool calls come in two shapes. Direct `exec_command` / `write_stdin` / `apply_patch` (~68%) are kept
    as they are. `exec` (18%) wraps JS: `text(await tools.exec_command({...}))`. Single-call wrappers are
    unwrapped to the direct call; anything else (Promise.all, several tools, MCP, loops) stays as a
    native `exec` call with weight 0, because the model cannot be taught JS orchestration we do not
    deploy. Multi-agent, MCP and image tools are kept as context with weight 0 for the same reason.
"""

import argparse, io, json, re
import sys
from collections import Counter
from pathlib import Path

import zstandard

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from dataset.trajectory.common import mark_loops, mask, responses, write_trajectories

# Setting =================================================
HARNESS = "codex"
DS_ROOT = f"{Path(__file__).resolve().parent}/../../../dataset"
IN_DIR  = Path(DS_ROOT) / "raw/session/jac-coding-trajectories-dataset-20261016/partial"
OUT     = f"{DS_ROOT}/raw/trajectory/{HARNESS}.jsonl"
MIN_JAC_CALLS = 5                                    # sessions with fewer tool calls touching *.jac are skipped
SPEC          = Path(__file__).resolve().parent / "harness" / f"{HARNESS}.json"
EXCLUDE_CWD   = ("jac_memory_redesign_experiments",)   # controlled memory-study runs (36 sessions): synthetic prompts, not real work
TRAIN_TOOLS   = {t["function"]["name"] for t in json.loads(SPEC.read_text())["tools"]}   # others get weight 0
INJECTED      = ("<app-context>", "<recommended_plugins>", "<permissions", "<environment_context>",
                 "<skills_instructions>", "<multi_agent_role>", "<collaboration_mode>", "<user_instructions>")
SIMPLE_EXEC   = re.compile(r"^\s*text\(\s*(?:\(\s*)?await\s+tools\.(\w+)\(\s*(\{.*\})\s*\)\s*(?:\)\s*\.output)?\s*\)\s*;?\s*$", re.S)
JS_KEY        = re.compile(r'([{,]\s*)([A-Za-z_]\w*)\s*:')
EXIT_CODE     = re.compile(r"Process exited with code (-?\d+)")

# Functions ===============================================
def read_events(fp: Path):
    with fp.open("rb") as raw:
        for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(raw), encoding="utf-8"):
            yield json.loads(line)


def text_of(content) -> str:
    """Message / result content (string or block list) -> plain text."""
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict))


def parse_js_object(src: str):
    """A JS object literal with unquoted keys -> dict, or None when it is not plain data."""
    try:
        return json.loads(JS_KEY.sub(r'\1"\2":', src))
    except json.JSONDecodeError:
        return None


def unwrap_exec(code: str):
    """`exec` JS -> (tool, args) when it is one plain tool call, else None."""
    m = SIMPLE_EXEC.match(code)
    if not m or code.count("tools.") != 1:
        return None
    args = parse_js_object(m.group(2))
    return (m.group(1), args) if args is not None else None


def call_row(e: dict) -> tuple[dict, bool]:
    """tool_call event -> (row, unwrapped). Rows carry `_cid`, removed once results are paired."""
    tool, raw = e["tool"], e.get("arguments") or ""
    unwrapped = False
    if tool == "exec":
        got = unwrap_exec(raw)
        if got:
            (tool, args), unwrapped = got, True
        else:
            args = {"code": raw}
    elif tool == "apply_patch":
        args = {"input": raw}
    else:
        try:
            args = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            args = {"raw": raw}
    row = {"role": "assistant", "mode": "tool_call", "name": tool, "args": args, "id": e["call_id"]}
    if tool not in TRAIN_TOOLS:
        row.update(weight=0, masked="exec_js" if tool == "exec" else "tool_unsupported")
    return row, unwrapped


def result_row(e: dict, unwrapped: bool) -> dict:
    """tool_result event -> harness row with status from the exit code when the tool reports one."""
    out = e.get("output")
    if isinstance(out, list):                        # `exec` wrapper: header block, then JSON chunks
        parts = [b.get("text", "") for b in out][1:] if unwrapped else [b.get("text", "") for b in out]
        chunks = []
        for p in parts:
            try:
                j = json.loads(p)
                chunks.append(j["output"] if unwrapped and isinstance(j, dict) and "output" in j else p)
            except (json.JSONDecodeError, TypeError):
                chunks.append(p)
        text = "\n".join(c for c in chunks if c)
    else:
        text = out or ""
    code = EXIT_CODE.search(text)
    if not code:
        try:                                         # apply_patch: {"output":..., "metadata": {"exit_code": N}}
            j = json.loads(text)
            code = {"exit_code": j["metadata"]["exit_code"]}
        except (json.JSONDecodeError, KeyError, TypeError):
            code = None
    bad = code and int((code.group(1) if hasattr(code, "group") else code["exit_code"])) != 0
    return {"role": "harness", "mode": "tool_result", "content": text, "status": "error" if bad else "ok"}


def pair_results(rows: list[dict], stats: Counter) -> list[dict]:
    """Put each response's results right after it, in call order; a call with no result gets an empty `missing` one."""
    out, i = [], 0
    while i < len(rows):
        r = rows[i]
        i += 1
        if r["mode"] == "tool_result":                # arrived after other rows (user message, compaction): no call to pair with
            stats["results_orphaned"] += 1
            continue
        out.append(r)
        if r["role"] != "assistant" or (i < len(rows) and rows[i]["role"] == "assistant"):
            continue
        j = len(out) - 1
        while j >= 0 and out[j]["role"] == "assistant":
            j -= 1
        calls = [x for x in out[j + 1:] if x["mode"] == "tool_call"]
        got = {}
        while i < len(rows) and rows[i]["role"] == "harness" and rows[i]["mode"] == "tool_result":
            got[rows[i]["_cid"]] = rows[i]
            i += 1
        for c in calls:
            res = got.pop(c["id"], None)
            if res is None:
                stats["calls_missing_result"] += 1
                res = {"role": "harness", "mode": "tool_result", "content": "", "status": "missing"}
            out.append(res)
        stats["results_unmatched"] += len(got)
    for r in out:
        r.pop("_cid", None)
    return out


def segment_rows(events, stats: Counter):
    """Events -> (rows per segment, model counter). A compaction starts a new segment."""
    segs, rows, models, unwrapped = [], [], Counter(), {}
    for e in events:
        k = e["kind"]
        if k == "compaction":
            segs.append(rows)
            rows = []
            hist = [m for m in e["data"].get("replacement_history", []) if m.get("type") == "message" and m.get("role") == "user"]
            for m in hist:
                t = text_of(m["content"]).strip()
                if t and not t.startswith(INJECTED):
                    rows.append({"role": "user", "mode": "prompt", "content": t})   # kept verbatim; the summary itself is encrypted
            stats["compactions"] += 1
        elif k == "message" and e["role"] == "user":
            t = text_of(e["content"]).strip()
            if t.startswith(INJECTED) or not t:
                stats["dropped_injected_user"] += 1
            elif t.startswith("# AGENTS.md instructions"):
                rows.append({"role": "harness", "mode": "context", "content": t})
            else:
                rows.append({"role": "user", "mode": "prompt", "content": t})
        elif k == "message" and e["role"] == "assistant":
            models[e.get("model")] += 1
            rows.append({"role": "assistant", "mode": "reply", "content": text_of(e["content"])})
        elif k == "tool_call":
            row, un = call_row(e)
            unwrapped[e["call_id"]] = un
            stats["exec_unwrapped"] += un
            rows.append(row)
        elif k == "tool_result":
            r = result_row(e, unwrapped.get(e["call_id"], False))
            r["_cid"] = e["call_id"]
            rows.append(r)
        elif k == "reasoning":
            stats["reasoning_dropped"] += 1
        else:                                         # developer messages, agent_message, lifecycle, token_usage
            stats[f"dropped_{k}"] += 1
    segs.append(rows)
    return segs, models


def trim_segment(rows: list[dict]) -> list[dict]:
    """A segment must open with user/prompt before its first assistant row (chat template rule)."""
    first = next((i for i, r in enumerate(rows) if r["mode"] == "prompt"), None)
    if first is None:
        return []
    ctx = [r for r in rows[:first] if r["role"] == "harness" and r["mode"] == "context"]
    return ctx + rows[first:]


def convert(d: Path, min_jac: int, stats: Counter) -> list[dict]:
    meta = json.loads((d / "metadata.json").read_text())
    cwd = (meta.get("session_metadata") or {}).get("cwd", "")
    if any(x in cwd for x in EXCLUDE_CWD):
        stats["sessions_skipped_excluded_cwd"] += 1
        return []
    segs, models = segment_rows(read_events(d / "conversation.jsonl.zst"), stats)
    jac = sum(1 for s in segs for r in s if r["mode"] == "tool_call" and ".jac" in json.dumps(r["args"]))
    if jac < min_jac:
        stats["sessions_skipped_low_jac"] += 1
        return []
    model = models.most_common(1)[0][0] if models else None
    trajs = []
    for n, rows in enumerate(segs):
        rows = trim_segment(pair_results(rows, stats))
        if not any(r["role"] == "assistant" for r in rows):
            stats["segments_dropped_empty"] += 1
            continue
        for g in responses(rows):                     # row-level weights -> whole-response mask
            if any(r.get("weight") == 0 for r in g):
                mask(g, next(r["masked"] for r in g if r.get("masked")))
        mark_loops(rows)
        sm = meta.get("session_metadata") or {}
        trajs.append({"meta": {
            "harness": HARNESS, "model": model, "models_seen": sorted(m for m in models if m),
            "session_id": meta["source_session_id"], "trajectory_id": meta["trajectory_id"], "segment": n,
            "parent": None, "host": meta["host"], "forked_from_id": sm.get("forked_from_id"),
            "split_group": meta.get("train_eval_split_group"), "jac_calls": jac,
        }, "rows": rows})
    return trajs


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in-dir", default=str(IN_DIR))
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--min-jac-calls", type=int, default=MIN_JAC_CALLS)
    ap.add_argument("--limit", type=int, default=0, help="first N sessions only (smoke test)")
    a = ap.parse_args()
    stats, trajs = Counter(), []
    dirs = sorted(Path(a.in_dir).glob("*/codex-*"))[: a.limit or None]
    for d in dirs:
        trajs += convert(d, a.min_jac_calls, stats)
    st = write_trajectories(trajs, a.out, dict(stats))
    print(f"{len(dirs)} sessions -> {len(trajs)} trajectories: {a.out}")
    print(json.dumps({k: v for k, v in st.items() if not k.startswith(("tool:", "rows_"))}, indent=1))
