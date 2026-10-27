"""Render agent sessions as a readable HTML (or Markdown) timeline: thinking, replies, tool calls, tool results, images.

Inputs (auto-detected; a folder takes every matching file in it, sorted):
  proxy     JSONL from script/eval/agent/log_proxy.py (output/serve/<model>/calls.jsonl): raw /v1/chat/completions requests and responses (SSE or JSON).
            Calls are grouped into sessions by system prompt + first user message; each call shows only the
            messages that are new since the previous call, and a context that shrank is marked as compaction.
  jaccoder  jac_coder LLM traces (<hhmmss>_<turn>.json.gz, `calls[].new_messages/reply/usage`), e.g. dataset/raw/prod.
  sft       rows {"messages", "tools", "meta"} such as dataset/raw/prod/sft/prod-64k; assistant weight is shown.
  traj      rows {"meta", "rows"} in the trajectory format of this folder's README.

Flags: a tool call identical to one of the last 4 in the session (so A,B,A,B loops count), a tool result starting with an error / LOOP DETECTED,
and finish_reason "length" are highlighted and listed at the top of each session.

    python script/dataset/trajectory/view.py output/eval/agent/<scenario>/<run>/calls.jsonl --client pi --out view.html
    python script/dataset/trajectory/view.py dataset/raw/prod/2026-10-22/prj_x --format md
"""

import argparse, base64, gzip, hashlib, html, json, mimetypes, os, re
from collections import Counter
from pathlib import Path

# Setting =================================================
MAX_CHARS  = 6000                 # longer text is clipped (the clipped length is shown)
OPEN_CHARS = 600                  # tool results and thinking up to this long render expanded
ERROR_RE   = re.compile(r"^\s*(error|LOOP DETECTED|STDERR|Traceback|.*\bFAILED\b)", re.I)
REPEAT_WIN = 4                     # a call equal to one of this many previous calls is a repeat (catches A,B,A,B loops)
LONG_ARGS  = {"content", "new_string", "old_string", "code", "patch", "input"}   # tool args shown as code blocks
CLIENTS    = [("opencode", re.compile(r"running in OpenCode|You name conversations|<conversation-checkpoint>")),
              ("pi", re.compile(r"operating inside pi, a coding agent|context summarization assistant|"
                                r"conversation history before this point was compacted")),
              ("jaccoder", re.compile(r"JacCoder|MainAgent\(|PlannerAgent"))]   # proxy logs: which agent sent a call


# Functions ===============================================
# --- reading ---
def records(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        if path.name.removesuffix(".gz").endswith(".jsonl"):
            for line in f:
                if line.strip():
                    yield json.loads(line)
        else:
            yield json.load(f)


def kind_of(rec: dict) -> str:
    if "request" in rec and "response" in rec and "path" in rec:
        return "proxy"
    if "calls" in rec and "turn_id" in rec:
        return "jaccoder"
    if "rows" in rec and "meta" in rec:
        return "traj"
    if "messages" in rec:
        return "sft"
    raise ValueError(f"unknown record shape: {sorted(rec)[:8]}")


def input_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.is_file() and re.search(r"\.jsonl?(\.gz)?$", p.name))


# --- normalising: every source becomes sessions of events ---
def text_parts(content) -> list[dict]:
    """Message content -> [{"text": str} | {"image": url-or-path}]."""
    if content is None:
        return []
    if isinstance(content, str):
        return [{"text": content}] if content else []
    out = []
    for p in content:
        if not isinstance(p, dict):
            out.append({"text": str(p)})
        elif p.get("type") == "text":
            out.append({"text": p.get("text", "")})
        elif p.get("type") in ("image_url", "input_image"):
            u = p.get("image_url")
            out.append({"image": u.get("url") if isinstance(u, dict) else u})
        elif p.get("type") == "image":
            out.append({"image": p.get("image") or p.get("url") or ""})
        else:
            out.append({"text": json.dumps(p, ensure_ascii=False)[:500]})
    return out


def tool_calls_of(msg: dict) -> list[dict]:
    calls = []
    for c in msg.get("tool_calls") or []:
        f = c.get("function", c)
        args = f.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                args = {"<unparsed>": args}
        calls.append({"name": f.get("name", "?"), "args": args or {}, "id": c.get("id")})
    return calls


def msg_event(m: dict, **extra) -> dict:
    role = m.get("role")
    ev = {"kind": {"system": "system", "user": "user", "tool": "tool", "assistant": "assistant"}.get(role, "user"),
          "parts": text_parts(m.get("content")), **extra}
    if role == "assistant":
        ev["reasoning"] = m.get("reasoning_content") or m.get("reasoning") or ""
        ev["calls"] = tool_calls_of(m)
        if "weight" in m:
            ev["weight"] = m["weight"]
    if role == "tool":
        ev["name"] = m.get("name")
    return ev


def parse_response(resp) -> dict:
    """Proxy response (raw SSE text or a JSON body) -> assistant message + usage + finish_reason."""
    if isinstance(resp, dict):
        ch = (resp.get("choices") or [{}])[0]
        return {"msg": ch.get("message", {}), "usage": resp.get("usage"), "finish": ch.get("finish_reason"),
                "error": resp.get("error")}
    content, reasoning, calls, usage, finish = "", "", {}, None, None
    for line in (resp or "").splitlines():
        if not line.startswith("data: {"):
            continue
        d = json.loads(line[6:])
        usage = d.get("usage") or usage
        for ch in d.get("choices") or []:
            finish = ch.get("finish_reason") or finish
            dl = ch.get("delta") or {}
            content += dl.get("content") or ""
            reasoning += dl.get("reasoning_content") or dl.get("reasoning") or ""
            for c in dl.get("tool_calls") or []:
                e = calls.setdefault(c.get("index", 0), {"function": {"name": "", "arguments": ""}})
                f = c.get("function") or {}
                e["function"]["name"] += f.get("name") or ""
                e["function"]["arguments"] += f.get("arguments") or ""
    msg = {"role": "assistant", "content": content, "reasoning_content": reasoning,
           "tool_calls": [calls[k] for k in sorted(calls)]}
    return {"msg": msg, "usage": usage, "finish": finish, "error": None}


def msg_key(m: dict) -> str:
    """Loose identity of a message across calls (clients re-serialise replies slightly differently)."""
    calls = [(c["name"], json.dumps(c["args"], sort_keys=True)) for c in tool_calls_of(m)]
    text = "".join(p.get("text", "") or p.get("image", "")[:64] for p in text_parts(m.get("content"))).strip()
    return json.dumps([m.get("role"), text, calls], ensure_ascii=False)


def client_of(rec: dict, msgs: list[dict]) -> str:
    """The agent behind a proxy call: its User-Agent when the proxy logged one, else a system/first-message pattern."""
    ua = ((rec.get("headers") or {}).get("user-agent") or "").lower()
    for name in ("opencode", "pi", "litellm"):
        if name in ua:
            return {"litellm": "jaccoder"}.get(name, name)
    head = " ".join("".join(p.get("text", "") for p in text_parts(m.get("content")))[:600] for m in msgs[:3])
    return next((name for name, pat in CLIENTS if pat.search(head)), "other")


def proxy_sessions(recs: list[dict]) -> list[dict]:
    sessions, by_key = [], {}
    for i, r in enumerate(recs):
        req = r.get("request") or {}
        if not isinstance(req, dict) or "messages" not in req:
            continue
        msgs = req["messages"]
        sys_txt = "".join(p.get("text", "") for p in text_parts(msgs[0].get("content"))) if msgs and msgs[0].get("role") == "system" else ""
        first_user = next((msg_key(m) for m in msgs if m.get("role") == "user"), "")
        key = hashlib.sha1((sys_txt + first_user).encode()).hexdigest()
        if key not in by_key:
            title = re.sub(r"\s+", " ", json.loads(first_user)[1] if first_user else "(no user message)")[:120]
            client = client_of(r, msgs)
            by_key[key] = {"title": f"[{client}] {title}", "client": client, "events": [], "prev": [], "calls": 0,
                           "tools": req.get("tools")}
            sessions.append(by_key[key])
        s = by_key[key]
        keys = [msg_key(m) for m in msgs]
        prev = s["prev"]
        k = 0
        while k < min(len(prev), len(keys)) and prev[k] == keys[k]:
            k += 1
        if prev and k < len(prev):
            s["events"].append({"kind": "compaction", "text": f"context rewritten: {len(prev)} messages before, "
                                f"first {k} kept, {len(keys) - k} now follow"})
        for m in msgs[k:]:
            s["events"].append(msg_event(m))
        out = parse_response(r.get("response"))
        s["calls"] += 1
        s["events"].append(msg_event(out["msg"], call=s["calls"], ts=r.get("ts"), latency=r.get("latency_s"),
                                     usage=out["usage"], finish=out["finish"], status=r.get("status"),
                                     max_tokens=req.get("max_tokens"), error=out["error"]))
        s["prev"] = keys + [msg_key(out["msg"])]
    return sessions


def jaccoder_session(rec: dict, src: Path) -> dict:
    events, n = [], 0
    for c in rec.get("calls", []):
        if c.get("after_compaction"):
            events.append({"kind": "compaction", "text": "after_compaction: the harness compacted the context before this call"})
        for m in c.get("new_messages") or []:
            events.append(msg_event(m))
        n += 1
        u = c.get("usage") or {}
        events.append(msg_event(c.get("reply") or {"role": "assistant"}, call=n, usage=u, finish=u.get("finish_reason"),
                                caller=f"{c.get('caller', '')} · {c.get('call_kind', '')}"))
    title = f"{src.name} · turn {rec.get('turn_number')} · {rec.get('model')}"
    return {"title": title, "events": events, "calls": n, "base": src.parent}


def sft_session(rec: dict, src: Path, idx: int) -> dict:
    events, n = [], 0
    for m in rec["messages"]:
        if m.get("role") == "assistant":
            n += 1
            events.append(msg_event(m, call=n))
        else:
            events.append(msg_event(m))
    tools = rec.get("tools")
    tools = json.loads(tools) if isinstance(tools, str) else tools
    meta = rec.get("meta") or {}
    return {"title": f"{src.name} row {idx} · {meta.get('fp', '')}", "events": events, "calls": n, "tools": tools, "base": src.parent}


def traj_session(rec: dict, src: Path, idx: int) -> dict:
    events, n, cur = [], 0, None
    for r in rec["rows"]:
        role, mode = r.get("role"), r.get("mode")
        if role == "assistant":
            if cur is None:
                n += 1
                cur = msg_event({"role": "assistant"}, call=n)
                events.append(cur)
            if mode == "think":
                cur["reasoning"] += r.get("content", "")
            elif mode == "reply":
                cur["parts"].append({"text": r.get("content", "")})
            elif mode == "tool_call":
                cur["calls"].append({"name": r.get("name"), "args": r.get("args") or {}, "id": r.get("id")})
            if r.get("weight") == 0:
                cur["weight"] = 0
            continue
        cur = None
        kind = {"system": "system", "tool_result": "tool"}.get(mode, "user")
        events.append({"kind": kind, "parts": text_parts(r.get("content")), "name": r.get("name")})
    return {"title": f"{src.name} trajectory {idx} · {rec['meta'].get('session', '')}", "events": events, "calls": n, "base": src.parent}


def load_sessions(path: Path) -> list[dict]:
    sessions = []
    for f in input_files(path):
        recs = list(records(f))
        if not recs:
            continue
        kind = kind_of(recs[0])
        if kind == "proxy":
            for s in proxy_sessions(recs):
                s["base"] = f.parent
                sessions.append(s)
        elif kind == "jaccoder":
            sessions += [jaccoder_session(r, f) for r in recs]
        elif kind == "sft":
            sessions += [sft_session(r, f, i) for i, r in enumerate(recs)]
        else:
            sessions += [traj_session(r, f, i) for i, r in enumerate(recs)]
    return sessions


def flag(sessions: list[dict]) -> None:
    """Mark repeated tool calls, error results, looping thinking and length stops; collect per-session stats.
    A flag is (anchor, reason); anchors are "c<call>" for assistant messages and "r<n>" for tool results."""
    for si, s in enumerate(sessions):
        recent = []                       # (sig, loose) of the last REPEAT_WIN calls, newest last
        flags, tools, finishes = [], Counter(), Counter()
        pt = ct = nres = 0
        for e in s["events"]:
            if e["kind"] == "assistant" and "call" in e:
                calls = e.get("calls", [])
                sig = json.dumps([(c["name"], c["args"]) for c in calls], sort_keys=True, default=str)
                loose = re.sub(r"\d+", "#", sig)
                back = next((len(recent) - i for i, (sg, _) in enumerate(recent) if sg == sig), 0) if calls else 0
                back_loose = next((len(recent) - i for i, (_, lo) in enumerate(recent) if lo == loose), 0) if calls else 0
                ago = lambda n: "the previous one" if n == 1 else f"the one {n} calls back"
                if back:
                    e["repeat"] = "repeat"
                    flags.append((f"c{e['call']}", f"#{e['call']} same tool call as {ago(back)}"))
                elif back_loose:
                    e["repeat"] = "near-repeat"
                    flags.append((f"c{e['call']}", f"#{e['call']} same tool call as {ago(back_loose)} except numbers"))
                recent = (recent + [(sig, loose) if calls else (None, None)])[-REPEAT_WIN:]
                tools.update(c["name"] for c in calls)
                finishes[e.get("finish") or "-"] += 1
                if e.get("finish") == "length":
                    flags.append((f"c{e['call']}", f"#{e['call']} finish_reason length"))
                lines = Counter(l.strip() for l in (e.get("reasoning") or "").splitlines() if len(l.strip()) > 20)
                if lines and lines.most_common(1)[0][1] >= 5:
                    e["loop_think"] = lines.most_common(1)[0][1]
                    flags.append((f"c{e['call']}", f"#{e['call']} thinking repeats one line {e['loop_think']}×"))
                u = e.get("usage") or {}
                pt = max(pt, u.get("prompt_tokens") or 0)
                ct += u.get("completion_tokens") or 0
            if e["kind"] == "tool":
                nres += 1
                e["anchor"] = f"r{nres}"
                t = "".join(p.get("text", "") for p in e["parts"])
                if ERROR_RE.match(t):
                    e["error_result"] = True
                    flags.append((e["anchor"], "tool result: " + re.sub(r"\s+", " ", t.strip())[:90]))
        s.update(flags=flags, tool_count=tools, finishes=finishes, max_prompt=pt, total_completion=ct, idx=si)


# --- HTML ---
CSS = """
:root{--bg:#fbfbf9;--fg:#1b1b1a;--mut:#73716b;--card:#fff;--bd:#e3e1da;--usr:#eef4fd;--tool:#f5f4ef;--asst:#fff;
--think:#f7f3ff;--warn:#fff4e0;--bad:#fde8e8;--badfg:#b42318;--acc:#2a64c4;--code:#f3f2ee}
@media (prefers-color-scheme:dark){:root{--bg:#141414;--fg:#e8e6e1;--mut:#9a978f;--card:#1d1d1c;--bd:#33322f;--usr:#1b2638;
--tool:#1f1f1d;--asst:#1d1d1c;--think:#241f33;--warn:#3a2d14;--bad:#3d1818;--badfg:#ff8a80;--acc:#7aa7ff;--code:#262624}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif}
main{max-width:1000px;margin:0 auto;padding:16px}h1{font-size:20px}h2{font-size:17px;margin-top:40px;border-bottom:1px solid var(--bd)}
.card{border:1px solid var(--bd);border-radius:8px;margin:8px 0;padding:8px 12px;background:var(--card)}
.user{background:var(--usr)}.tool{background:var(--tool)}.system{background:var(--tool)}
.bad{background:var(--bad)!important;border-color:var(--badfg)}.warnc{background:var(--warn)!important}
.hdr{font-size:12px;color:var(--mut);display:flex;gap:10px;flex-wrap:wrap}.hdr b{color:var(--fg)}
.tag{font-size:11px;padding:1px 6px;border-radius:9px;border:1px solid var(--bd)}.tag.r{color:var(--badfg);border-color:var(--badfg)}
pre{white-space:pre-wrap;word-break:break-word;margin:6px 0;font:12.5px/1.45 ui-monospace,monospace;background:var(--code);padding:8px;border-radius:6px}
.think{background:var(--think)}details>summary{cursor:pointer;color:var(--mut);font-size:12px}
.call{border-left:3px solid var(--acc);padding-left:8px;margin:6px 0}.call .nm{font-weight:600;font-family:ui-monospace,monospace}
.cmp{text-align:center;color:var(--badfg);font-size:12px;margin:14px 0;border-top:2px dashed var(--badfg);padding-top:4px}
img{max-width:100%;border:1px solid var(--bd);border-radius:6px;margin:4px 0}
table{border-collapse:collapse;font-size:13px}td,th{border:1px solid var(--bd);padding:2px 8px;text-align:left}
a{color:var(--acc)}.toc li{margin:2px 0}
"""


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def clip(t: str, n: int) -> str:
    return t if len(t) <= n else t[:n] + f"\n… [{len(t) - n:,} more chars]"


def img_src(ref: str, base: Path | None, out_dir: Path, embed: bool) -> str:
    if ref.startswith("data:") or re.match(r"https?://", ref):
        return ref
    p = Path(ref)
    if not p.is_absolute() and base is not None:
        for d in [base, *base.parents]:            # prod traces say media/<hash>.png relative to the dataset root
            if (d / ref).exists():
                p = d / ref
                break
    if embed and p.exists():
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
    return os.path.relpath(p, out_dir) if p.is_absolute() else ref


def parts_html(parts, base, out_dir, embed, max_chars, open_chars) -> str:
    out = []
    for p in parts:
        if "image" in p:
            out.append(f'<img loading="lazy" src="{esc(img_src(p["image"], base, out_dir, embed))}">')
        elif p.get("text", "").strip():
            t = p["text"]
            pre = f"<pre>{esc(clip(t, max_chars))}</pre>"
            out.append(pre if len(t) <= open_chars else f"<details><summary>{len(t):,} chars</summary>{pre}</details>")
    return "".join(out)


def args_html(args: dict, max_chars: int) -> str:
    short = {k: v for k, v in args.items() if not (k in LONG_ARGS and isinstance(v, str) and len(v) > 120)}
    out = [f"<pre>{esc(clip(json.dumps(short, indent=1, ensure_ascii=False), max_chars))}</pre>"] if short else []
    for k, v in args.items():
        if k not in short:
            out.append(f"<details><summary>{esc(k)} · {len(v):,} chars</summary><pre>{esc(clip(v, max_chars))}</pre></details>")
    return "".join(out)


def event_html(e, sid, base, out_dir, embed, max_chars, open_chars) -> str:
    k = e["kind"]
    if k == "compaction":
        return f'<div class="cmp">⟲ {esc(e["text"])}</div>'
    if k == "system":
        body = parts_html(e["parts"], base, out_dir, embed, 10**9, 0)
        n = sum(len(p.get("text", "")) for p in e["parts"])
        return f'<div class="card system"><details><summary>system prompt · {n:,} chars</summary>{body}</details></div>'
    if k in ("user", "tool"):
        cls = "tool" + (" warnc" if e.get("error_result") else "") if k == "tool" else "user"
        label = f"tool result{' · ' + esc(e['name']) if e.get('name') else ''}" if k == "tool" else "user"
        aid = f' id="s{sid}{e["anchor"]}"' if e.get("anchor") else ""
        return (f'<div class="card {cls}"{aid}><div class="hdr"><b>{label}</b></div>'
                f'{parts_html(e["parts"], base, out_dir, embed, max_chars, open_chars)}</div>')
    # assistant
    u = e.get("usage") or {}
    bits = [f'<b id="s{sid}c{e.get("call")}">assistant #{e.get("call", "")}</b>']
    for lab, val in (("", e.get("caller")), ("", e.get("ts")), ("", f'{e["latency"]:.1f}s' if e.get("latency") is not None else None),
                     ("prompt ", u.get("prompt_tokens")), ("out ", u.get("completion_tokens")), ("finish ", e.get("finish"))):
        if val not in (None, ""):
            bits.append(f"<span>{lab}{esc(val)}</span>")
    if "weight" in e:
        bits.append(f'<span class="tag{" r" if not e["weight"] else ""}">{"trained" if e["weight"] else "weight 0"}</span>')
    if e.get("repeat"):
        bits.append(f'<span class="tag r">{e["repeat"]}</span>')
    if e.get("loop_think"):
        bits.append(f'<span class="tag r">thinking loop ×{e["loop_think"]}</span>')
    bad = e.get("repeat") or e.get("loop_think") or e.get("finish") == "length" or e.get("error") or (e.get("status") not in (None, 200))
    body = []
    r = e.get("reasoning") or ""
    if r:
        pre = f'<pre class="think">{esc(clip(r, max_chars))}</pre>'
        body.append(f'<details{" open" if len(r) <= open_chars else ""}><summary>thinking · {len(r):,} chars</summary>{pre}</details>')
    body.append(parts_html(e["parts"], base, out_dir, embed, max_chars, 10**9))
    for c in e.get("calls", []):
        body.append(f'<div class="call"><span class="nm">{esc(c["name"])}</span>{args_html(c["args"], max_chars)}</div>')
    if e.get("error"):
        body.append(f"<pre>{esc(json.dumps(e['error'], ensure_ascii=False)[:2000])}</pre>")
    return f'<div class="card{" bad" if bad else ""}"><div class="hdr">{"".join(bits)}</div>{"".join(body)}</div>'


def session_html(i, s, out_dir, embed, max_chars, open_chars) -> str:
    rows = [f"<tr><th>calls</th><td>{s['calls']}</td></tr>",
            f"<tr><th>max prompt tokens</th><td>{s['max_prompt']:,}</td></tr>",
            f"<tr><th>completion tokens</th><td>{s['total_completion']:,}</td></tr>",
            f"<tr><th>finish</th><td>{esc(', '.join(f'{k} {v}' for k, v in s['finishes'].most_common()))}</td></tr>",
            f"<tr><th>tools</th><td>{esc(', '.join(f'{k} {v}' for k, v in s['tool_count'].most_common()))}</td></tr>"]
    flags = "".join(f'<li><a href="#s{i}{a}">{esc(why)}</a></li>' for a, why in s["flags"])
    tools = s.get("tools") or []
    names = [t.get("function", t).get("name", "?") for t in tools if isinstance(t, dict)]
    tool_html = (f"<details><summary>{len(names)} tool schemas: {esc(', '.join(names))}</summary>"
                 f"<pre>{esc(json.dumps(tools, indent=1, ensure_ascii=False))}</pre></details>") if names else ""
    events = "".join(event_html(e, i, s.get("base"), out_dir, embed, max_chars, open_chars) for e in s["events"])
    return (f'<h2 id="s{i}">{i + 1}. {esc(s["title"])}</h2><table>{"".join(rows)}</table>'
            f'{"<details open><summary>flags (" + str(len(s["flags"])) + ")</summary><ul>" + flags + "</ul></details>" if flags else ""}'
            f"{tool_html}{events}")


def render_html(src: Path, sessions, out: Path, embed, max_chars, open_chars) -> str:
    toc = "".join(f'<li><a href="#s{i}">{esc(s["title"])}</a> · {s["calls"]} calls'
                  f'{" · <b>" + str(len(s["flags"])) + " flags</b>" if s["flags"] else ""}</li>' for i, s in enumerate(sessions))
    body = "".join(session_html(i, s, out.parent, embed, max_chars, open_chars) for i, s in enumerate(sessions))
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>Agent log viewer</title><style>{CSS}</style></head><body><main><h1>{esc(src)}</h1>"
            f'<ol class="toc">{toc}</ol>{body}</main></body></html>')


# --- Markdown ---
def fence(t: str) -> str:
    ticks = "````" if "```" in t else "```"
    return f"{ticks}\n{t}\n{ticks}"


def render_md(src: Path, sessions, max_chars: int) -> str:
    out = [f"# {src}", ""]
    for i, s in enumerate(sessions):
        out += [f"## {i + 1}. {s['title']}", "",
                f"calls {s['calls']} · max prompt {s['max_prompt']:,} · completion {s['total_completion']:,} · "
                f"finish {dict(s['finishes'])}", ""]
        out += [f"- flag: {why}" for _, why in s["flags"]] + [""]
        for e in s["events"]:
            k = e["kind"]
            if k == "compaction":
                out += [f"> ⟲ {e['text']}", ""]
                continue
            text = "\n".join(p.get("text") or f"[image {p['image'][:80]}]" for p in e.get("parts", []))
            if k == "system":
                out += [f"**system** ({len(text):,} chars, omitted)", ""]
            elif k in ("user", "tool"):
                out += [f"**{'tool result' if k == 'tool' else 'user'}**{' ⚠' if e.get('error_result') else ''}", "", fence(clip(text, max_chars)), ""]
            else:
                u = e.get("usage") or {}
                head = f"### assistant #{e.get('call', '')}" + (f" ⚠ {e['repeat']}" if e.get("repeat") else "")
                head += f" ⚠ thinking loop ×{e['loop_think']}" if e.get("loop_think") else ""
                head += f" · out {u.get('completion_tokens')} · finish {e.get('finish')}" if u else ""
                out += [head, ""]
                if e.get("reasoning"):
                    out += ["<details><summary>thinking</summary>", "", fence(clip(e["reasoning"], max_chars)), "", "</details>", ""]
                if text.strip():
                    out += [clip(text, max_chars), ""]
                for c in e.get("calls", []):
                    out += [f"→ `{c['name']}`", "", fence(clip(json.dumps(c["args"], indent=1, ensure_ascii=False), max_chars)), ""]
    return "\n".join(out)


def build(in_path: str, out: str | None = None, fmt: str = "html", match: str | None = None,
          embed: bool = False, max_chars: int = MAX_CHARS, open_chars: int = OPEN_CHARS, client: str | None = None) -> Path:
    src = Path(in_path).resolve()
    sessions = load_sessions(src)
    if client:
        sessions = [s for s in sessions if s.get("client") == client]
    if match:
        sessions = [s for s in sessions if match.lower() in s["title"].lower()]
    flag(sessions)
    stem = src.name.removesuffix(".gz").removesuffix(".jsonl").removesuffix(".json")
    out_path = Path(out) if out else (src.parent if src.is_file() else src) / f"{stem}.view.{fmt}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = render_md(src, sessions, max_chars) if fmt == "md" else render_html(src, sessions, out_path.resolve(), embed, max_chars, open_chars)
    out_path.write_text(text, encoding="utf-8")
    print(f"{len(sessions)} sessions, {sum(s['calls'] for s in sessions)} calls, "
          f"{sum(len(s['flags']) for s in sessions)} flags -> {out_path}")
    return out_path


# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("in_path", help="a log file (.json/.jsonl, optionally .gz) or a folder of them")
    cli.add_argument("--out", help="output file (default: <input>.view.<format> next to the input)")
    cli.add_argument("--format", choices=["html", "md"], default="html")
    cli.add_argument("--match", help="keep only sessions whose title contains this text")
    cli.add_argument("--client", choices=["jaccoder", "opencode", "pi", "other"], help="proxy logs: keep one agent's sessions")
    cli.add_argument("--embed", action="store_true", help="inline image files as data URLs (self-contained HTML)")
    cli.add_argument("--max-chars", type=int, default=MAX_CHARS, help="clip any text block to this many characters")
    cli.add_argument("--open-chars", type=int, default=OPEN_CHARS, help="expand thinking / tool results up to this length")
    a = cli.parse_args()
    build(a.in_path, a.out, a.format, a.match, a.embed, a.max_chars, a.open_chars, a.client)
