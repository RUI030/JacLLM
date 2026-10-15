"""Tool-use FIM eval: real pi agent fills held-out stubbed Jac bodies against an OpenAI-compatible server."""

import argparse, difflib, json, os, re, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from utils.jac_cli       import check_path
from dataset.parser.repo import DROP_DIRS

# Setting =================================================
ROOT     = Path(__file__).resolve().parent.parent.parent.parent
DS_ROOT  = ROOT / "dataset"
RAW_REPO = DS_ROOT / "raw/repo"
TASK     = "tool_fim"
DS_NAME  = "repo-all-pi"
OUT_ROOT = ROOT / "output/eval" / TASK

PI_FLAGS = ["-p", "--mode", "json", "--no-session", "--offline", "--no-mcp", "--no-context-files",
            "--no-skills", "--no-extensions", "--no-prompt-templates"]   # match the captured training system prompt
TIMEOUT  = 600                          # seconds per task (whole agent run)
STUB     = "# TODO: implement"

# Functions ===============================================
def load_tasks(ds: str, split: str, limit: int | None) -> list[dict]:
    rows = [json.loads(l) for l in (DS_ROOT / "sft" / TASK / ds / f"{split}.jsonl").open()]
    return rows[:limit]


def edits_of(record: dict) -> list[dict]:
    """The reference `edit` call's edits (oldText = stub, newText = original body)."""
    for m in record["messages"]:
        for c in m.get("tool_calls") or []:
            if c["function"]["name"] == "edit":
                return json.loads(c["function"]["arguments"])["edits"]
    raise ValueError(f"no edit call in {record['meta']['fp']}")


def workspace(record: dict, tmp: Path) -> tuple[Path, str]:
    """Copy the repo and stub the task's bodies; returns (workspace, original file text)."""
    meta = record["meta"]
    ws   = tmp / Path(meta["repo"]).name
    shutil.copytree(RAW_REPO / meta["repo"], ws, ignore=shutil.ignore_patterns(*DROP_DIRS), symlinks=True)
    path     = ws / meta["file"]
    original = path.read_text(encoding="utf-8")
    stubbed  = original
    for e in edits_of(record):
        stubbed = stubbed.replace(e["newText"], e["oldText"], 1)
    path.write_text(stubbed, encoding="utf-8")
    return ws, original


def agent_dir(base_url: str, model: str, out_dir: Path) -> Path:
    """A pi agent dir whose only provider is the server under test (no MCP, skills or extensions)."""
    d = out_dir / "pi_agent"
    d.mkdir(parents=True, exist_ok=True)
    (d / "models.json").write_text(json.dumps({"providers": {"local": {
        "baseUrl": base_url, "api": "openai-completions", "apiKey": "local", "models": [{"id": model}]}}}))
    return d


def tool_calls(events: list[dict]) -> list[dict]:
    """`{name, args}` of every tool call, from the assistant `message_end` records."""
    calls = []
    for ev in events:
        msg = ev.get("message") or {}
        if ev.get("type") == "message_end" and msg.get("role") == "assistant":
            calls += [{"name": b.get("name"), "args": b.get("arguments")}
                      for b in msg.get("content", []) if isinstance(b, dict) and b.get("type") == "toolCall"]
    return calls


def body_after(text: str, edit: dict) -> str | None:
    """The filled declaration in `text`: from the stub's head line to the next line at the head's indent."""
    head = edit["oldText"].split("\n")[0]
    at   = text.find(head)
    if at < 0:
        return None
    indent = re.match(r"[ \t]*", head).group(0)
    m = re.compile(rf"^{indent}\}}", re.M).search(text, at + len(head))
    return text[at: m.end()] if m else None


def run_task(record: dict, prompt: str, model: str, agent: Path, out_dir: Path) -> dict:
    """One pi run on a fresh workspace; returns the graded row and saves the event stream."""
    meta = record["meta"]
    with tempfile.TemporaryDirectory() as tmp:
        ws, original = workspace(record, Path(tmp))
        start = time.time()
        try:
            proc = subprocess.run(["pi", *PI_FLAGS, "--model", f"local/{model}", prompt], cwd=ws,
                                  env={**os.environ, "PI_CODING_AGENT_DIR": str(agent)},
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=TIMEOUT)
            stdout, timed_out = proc.stdout, False
        except subprocess.TimeoutExpired as exc:
            stdout, timed_out = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""), True
        seconds = time.time() - start
        events  = [json.loads(l) for l in stdout.splitlines() if l.startswith("{")]
        after   = (ws / meta["file"]).read_text(encoding="utf-8")
        ok, out = check_path(meta["file"], cwd=ws, timeout=120)

    edits  = edits_of(record)
    filled = [body_after(after, e) for e in edits]
    sim    = [difflib.SequenceMatcher(None, f or "", e["newText"]).ratio() for f, e in zip(filled, edits)]
    calls  = tool_calls(events)
    name   = meta["fp"].replace("/", "__").replace("::", "--")
    (out_dir / "transcripts").mkdir(exist_ok=True)
    (out_dir / "transcripts" / f"{name}.jsonl").write_text(stdout)
    return {
        "fp":          meta["fp"],
        "holes":       meta["holes"],
        "stub_left":   STUB in after,
        "check":       ok,
        "check_out":   out[-600:] if not ok else "",
        "exact":       after == original,
        "similarity":  sum(sim) / len(sim),
        "tool_calls":  len(calls),
        "tools":       [c["name"] for c in calls],
        "edited_file": any(c["name"] in ("edit", "write") and (c["args"] or {}).get("path", "").endswith(meta["file"]) for c in calls),
        "timed_out":   timed_out,
        "seconds":     round(seconds, 1),
        "filled":      filled,
    }


def summarize(rows: list[dict]) -> dict:
    n    = len(rows)
    rate = lambda k: round(sum(bool(r[k]) for r in rows) / n, 4)
    solved = [r for r in rows if not r["stub_left"] and r["check"]]
    return {
        "n":                 n,
        "solved":            round(len(solved) / n, 4),   # stub replaced and `jac check` passes
        "stub_left":         rate("stub_left"),
        "check":             rate("check"),
        "exact":             rate("exact"),
        "edited_file":       rate("edited_file"),
        "timed_out":         rate("timed_out"),
        "similarity_mean":   round(sum(r["similarity"] for r in rows) / n, 4),
        "tool_calls_mean":   round(sum(r["tool_calls"] for r in rows) / n, 2),
        "seconds_mean":      round(sum(r["seconds"] for r in rows) / n, 1),
    }


def run_eval(base_url: str, model: str, tag: str, ds: str = DS_NAME, split: str = "valid",
             limit: int | None = None, workers: int = 4) -> Path:
    """Run every task of `split` through pi; writes results.jsonl, report.json and transcripts/."""
    out_dir = OUT_ROOT / ds / f"{tag}_{time.strftime('%m-%d_%H-%M')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    agent = agent_dir(base_url, model, out_dir)
    tasks = load_tasks(ds, split, limit)
    prompt_of = lambda r: next(m["content"] for m in r["messages"] if m["role"] == "user")
    with ThreadPoolExecutor(workers) as pool:
        rows = list(pool.map(lambda r: run_task(r, prompt_of(r), model, agent, out_dir), tasks))
    with (out_dir / "results.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    report = {"tag": tag, "model": model, "ds": ds, "split": split, **summarize(rows)}
    (out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return out_dir

# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    cli.add_argument("--model",    default="local", help="model id the server answers to")
    cli.add_argument("--tag",      required=True)
    cli.add_argument("--ds",       default=DS_NAME)
    cli.add_argument("--split",    default="valid")
    cli.add_argument("--limit",    type=int, default=None)
    cli.add_argument("--workers",  type=int, default=4)
    args = cli.parse_args()
    run_eval(args.base_url, args.model, args.tag, args.ds, args.split, args.limit, args.workers)
