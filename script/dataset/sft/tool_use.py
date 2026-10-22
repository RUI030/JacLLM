"""Agent trajectories (dataset/raw/trajectory/<ds>.jsonl) -> tool-use SFT records (chat messages + tool schemas)."""

import argparse, json, random, re, sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from utils.classifier          import classify_structural as classify
from dataset.pipeline          import report, split_and_write
from dataset.trajectory.common import redact, to_template_input

# Setting =================================================
DS_FORMAT = "chat"
DS_NAME   = "jaccoder-old"
SOURCE    = "session"
TASK_TYPE = "tool_use"

DS_ROOT  = f"{Path(__file__).resolve().parent}/../../../dataset"
IN_FILE  = f"{DS_ROOT}/raw/trajectory/jaccoder_old.jsonl"
OUT_DIR  = f"{DS_ROOT}/sft/{TASK_TYPE}/{DS_NAME}"
HARNESS_DIR = f"{Path(__file__).resolve().parent}/../trajectory/harness"   # fallback for rows without `tools`

OUT_FORMAT = "jsonl"
VALID_SIZE = 0.05                       # held out by conversation
SEED       = 3407
MAX_TOKENS = 16384                      # chat-template tokens incl. system prompt + tool schemas
TOKENIZER  = "ornith-ai/Ornith-1.5-9B"
WRITE_EXTS = ("jac", "css", "toml")     # --require-write keeps trajectories whose trained calls write one of these
PATCH_FILE = re.compile(r"\*\*\* (?:Add|Update) File: (\S.*)")
SHELL_WRITE = re.compile(r"(?:>>?|\btee(?: -a)?|\bsed -i\S*|\bcp|\bmv)\s+[^\n;|&]*?\.(\w+)\b")

# Functions ===============================================
def token_counter(tokenizer_name: str):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(tokenizer_name)
    def n_tokens(msgs: list[dict], tools: list[dict]) -> int:
        parsed = [{**m, "tool_calls": [{**c, "function": {**c["function"], "arguments": json.loads(c["function"]["arguments"])}}
                                       for c in m["tool_calls"]]} if "tool_calls" in m else m for m in msgs]
        text = tok.apply_chat_template(parsed, tools=tools, tokenize=False)
        return len(tok(text, add_special_tokens=False)["input_ids"])
    n_tokens.tok = tok
    return n_tokens


def jac_written(traj: dict) -> str:
    """Jac code the model wrote (write/edit arguments on .jac files), for the structural class."""
    code = []
    for r in traj["rows"]:
        if r["mode"] == "tool_call" and r.get("weight", 1) != 0:
            a = r["args"]
            if str(a.get("file_path", a.get("path", ""))).endswith(".jac"):
                code.append(a.get("content") or a.get("new_string") or "")
    return "\n".join(code)


def writes_ext(traj: dict, exts: tuple[str, ...]) -> bool:
    """True when a trained call writes a file with one of `exts`: apply_patch, a shell write, or a write/edit tool's path."""
    for r in traj["rows"]:
        if r["mode"] != "tool_call" or r.get("weight", 1) == 0:
            continue
        a = r["args"] if isinstance(r["args"], dict) else {}
        found = [Path(p.strip()).suffix[1:] for p in PATCH_FILE.findall(str(a.get("input", a.get("cmd", ""))))]
        found += SHELL_WRITE.findall(str(a.get("cmd", "")))
        found.append(Path(str(a.get("file_path", a.get("path", "")))).suffix[1:])
        if any(e in exts for e in found):
            return True
    return False


def messages(traj: dict, system: str | None) -> list[dict]:
    """Rows -> chat messages (tool-call arguments as JSON strings, which the chat template expects)."""
    msgs = to_template_input(traj, system)
    for m in msgs:
        for c in m.get("tool_calls", []):
            c["function"]["arguments"] = json.dumps(c["function"]["arguments"], ensure_ascii=False)
    return msgs


def prompt_cuts(rows: list[dict]) -> list[int]:
    """Indices where cutting the trajectory ends on a whole user turn: before each later user prompt, then the end."""
    starts = [i for i, r in enumerate(rows) if r["mode"] == "prompt" and i > 1
              and rows[i - 1]["role"] != "user"]
    return starts[::-1] and [len(rows)] + starts[::-1]


def fit(traj: dict, system: str | None, tools: list[dict], n_tokens, max_tokens: int) -> tuple[dict, list[dict], int, int] | None:
    """Longest prefix of whole user turns within `max_tokens` that still trains on something.

    Returns (trajectory, messages, tokens, user turns dropped) or None.
    """
    rows = traj["rows"]
    for k, cut in enumerate(prompt_cuts(rows) or [len(rows)]):
        part = {**traj, "rows": rows[:cut]}
        if not any(r["role"] == "assistant" and r.get("weight", 1) != 0 for r in part["rows"]):
            continue
        msgs = messages(part, system)
        n    = n_tokens(msgs, tools)
        if n <= max_tokens:
            return part, msgs, n, k
    return None


def row_tokens(row: dict, tok) -> int:
    """Rough chat-template tokens of one row (text or call arguments, plus per-message overhead)."""
    text = row.get("content") or json.dumps(row.get("args", ""), ensure_ascii=False)
    return len(tok(text, add_special_tokens=False)["input_ids"]) + 8


def windows(traj: dict, system: str | None, tools: list[dict], n_tokens, max_tokens: int):
    """Cut the whole trajectory into consecutive windows of at most `max_tokens`; yields (trajectory, messages, tokens).

    A window starts at a response boundary (so no tool result loses its call) and ends at the next one.
    Every window after the first begins with the user prompt it continues, as context only, because a
    chat template needs a user turn first and the model must still see the task. A window without a
    trained response is skipped. Sizes are planned from per-row estimates, then checked with the real
    template and shortened by one response until they fit.
    """
    rows   = traj["rows"]
    tok    = n_tokens.tok
    cost   = [row_tokens(r, tok) for r in rows]
    starts = [i for i, r in enumerate(rows) if r["role"] == "assistant" and (i == 0 or rows[i - 1]["role"] != "assistant")]
    start  = 0
    k      = 0
    while start < len(rows):
        anchor = [] if start == 0 else [next((r for r in rows[start::-1] if r["mode"] == "prompt"), None)]
        anchor = [a for a in anchor if a]
        room   = max_tokens - 4096 - sum(cost[rows.index(a)] for a in anchor)      # 4096: system prompt + tool schemas, with margin
        cuts   = [i for i in starts if i > start] + [len(rows)]
        end, used = start, 0
        for c in cuts:
            used += sum(cost[end:c])
            if used > room and end > start:
                break
            end = c
        while True:
            part = {**traj, "rows": anchor + rows[start:end], "meta": {**traj["meta"], "window": k}}
            if not any(r["role"] == "assistant" and r.get("weight", 1) != 0 for r in part["rows"]):
                break
            msgs = messages(part, system)
            n    = n_tokens(msgs, tools)
            if n <= max_tokens:
                yield part, msgs, n
                break
            smaller = [c for c in cuts if start < c < end]
            if not smaller:
                break                    # a single response is larger than the limit
            end = smaller[-1]
        start = max(end, start + 1)
        k += 1


def build_record(traj: dict, msgs: list[dict], tools: list[dict], n: int, dropped: int) -> dict:
    meta = traj["meta"]
    return {
        "messages": msgs,
        "tools":    json.dumps(tools, ensure_ascii=False),      # a string: Arrow would merge the schemas' keys
        "meta": {
            "source":     SOURCE,
            "format":     DS_FORMAT,
            "class":      classify(jac_written(traj)),
            "task_type":  TASK_TYPE,
            "fp":         meta.get("split_group") or meta["session_id"],     # forks of one session stay on one side of the split
            "window":     meta.get("window"),
            "harness":    meta["harness"],
            "tool_calls": sum(r["mode"] == "tool_call" for r in traj["rows"]),
            "trained_calls": sum(r["mode"] == "tool_call" and r.get("weight", 1) != 0 for r in traj["rows"]),
            "synthetic_reads": sum(bool(r.get("synthetic")) for r in traj["rows"] if r["mode"] == "tool_call"),
            "turns_dropped": dropped,
            "tokens":     n,
        },
    }


def traj2tool_use(in_file=IN_FILE, out_dir=OUT_DIR, format=OUT_FORMAT, max_tokens=MAX_TOKENS, limit=None, window=False, require_write=()):
    """One record per trajectory, cut to whole user turns that fit `max_tokens`; split by conversation.

    `require_write` (extensions): trajectories without a trained write to one of them are dropped whole;
    kept ones keep every window, reads and searches included.

    Writes train/valid to `out_dir` and `rejected.jsonl` (nothing fits, or nothing to train on).
    """
    out_dir = Path(out_dir)
    trajs   = [json.loads(l) for l in open(in_file, encoding="utf-8")][:limit]
    if not trajs:
        raise FileNotFoundError(f"No trajectories in: {in_file}")
    n_tokens = token_counter(TOKENIZER)
    records, rejected, count = [], [], Counter()
    for traj in map(redact, trajs):
        if require_write and not writes_ext(traj, require_write):
            count["no_write"] += 1
            continue
        tools, system = traj.get("tools"), None
        if not tools:                   # a known harness: its prompt and tools come from harness/<name>.json
            spec   = json.loads(Path(f"{HARNESS_DIR}/{traj['meta']['harness']}.json").read_text())
            tools  = spec["tools"]
            system = spec["system"].replace("{cwd}", traj["meta"].get("cwd", ""))
        if window:                      # whole trajectory as consecutive windows, nothing dropped
            n_win = 0
            for part, msgs, n in windows(traj, system, tools, n_tokens, max_tokens):
                records.append(build_record(part, msgs, tools, n, 0))
                n_win += 1
            count["windows"] += n_win
            if not n_win:
                rejected.append({"fp": traj["meta"]["session_id"], "reason": f"no window within {max_tokens} tokens with a trained response"})
            continue
        got   = fit(traj, system, tools, n_tokens, max_tokens)
        if not got:
            rejected.append({"fp": traj["meta"]["session_id"], "reason": f"no whole-turn prefix within {max_tokens} tokens with a trained response"})
            continue
        part, msgs, n, dropped = got
        count["turns_dropped"] += dropped
        count["trimmed"] += bool(dropped)
        records.append(build_record(part, msgs, tools, n, dropped))

    rng = random.Random(SEED)
    rng.shuffle(records)
    counts = split_and_write(records, out_dir, VALID_SIZE, format)
    with (out_dir / "rejected.jsonl").open("w", encoding="utf-8") as f:
        for row in rejected:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    report(counts, out_dir)
    tokens = sorted(r["meta"]["tokens"] for r in records)
    print(f"  {len(trajs)} trajectories ({count['no_write']} without a write to {'/'.join(require_write)}) -> {len(records)} records ({count['trimmed']} cut to fit, "
          f"{count['turns_dropped']} user turns dropped); {len(rejected)} rejected (see rejected.jsonl)")
    print(f"  tokens: total {sum(tokens):,}, median {tokens[len(tokens) // 2]}, max {tokens[-1]}")


# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--in-file", default=IN_FILE)
    cli.add_argument("--out-dir", default=OUT_DIR)
    cli.add_argument("--max-token", dest="max_tokens", type=int, default=MAX_TOKENS,
                     help="cut trajectories to whole user turns within this many chat-template tokens (incl. tools)")
    cli.add_argument("--window", action="store_true",
                     help="cut every trajectory into consecutive windows within --max-token (continuation windows repeat their user prompt as context)")
    cli.add_argument("--require-write", nargs="?", const=",".join(WRITE_EXTS), default="", metavar="EXTS",
                     help=f"keep only trajectories whose trained calls write these extensions (comma list; bare flag = {','.join(WRITE_EXTS)})")
    cli.add_argument("--limit", type=int, default=None, help="first N trajectories only (smoke run)")
    args = cli.parse_args()
    traj2tool_use(args.in_file, args.out_dir, max_tokens=args.max_tokens, limit=args.limit, window=args.window,
                  require_write=tuple(e for e in args.require_write.split(",") if e))
