"""Render one record of an SFT chat JSONL (`{"messages": [...], "tools": [...]}`) as a readable Markdown file.

Usage:
    python script/dataset/render.py --in dataset/sft/tool_use/codex/valid.jsonl --n 0 [--out record.md] [--tools]
Roles become `## ROLE` headings, tool calls and tool results go in fenced blocks (fence grows past any backticks inside).
"""

import argparse, json
from pathlib import Path

# Setting =================================================
OUT_DIR   = "output/render"      # default output: <OUT_DIR>/<stem>-<n>.md
MAX_CHARS = 0                    # truncate each block to this many chars; 0 => no limit
CODE_ARGS = {"cmd": "bash", "input": "diff", "code": "js", "content": ""}   # tool-arg keys shown as raw code blocks


# Functions ===============================================
def fence(text: str, lang: str = "") -> str:
    ticks = "`" * max(3, max((len(r) for r in text.replace("\n", " ").split(" ") if r and set(r) == {"`"}), default=0) + 1)
    if MAX_CHARS and len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + f"\n... [{len(text) - MAX_CHARS} more chars]"
    return f"{ticks}{lang}\n{text}\n{ticks}"


def render_call(c: dict) -> str:
    fn = c.get("function", c)
    name, args = fn.get("name"), fn.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return f"**tool call** `{name}`\n\n{fence(args)}"
    out = [f"**tool call** `{name}`"]
    rest = {}
    for k, v in (args or {}).items():
        if k in CODE_ARGS and isinstance(v, str):
            out.append(f"`{k}`:\n\n{fence(v, CODE_ARGS[k])}")
        else:
            rest[k] = v
    if rest:
        out.append(fence(json.dumps(rest, ensure_ascii=False, indent=2), "json"))
    return "\n\n".join(out)


def render_message(m: dict) -> str:
    role = m["role"].upper()
    tag = ""
    if m.get("weight") is not None:
        tag = f" (weight {m['weight']})"
    if role == "TOOL":
        tag += f" `{m.get('tool_call_id', '')}`"
    parts = [f"## {role}{tag}"]
    if m.get("reasoning_content"):
        parts.append("**reasoning**\n\n" + fence(m["reasoning_content"]))
    content = m.get("content")
    if content:
        parts.append(fence(content) if role in ("TOOL", "SYSTEM") else content)
    parts += [render_call(c) for c in m.get("tool_calls") or []]
    return "\n\n".join(parts)


def render_record(rec: dict, with_tools: bool = False) -> str:
    head = ["# Record", fence(json.dumps(rec.get("meta", {}), ensure_ascii=False, indent=2), "json")]
    if with_tools and rec.get("tools"):
        tools = json.loads(rec["tools"]) if isinstance(rec["tools"], str) else rec["tools"]
        names = [t["function"]["name"] for t in tools]
        head.append(f"**tools**: {', '.join(names)}")
    return "\n\n".join(head + [render_message(m) for m in rec["messages"]]) + "\n"


def load_record(fp: str, n: int) -> dict:
    with open(fp, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == n:
                return json.loads(line)
    raise SystemExit(f"{fp} has fewer than {n + 1} records")


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="in_fp", required=True)
    ap.add_argument("--n", type=int, default=0, help="0-based line number of the record")
    ap.add_argument("--out", default=None)
    ap.add_argument("--tools", action="store_true", help="list the tool names the record carries")
    ap.add_argument("--max-chars", type=int, default=MAX_CHARS)
    a = ap.parse_args()
    MAX_CHARS = a.max_chars
    out = Path(a.out or f"{OUT_DIR}/{Path(a.in_fp).stem}-{a.n}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_record(load_record(a.in_fp, a.n), a.tools), encoding="utf-8")
    print(out)
