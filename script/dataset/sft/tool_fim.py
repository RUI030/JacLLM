"""Repo Jac bodies -> pi tool-call trajectories that fill a stubbed body (FIM as an agent task)."""

import argparse, json, random, re, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from utils.classifier          import classify_structural as classify
from utils.jac_cli             import execute
from dataset.parser.repo       import (DROP_DIRS, body_name, body_spans, cross_refs, iter_repos,
                                       jac_sources, load_meta, symbol_index)
from dataset.pipeline          import load_prompts, report, split_and_write
from dataset.trajectory.common import redact, to_template_input, write_trajectories

# Setting =================================================
DS_FORMAT = "repo"
DS_NAME   = "repo-all-pi"
SOURCE    = "code"
TASK_TYPE = "tool_fim"
HARNESS   = "pi"

DS_ROOT  = f"{Path(__file__).resolve().parent}/../../../dataset"
IN_DIR   = f"{DS_ROOT}/raw/repo"
OUT_DIR  = f"{DS_ROOT}/sft/{TASK_TYPE}/{DS_NAME}"
TRAJ_OUT = f"{DS_ROOT}/raw/trajectory/{DS_NAME}.jsonl"    # rows before chat-template mapping (inspection)
HARNESS_SPEC = f"{Path(__file__).resolve().parent}/../trajectory/harness/{HARNESS}.json"

PROMPT     = f"{Path(__file__).resolve().parent}/../template/prompt_template.json"
OUT_FORMAT = "jsonl"
VALID_SIZE = 0.05                       # held out by file: no valid body is ever visible in a train context
SEED       = 3407
WORKERS    = 8                          # repos built in parallel (rg / jac subprocesses)

MIN_BODY_LINES  = 2                     # skip one-liners: nothing to learn from filling `{ return x; }`
MAX_BODY_LINES  = 60
HOLES_PER_FILE  = 16                    # caps how often one file is re-read across trajectories
MULTI_P         = 0.15                  # chance a file also gets one 2-3 hole trajectory (single edit call)
NO_PATH_P       = 0.25                  # prompt names only the symbol; the trajectory searches for it
CTX_MAX         = 2                     # cross-file symbols looked up before editing
READ_FULL_LINES = 200                   # longer files are read as a window around the hole
READ_PAD        = 30
CTX_READ_LINES  = 60
CHECK_TAIL      = 3                     # `jac check` warnings go to stderr and run long; agents tail it
MAX_TOKENS      = 8192                  # chat-template tokens incl. system prompt + tool schemas
TOKENIZER       = "ornith-ai/Ornith-1.5-9B"
CWD_ROOTS       = ["/home/dev", "/home/user/projects", "/workspace", "/home/alex/code", "/srv/app"]

PI_MAX_LINES = 2000                     # pi read/bash truncation limits (core/tools/truncate.js)
PI_MAX_BYTES = 50 * 1024

SAY_LOCATE = ["", "", "Let me find it first.", "Locating `{name}`."]
SAY_READ   = ["", "", "Let me look at the file.", "Reading {path} first."]
SAY_CTX    = ["", "Let me check `{ref}`.", "`{name}` uses `{ref}`; checking its definition."]
SAY_EDIT   = ["", "", "Now filling in the body.", "Implementing it now."]
SAY_CHECK  = ["", "", "Checking the file."]
SAY_DONE   = ["Implemented {names} in {path}; `jac check` passes.",
              "Done: implemented {names} in {path}; the file type-checks.",
              "{names} implemented. `jac check {path}` passes."]

# Functions ===============================================
def pi_read(text: str, offset: int | None = None, limit: int | None = None) -> str:
    """What pi's `read` tool returns for a text file (no truncation case; callers stay under the limits)."""
    lines = text.split("\n")
    start = offset - 1 if offset else 0
    if limit is None:
        return "\n".join(lines[start:])
    end  = min(start + limit, len(lines))
    out  = "\n".join(lines[start:end])
    if end < len(lines):
        out += f"\n\n[{len(lines) - end} more lines in file. Use offset={end + 1} to continue.]"
    return out


def rg(ws: Path, pattern: str, where: str) -> tuple[str, str]:
    """(command shown to the model, its output) for an `rg -n` search run in the workspace."""
    shown = f'rg -n "{pattern}" {where}'
    proc  = subprocess.run(f'rg --sort path -n "{pattern}" {where}', shell=True, cwd=ws, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True)        # --sort: rg's thread order is not stable
    return shown, (proc.stdout + proc.stderr) or "(no output)"


def jac_check(ws: Path, rel: str) -> tuple[bool, str]:
    """(passed, `jac check <rel> 2>&1 | tail -n CHECK_TAIL` output) in the workspace."""
    res  = execute(["check", rel], 120, ws, merge_stderr=True)
    tail = res.stdout.rstrip("\n").split("\n")[-CHECK_TAIL:]
    return res.ok and not res.timed_out, "\n".join(tail) + "\n"


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def head_pattern(source: str, span: tuple[int, int, int], name: str) -> str:
    """Declaration head up to and including the name (`def:pub load`), as an rg pattern."""
    head = " ".join(source[span[0]:span[1]].split())
    return head[: head.index(name) + len(name)] + r"\b"


def stub(source: str, spans: list[tuple[int, int, int]]) -> tuple[str, list[dict]]:
    """Replace each body in `spans` with a TODO stub; returns (stubbed source, pi edits that undo it)."""
    out, edits, cursor = [], [], 0
    for head_start, open_at, close in spans:
        line_start = source.rfind("\n", 0, head_start) + 1
        indent     = re.match(r"[ \t]*", source[line_start:]).group(0)
        stubbed    = source[line_start:open_at] + "{\n" + indent + "    # TODO: implement\n" + indent + "}"
        out.append(source[cursor:line_start] + stubbed)
        edits.append({"oldText": stubbed, "newText": source[line_start:close]})
        cursor = close
    out.append(source[cursor:])
    return "".join(out), edits


def fillable(source: str) -> list[tuple[tuple[int, int, int], str]]:
    """(span, name) of bodies worth filling: named, MIN..MAX lines, name unique among the file's bodies.

    Bodies with inline `::py::` are skipped: filling them teaches Python, not Jac.
    """
    spans = [(s, body_name(source, s)) for s in body_spans(source)]
    names = [n for _, n in spans]
    return [(s, n) for s, n in spans
            if n and names.count(n) == 1 and "::py::" not in source[s[1]:s[2]]
            and MIN_BODY_LINES <= source[s[1]:s[2]].count("\n") <= MAX_BODY_LINES]


def unique_edit(source: str, span: tuple[int, int, int]) -> bool:
    """pi rejects an edit whose oldText occurs more than once."""
    stubbed, edits = stub(source, [span])
    return stubbed.count(edits[0]["oldText"]) == 1


def readable(text: str) -> bool:
    return len(text.split("\n")) <= READ_FULL_LINES and len(text.encode()) < PI_MAX_BYTES


class Trajectory:
    """Builds trajectory rows (see trajectory/README.md); every response is reply? + tool_call(s)."""

    def __init__(self, rng: random.Random):
        self.rng, self.rows = rng, []

    def say(self, options: list[str], **fmt) -> None:
        text = self.rng.choice(options).format(**fmt)
        if text:
            self.rows.append({"role": "assistant", "mode": "reply", "content": text})

    def call(self, name: str, args: dict, result: str) -> None:
        self.rows.append({"role": "assistant", "mode": "tool_call", "name": name, "args": args})
        self.rows.append({"role": "harness", "mode": "tool_result", "content": result, "status": "ok"})


def build_trajectory(ws: Path, rel: str, source: str, holes: list[tuple[tuple[int, int, int], str]],
                     index: dict, check_out: str, prompts: dict, rng: random.Random) -> list[dict]:
    """Rows of one task: locate/read the stubbed file, look up cross-file symbols, edit, `jac check`.

    The stub is written into the workspace while the task's `rg` calls run, so
    every tool result is what pi would have returned at that point.
    """
    spans, names = [s for s, _ in holes], [n for _, n in holes]
    stubbed, edits = stub(source, spans)
    (ws / rel).write_text(stubbed, encoding="utf-8")
    try:
        t, name = Trajectory(rng), names[0]
        multi   = len(holes) > 1
        no_path = not multi and rng.random() < NO_PATH_P
        if multi:
            targets = "\n".join(f"- `{n}`" for n in names)
            prompt  = rng.choice(prompts["tool_fim_multi"]).format(path=rel, targets=targets)
        elif no_path:
            prompt  = rng.choice(prompts["tool_fim_nopath"]).format(target=name)
        else:
            prompt  = rng.choice(prompts["tool_fim"]).format(target=name, path=rel)
        t.rows.append({"role": "user", "mode": "prompt", "content": prompt})

        hole_line = line_of(stubbed, stubbed.index(edits[0]["oldText"]))
        if no_path or not readable(stubbed):
            t.say(SAY_LOCATE, name=name)
            t.call("bash", {"command": (cmd := rg(ws, head_pattern(source, spans[0], name),
                                                  '-g "*.jac" .' if no_path else rel))[0]}, cmd[1])
        t.say(SAY_READ, path=rel)
        if readable(stubbed):
            t.call("read", {"path": rel}, pi_read(stubbed))
        else:
            offset = max(1, hole_line - READ_PAD)
            limit  = edits[0]["oldText"].count("\n") + 1 + 2 * READ_PAD
            t.call("read", {"path": rel, "offset": offset, "limit": limit}, pi_read(stubbed, offset, limit))

        body = "".join(source[s[1]:s[2]] for s in spans)
        for ref in cross_refs(body, rel, index)[: rng.randint(0, CTX_MAX)]:
            d   = index[ref][0]
            ctx = (ws / d["file"]).read_text(encoding="utf-8")
            t.say(SAY_CTX, ref=ref, name=name)
            t.call("bash", {"command": (cmd := rg(ws, f"{d['kind']}(:\\w+)? {ref}\\b", '-g "*.jac" .'))[0]}, cmd[1])
            limit = min(ctx[d["start"]:d["end"]].count("\n") + 3, CTX_READ_LINES)
            t.call("read", {"path": d["file"], "offset": d["line"], "limit": limit}, pi_read(ctx, d["line"], limit))

        t.say(SAY_EDIT)
        t.call("edit", {"path": rel, "edits": edits}, f"Successfully replaced {len(edits)} block(s) in {rel}.")
        t.say(SAY_CHECK)
        t.call("bash", {"command": f"jac check {rel} 2>&1 | tail -n {CHECK_TAIL}"}, check_out)
        t.say(SAY_DONE, names=", ".join(f"`{n}`" for n in names), path=rel)
        return t.rows
    finally:
        (ws / rel).write_text(source, encoding="utf-8")


def repo_trajectories(key: str, root: Path, exclude: set[str], prompts: dict) -> tuple[list[dict], list[dict]]:
    """All trajectories of one repo, built in a scratch copy; returns (trajectories, rejected files)."""
    rng = random.Random(f"{SEED}:{key}")
    trajs, rejected = [], []
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / root.name
        shutil.copytree(root, ws, ignore=shutil.ignore_patterns(*DROP_DIRS), symlinks=True)
        sources = jac_sources(ws, exclude)
        index   = symbol_index(sources)
        cwd     = f"{rng.choice(CWD_ROOTS)}/{root.name.split('__')[-1]}"
        for rel, source in sorted(sources.items()):
            holes = [h for h in fillable(source) if unique_edit(source, h[0])]
            if not holes:
                continue
            ok, check_out = jac_check(ws, rel)
            if not ok:
                rejected.append({"fp": f"{key}::{rel}", "reason": "jac check fails on the original file"})
                continue
            tasks = [[h] for h in rng.sample(holes, min(len(holes), HOLES_PER_FILE))]
            if len(holes) >= 2 and readable(source) and rng.random() < MULTI_P:
                tasks.append(sorted(rng.sample(holes, rng.randint(2, min(3, len(holes)))), key=lambda h: h[0]))
            for task in tasks:
                rows = build_trajectory(ws, rel, source, task, index, check_out, prompts, rng)
                trajs.append({
                    "meta": {"harness": HARNESS, "model": "synthetic", "cwd": cwd, "repo": key, "file": rel,
                             "holes": [n for _, n in task],
                             "body": "\n".join(source[s[1]:s[2]] for s, _ in task)},
                    "rows": rows,
                })
    return trajs, rejected


def build_record(traj: dict, harness: dict, n_tokens) -> dict:
    """Trajectory -> SFT record: chat messages (tool-call arguments as JSON strings) + tool schemas."""
    msgs = to_template_input(traj, harness["system"].replace("{cwd}", traj["meta"]["cwd"]))
    for m in msgs:
        for c in m.get("tool_calls", []):
            c["function"]["arguments"] = json.dumps(c["function"]["arguments"], ensure_ascii=False)
    meta = traj["meta"]
    return {
        "messages": msgs,
        "tools":    json.dumps(harness["tools"], ensure_ascii=False),  # a string: Arrow would merge the schemas' keys
        "meta": {
            "source":     SOURCE,
            "format":     DS_FORMAT,
            "class":      classify(meta["body"]),
            "task_type":  TASK_TYPE,
            "fp":         f"{meta['repo']}::{meta['file']}#{'+'.join(meta['holes'])}",
            "harness":    HARNESS,
            "repo":       meta["repo"],
            "file":       meta["file"],
            "holes":      meta["holes"],
            "tool_calls": sum(r["mode"] == "tool_call" for r in traj["rows"]),
            "tokens":     n_tokens(msgs, harness["tools"]),
        },
    }


def token_counter(tokenizer_name: str):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(tokenizer_name)
    def n_tokens(msgs: list[dict], tools: list[dict]) -> int:
        parsed = [{**m, "tool_calls": [{**c, "function": {**c["function"], "arguments": json.loads(c["function"]["arguments"])}}
                                       for c in m["tool_calls"]]} if "tool_calls" in m else m for m in msgs]
        text = tok.apply_chat_template(parsed, tools=tools, tokenize=False)
        return len(tok(text, add_special_tokens=False)["input_ids"])
    return n_tokens


def split_by_file(records: list[dict], valid_size: float, rng: random.Random) -> tuple[list[dict], float]:
    """Order records valid-files-first; returns (records, valid_size for split_and_write)."""
    files = sorted({(r["meta"]["repo"], r["meta"]["file"]) for r in records})
    rng.shuffle(files)
    held, n = set(), 0
    for f in files:
        if n >= valid_size * len(records):
            break
        held.add(f)
        n += sum((r["meta"]["repo"], r["meta"]["file"]) == f for r in records)
    valid = [r for r in records if (r["meta"]["repo"], r["meta"]["file"]) in held]
    train = [r for r in records if (r["meta"]["repo"], r["meta"]["file"]) not in held]
    return valid + train, (len(valid) + 0.5) / len(records)     # +0.5: int(N * size) must not floor below len(valid)


def repo2tool_fim(in_dir=IN_DIR, out_dir=OUT_DIR, format=OUT_FORMAT, max_tokens=MAX_TOKENS, limit=None):
    """One pi trajectory per sampled hole (plus some multi-hole ones) over every repo in `in_dir`.

    Writes the raw trajectories to TRAJ_OUT, SFT records (train/valid split by
    file) to `out_dir`, and `rejected.jsonl` (files failing `jac check`, records
    over `max_tokens`). `limit` caps the number of repos (smoke runs).
    """
    in_dir, out_dir = Path(in_dir), Path(out_dir)
    meta    = load_meta(in_dir / "meta.json")
    prompts = load_prompts(PROMPT, "tool_fim", "tool_fim_nopath", "tool_fim_multi")
    harness = json.loads(Path(HARNESS_SPEC).read_text())
    repos   = list(iter_repos(in_dir))[:limit]
    if not repos:
        raise FileNotFoundError(f"No repos found in: {in_dir}")

    with ThreadPoolExecutor(WORKERS) as pool:
        results = list(pool.map(lambda kr: repo_trajectories(kr[0], kr[1], set(meta["exclude_files"].get(kr[0], [])), prompts),
                                repos))
    trajs    = [t for ts, _ in results for t in ts]
    rejected = [r for _, rs in results for r in rs]
    write_trajectories(trajs, TRAJ_OUT)

    n_tokens = token_counter(TOKENIZER)
    records  = []
    for traj in trajs:
        rec = build_record(redact(traj), harness, n_tokens)
        if rec["meta"]["tokens"] > max_tokens:
            rejected.append({"fp": rec["meta"]["fp"], "reason": f"{rec['meta']['tokens']} tokens > {max_tokens}"})
            continue
        records.append(rec)

    rng = random.Random(SEED)
    rng.shuffle(records)
    records, valid_size = split_by_file(records, VALID_SIZE, rng)
    counts = split_and_write(records, out_dir, valid_size, format)
    with (out_dir / "rejected.jsonl").open("w", encoding="utf-8") as f:
        for row in rejected:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    report(counts, out_dir)
    tokens = sorted(r["meta"]["tokens"] for r in records)
    print(f"  {len(trajs)} trajectories from {len(repos)} repos; {len(rejected)} rejected (see rejected.jsonl)")
    print(f"  tokens: total {sum(tokens):,}, median {tokens[len(tokens) // 2]}, max {tokens[-1]}")

# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--max-token", dest="max_tokens", type=int, default=MAX_TOKENS,
                     help="drop records longer than this (chat-template tokens incl. tools)")
    cli.add_argument("--limit", type=int, default=None, help="first N repos only (smoke run)")
    cli.add_argument("--out-dir", default=OUT_DIR)
    args = cli.parse_args()
    repo2tool_fim(out_dir=args.out_dir, max_tokens=args.max_tokens, limit=args.limit)
