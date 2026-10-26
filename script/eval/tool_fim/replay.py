"""Replay tool_fim records through real pi and report tool results that differ from the recorded ones."""

import argparse, json, os, subprocess, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from run_eval import DS_NAME, PI_FLAGS, TIMEOUT, agent_dir, load_tasks, workspace

# Setting =================================================
MODEL    = "replay"
VOLATILE = ("passed in",)               # tool results that carry timings; a difference there is not a mismatch

# Functions ===============================================
def chunk(delta: dict, finish: str | None = None) -> bytes:
    body = {"id": "r", "object": "chat.completion.chunk", "created": 0, "model": MODEL,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
    return f"data: {json.dumps(body)}\n\n".encode()


def serve(record: dict) -> tuple[HTTPServer, list[dict]]:
    """A fake model server on a free port that answers request n with the record's n-th assistant turn;
    returns it and the list it appends each request body to."""
    turns, requests = [m for m in record["messages"] if m["role"] == "assistant"], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(req)
            n = sum(m["role"] == "assistant" for m in req["messages"])
            m = turns[n] if n < len(turns) else {"content": ""}
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(chunk({"role": "assistant", "content": m.get("content") or ""}))
            for i, c in enumerate(m.get("tool_calls") or []):
                self.wfile.write(chunk({"tool_calls": [{"index": i, "id": f"c{n}_{i}", "type": "function",
                                                        "function": c["function"]}]}))
            self.wfile.write(chunk({}, "tool_calls" if m.get("tool_calls") else "stop"))
            self.wfile.write(b"data: [DONE]\n\n")

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, requests


def replay(record: dict, tmp: Path) -> list[tuple]:
    """Run pi on the stubbed workspace against the record; returns the differing tool results
    as (index, recorded, replayed), plus ("count", recorded, replayed) when the counts differ."""
    server, requests = serve(record)
    try:
        agent = agent_dir(f"http://127.0.0.1:{server.server_port}/v1", MODEL, tmp)
        ws, _ = workspace(record, tmp)
        prompt = next(m["content"] for m in record["messages"] if m["role"] == "user")
        subprocess.run(["pi", *PI_FLAGS, "--model", f"local/{MODEL}", prompt], cwd=ws,
                       env={**os.environ, "PI_CODING_AGENT_DIR": str(agent)},
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=TIMEOUT)
    finally:
        server.shutdown()
    got  = [m["content"] for m in requests[-1]["messages"] if m["role"] == "tool"] if requests else []
    want = [m["content"] for m in record["messages"] if m["role"] == "tool"]
    diffs = [(i, w, g) for i, (w, g) in enumerate(zip(want, got))
             if w != g and not any(v in w for v in VOLATILE)]
    if len(got) != len(want):
        diffs.append(("count", len(want), len(got)))
    return diffs

# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--ds",    default=DS_NAME)
    cli.add_argument("--split", default="valid")
    cli.add_argument("--limit", type=int, default=5)
    args = cli.parse_args()

    records, bad = load_tasks(args.ds, args.split, args.limit), 0
    for k, record in enumerate(records):
        with tempfile.TemporaryDirectory() as tmp:
            diffs = replay(record, Path(tmp))
        bad += bool(diffs)
        print(k, record["meta"]["fp"][:80], "DIFF" if diffs else "OK",
              [(d[0], repr(d[1])[:200], repr(d[2])[:200]) for d in diffs[:2]])
    print(f"mismatched: {bad} / {len(records)}")
