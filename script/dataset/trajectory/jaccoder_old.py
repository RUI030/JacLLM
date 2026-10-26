"""JacHammer JacCoder chat export (jaccoder_conversations.jsonl, to 2026-10-14) -> trajectory JSONL (see README.md).

The export keeps only user prompts, the final assistant text of each turn and the
write_code / edit_code / delete_code calls. Reads, searches, runs, skills, reasoning
and the per-turn opener are not in it, so a trajectory is the edits without what led to them.

Replaying the writes and edits of a conversation gives the exact content of every file it
wrote. Where that content is known, a `read_file` call and result (rows marked `synthetic`)
are inserted before an edit that needs fresh content. Edits to a file whose content is not
known (a template or earlier file), edits the replay can't verify, and calls that failed get
`weight: 0`, so the model is not trained on `old_string`s it never saw.
"""

import argparse, json, random, re, shlex
import sys
from collections import Counter, deque
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from dataset.trajectory.common import mark_loops, write_trajectories

# Setting =================================================
HARNESS = "jaccoder"
DS_ROOT = f"{Path(__file__).resolve().parent}/../../../dataset"
IN_FILE = f"{DS_ROOT}/raw/session/jaccoder_session_logs/jachammer_prod_2026-10-15/jaccoder_conversations.jsonl"
OUT     = f"{DS_ROOT}/raw/trajectory/{HARNESS}_old.jsonl"
SPEC    = Path(__file__).resolve().parent / "harness" / "jaccoder.json"
ARGS    = {                          # tool -> (log field -> schema argument); all are required to emit the call
    "write_code":  {"file": "file_path", "content": "content"},
    "edit_code":   {"file": "file_path", "old": "old_string", "new": "new_string"},
    "delete_code": {"file": "file_path"},
}

PI_SPEC  = Path(__file__).resolve().parent / "harness" / "pi.json"
PI_OUT   = f"{DS_ROOT}/raw/trajectory/{HARNESS}_old_pi.jsonl"
CWD_ROOTS = ["/home/dev", "/home/user/projects", "/workspace", "/home/alex/code", "/srv/app"]   # as sft/tool_fim.py
READ_LINES = 2000                    # read_file's default limit: longer files show only their head

# Functions ===============================================
def numbered(text: str) -> str:
    """Content as read_file returns it: `N: line` for the first READ_LINES lines."""
    return "\n".join(f"{i}: {line}" for i, line in enumerate(text.split("\n")[:READ_LINES], 1))


def mock_read(path: str) -> tuple[dict, dict]:
    return ({"role": "assistant", "mode": "tool_call", "name": "read_file", "args": {"file_path": path}, "synthetic": True},
            {"role": "harness", "mode": "tool_result", "content": None, "status": "ok", "synthetic": True})


def tool_call(change: dict) -> tuple[dict, dict] | str:
    """One logged code change -> (tool_call row, tool_result row), or the reason it can't be used."""
    name = change.get("tool")
    if name not in ARGS:
        return "unknown_tool"
    if change.get("truncated"):
        return "truncated"
    if change.get("status") != "done" or not change.get("result"):
        return "incomplete"           # still running when logged, or no result recorded
    if any(change.get(k) is None for k in ARGS[name]):
        return "incomplete"
    args = {arg: change[k] for k, arg in ARGS[name].items()}
    if name == "edit_code" and change.get("replace_all") is not None:
        args["replace_all"] = str(change["replace_all"]).lower() == "true"
    ok = not change["result"].startswith(("Error", "Tool error"))
    return ({"role": "assistant", "mode": "tool_call", "name": name, "args": args},
            {"role": "harness", "mode": "tool_result", "content": change["result"], "status": "ok" if ok else "error"})


def convert_conversation(conv: dict, count: Counter) -> dict | None:
    """One conversation -> one trajectory, or None when it holds no usable model output."""
    rows  = []
    files = {}                       # path -> replayed content; absent = unknown
    seen  = {}                       # path -> (user turn, content) last shown to the model (written or read)
    n_user = 0
    for turn in conv["turns"]:
        if turn["role"] == "error":
            count["error_turns_dropped"] += 1
        elif turn["role"] == "user":
            n_user += 1
            text = turn["content"] + ("\n[image]" * turn.get("images_attached", 0))
            rows.append({"role": "user", "mode": "prompt", "content": text})
        else:
            for change in turn.get("code_changes", []):
                got = tool_call(change)
                if isinstance(got, str):
                    count[f"changes_dropped_{got}"] += 1
                    continue
                call, result = got
                name, args, path, ok = call["name"], call["args"], call["args"]["file_path"], result["status"] == "ok"
                reason = None if ok else "failed"
                if name == "edit_code":
                    cur = files.get(path)
                    known = cur is not None and args["old_string"] in cur
                    if cur is None:
                        reason = reason or "unseen_file"
                    elif not known and ok:
                        reason = "unverified"      # the replay missed an edit that the real file had
                        files.pop(path)
                    elif known and (path not in seen or seen[path] != (n_user, cur)) \
                            and args["old_string"] in "\n".join(cur.split("\n")[:READ_LINES]):
                        r_call, r_res = mock_read(path)
                        r_res["content"] = numbered(cur)
                        rows += [r_call, r_res]
                        seen[path] = (n_user, cur)
                        count["mock_reads"] += 1
                    if known and ok:
                        files[path] = cur.replace(args["old_string"], args["new_string"],
                                                  -1 if args.get("replace_all") else 1)
                elif ok and name == "write_code":
                    files[path] = args["content"]
                    seen[path]  = (n_user, args["content"])
                elif ok:                                  # delete_code
                    files.pop(path, None)
                    seen.pop(path, None)
                if reason:
                    call["weight"], call["masked"] = 0, reason
                rows += [call, result]
            if turn["content"].strip():
                rows.append({"role": "assistant", "mode": "reply", "content": turn["content"]})
    while rows and rows[0]["role"] != "user":
        rows.pop(0)                  # chat templates need a human query before the first reply
    if not any(r["role"] == "assistant" for r in rows):
        return None
    mark_loops(rows)
    spec = json.loads(SPEC.read_text())
    meta = {"harness": HARNESS, "model": "unknown", "session_id": conv["conversation_id"], "segment": 0,
            "parent": None, "source": "export_old", "project_type": conv.get("project_type"),
            "template_id": conv.get("template_id"), "started_at": conv.get("started_at")}
    return {"meta": meta, "tools": spec["tools"],
            "rows": [{"role": "harness", "mode": "system", "content": spec["system"]}] + rows}


def to_pi(traj: dict) -> dict:
    """JacCoder trajectory -> the same session in pi's tools (read / write / edit / bash), wording and prompt.

    The system prompt and tool schemas are not stored: pi's come from harness/pi.json at SFT time
    (`meta.cwd` fills its `{cwd}`). A tool result keeps JacCoder's text only when the call failed;
    a successful one gets pi's own message, so JacCoder's appended `jac check` and preview output is lost.
    Paths stay relative to `cwd`, which pi accepts. A call with `replace_all` can't be one pi edit
    (oldText must be unique) and is masked.
    """
    rows, calls = [], deque()
    for r in traj["rows"]:
        if r["mode"] == "system":
            continue
        r = dict(r)
        if r["mode"] == "tool_call":
            name, a = r["name"], r["args"]
            path = a["file_path"]
            if name == "read_file":
                r["name"], r["args"] = "read", {"path": path}
            elif name == "write_code":
                r["name"], r["args"] = "write", {"path": path, "content": a["content"]}
            elif name == "edit_code":
                r["name"], r["args"] = "edit", {"path": path, "edits": [{"oldText": a["old_string"], "newText": a["new_string"]}]}
                if a.get("replace_all"):
                    r.update(weight=0, masked="replace_all")
            else:
                r["name"], r["args"] = "bash", {"command": f"rm {shlex.quote(path)}"}
            calls.append((name, path))
        elif r["mode"] == "tool_result":
            name, path = calls.popleft()
            if r["status"] == "ok":
                r["content"] = {"read_file": re.sub(r"(?m)^\d+: ", "", r["content"]),
                                "write_code": f"Successfully wrote to {path}",
                                "edit_code": f"Successfully replaced 1 block(s) in {path}.",
                                "delete_code": "(no output)"}[name]
        rows.append(r)
    sid = traj["meta"]["session_id"]
    cwd = f"{random.Random(sid).choice(CWD_ROOTS)}/app"
    meta = {**traj["meta"], "harness": "pi", "source_harness": HARNESS, "cwd": cwd}
    return {"meta": meta, "rows": rows}


def convert(in_file=IN_FILE, out=OUT, harness=HARNESS):
    """Convert every conversation, write JSONL + stats; `harness="pi"` re-expresses it in pi's tools."""
    count = Counter()
    trajs = []
    for line in open(in_file, encoding="utf-8"):
        count["conversations"] += 1
        t = convert_conversation(json.loads(line), count)
        if t:
            trajs.append(to_pi(t) if harness == "pi" else t)
        else:
            count["conversations_without_model_output"] += 1
    st = write_trajectories(trajs, out, dict(count))
    print(json.dumps(st, indent=2))
    print(f"Wrote {len(trajs)} trajectories to {out}")


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in-file", default=IN_FILE)
    ap.add_argument("--harness", choices=[HARNESS, "pi"], default=HARNESS, help="tools the trajectory is written in")
    ap.add_argument("--out",     help="default: raw/trajectory/jaccoder_old[_pi].jsonl")
    args = ap.parse_args()
    convert(args.in_file, args.out or (PI_OUT if args.harness == "pi" else OUT), args.harness)
