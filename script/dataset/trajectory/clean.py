"""Clean JacHammer prod traces into per-turn SFT samples (rules: dataset/raw/prod/sft/prod-64k/RULES.md; habits behind them: dataset/raw/prod/badhabit.md); --stats prints what each rule does."""

import argparse, gzip, hashlib, json, glob, re, sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

# Setting =================================================
IN_DIR    = "dataset/raw/prod"
TOKENIZER = "ornith-ai/Ornith-1.5-9B"
PROCESSOR = "output/model/JacLLM-SFT-Ornith-9B-v1.35-vlm"     # image processor: exact image token counts
TOOLS     = "dataset/raw/prod/tools_f14d1f1.json"              # byLLM schemas of the harness at the log date
OUT_DIR   = "dataset/raw/prod/sft/prod-64k"                    # under raw/: real user data, never committed
CAP       = 65536                                              # tokens per written sample, chat template and tools included
VALID_SESSIONS = 0.05                                          # split by session: turns of one session share history
SEED      = 3407
WINDOWS   = [None, 131072, 65536]          # sample length caps to report (None = full turn)
BUDGET    = 100                            # main-agent calls per turn in the prod harness
FLAIL_AT  = 3                              # same error class seen this many times with a fix attempt in between = flailing
                                           # (system prompt: stop once an error class survives 2 fix rounds)
READ_TOOLS = {"read_file", "list_files", "grep_search", "find_files", "preview_status", "load_jac_skill",
              "browser_state", "analyze_project"}
EDIT_TOOLS = {"write_code", "edit_code", "delete_code"}
RO_CMD      = re.compile(r"^\s*(jac check|cat |ls|grep|rg |tail|head|find |sed -n|wc |pwd|echo [^>]*$)")
SHELL_WRITE = re.compile(r"(>\s*[\w./-]+\.(jac|toml|json|css)\b|\b(cp|mv)\s[^|;]*\.(jac|toml)|sed -i|rm -rf|\btee\b)")
CACHE_RM    = re.compile(r"rm -rf\s+\S*(\.jac/|node_modules|compiled|cache|dist|/tmp)")
CLAIM       = re.compile(r"\b(verified|tested|confirmed|validated|end[- ]to[- ]end)\b", re.I)    # explicit verification claims only
LINE_NO     = re.compile(r"^\s*\d+: ?", re.M)
ERR_LINE    = re.compile(r"(✖ Error: .*|error\[E\d+\]: .*|error during build.*|Build gate failed.*)")
INLINE_ERR  = re.compile(r"^(SYNTAX|TYPE) ERRORS:\s*\n(.*)", re.M)
# M7: calls the harness system prompt forbids in so many words (quotes in RULES.md)
UI_FILE     = re.compile(r"(\.cl\.jac$|(^|/)(components|pages|styles)/|(^|/)main\.jac$|\.css$)")   # a "rendering edit"
APP_PATH    = re.compile(r"^/(walker|function|user|api|healthz|docs|openapi|sso|__)")    # API/status endpoints, not the page
PAGE_CURL   = re.compile(r"\bcurl\b.*?https?://(?:localhost|127\.0\.0\.1)(?::\d+)?(/[^\s'\"]*)?")
STATUS_ONLY = re.compile(r"-o\s*/dev/null|--head\b|\s-I\b|-sI\b")                       # health check, not reading the page
BROWSER_FAIL = re.compile(r"✗|\berror\b|failed|not found|timed? ?out|could not|no element|unable", re.I)
LLM_DIRECT  = re.compile(r"https?://api\.(openai|anthropic)\.com|import\s+(from\s+)?(openai|anthropic)\b")


# Functions ===============================================
def text(c) -> str:
    if isinstance(c, str):
        return c
    return "\n".join(p.get("text", "") for p in c or [] if isinstance(p, dict))


def images(c) -> list[str]:
    return [p["image_url"]["url"] for p in c if isinstance(p, dict) and p.get("type") == "image_url"] if isinstance(c, list) else []


def arg_text(tcs) -> str:
    """Decoded string values of tool-call arguments (the raw JSON has escaped newlines and quotes)."""
    out = []
    for tc in tcs or []:
        a = args(tc)
        out.append(tc["function"]["name"] + "\n" + "\n".join(v for v in a.values() if isinstance(v, str)))
    return "\n".join(out)


def args(tc) -> dict:
    try:
        a = json.loads(tc["function"]["arguments"])
        return a if isinstance(a, dict) else {}
    except Exception:
        return {}


def norm(s: str) -> str:
    """Error class: file + message, without line/col, quoted names and numbers. The file stays so that one fixed
    error per file in a long build is not mistaken for one error surviving many fixes."""
    s = re.sub(r",? line \d+, col \d+:", ":", s)
    s = re.sub(r"'[^']*'|\"[^\"]*\"|`[^`]*`", "Q", s)
    return re.sub(r"\d+", "N", s).strip()[:90]


def error_classes(name: str, a: dict, r: str) -> set[str]:
    out = set()
    if name in ("write_code", "edit_code"):
        for _, first in INLINE_ERR.findall(r):
            out.add(norm(first))
    elif name == "run_command":
        m = ERR_LINE.search(r)
        if m:
            out.add(norm(m.group(1)))
    elif name == "preview_status" and r.startswith("Preview: FAILED"):
        out.add("preview FAILED")
    elif name == "browser_validate" and ("no content rendered" in r or "PREVIEW_NOT_READY" in r):
        out.add("app does not render")
    return out


class Tok:
    """Token length of message text (cached), plus image tokens at one per 32x32 px."""
    def __init__(self, name: str | None, root: str):
        from transformers import AutoTokenizer
        self.tok, self.root, self.cache, self.dims = AutoTokenizer.from_pretrained(name), root, {}, {}

    def __call__(self, s: str) -> int:
        h = hashlib.sha1(s.encode()).digest()
        if h not in self.cache:
            self.cache[h] = len(self.tok(s, add_special_tokens=False)["input_ids"]) if s else 0
        return self.cache[h]

    def image(self, url: str) -> int:
        if url not in self.dims:
            with Image.open(f"{self.root}/{url}") as im:
                w, h = im.size
            self.dims[url] = max(1, round(w / 32)) * max(1, round(h / 32))
        return self.dims[url]


def build(d: dict) -> tuple[list[dict], dict]:
    """The main agent's turn -> ordered message list (see build_calls)."""
    resp = [c for c in d["calls"] if c["caller"] == "respond"]
    return build_calls([c for c in resp if c["call_kind"] == "react_iteration"],
                       resp[-1] if resp and resp[-1]["call_kind"] == "final_answer_restream" else None)


def planner_chains(d: dict) -> list[tuple[list[dict], dict | None]]:
    """(react calls, restream call) per planner chain. A chain starts at a do_work call that carries a system prompt:
    parent_invocation_id names the main agent's whole run, so it cannot tell two chains in one turn apart."""
    chains = []
    for c in d["calls"]:
        if c["caller"] == "do_work":
            if not chains or any(m.get("role") == "system" for m in c["new_messages"]):
                chains.append([])
            chains[-1].append(c)
    return [([c for c in ch if c["call_kind"] == "react_iteration"],
             ch[-1] if ch[-1]["call_kind"] == "final_answer_restream" else None) for ch in chains]


def build_calls(main: list[dict], restream: dict | None) -> tuple[list[dict], dict]:
    """One agent run -> ordered message list. Each msg: role, origin (history|user|own), text, images, calls,
    result_of, raw (the logged message, for writing)."""
    msgs = []
    first = main[0]["new_messages"] if main else []
    hist_end = max((i for i, m in enumerate(first) if m.get("role") == "user"), default=-1)
    for k, c in enumerate(main):
        for i, m in enumerate(c["new_messages"]):
            origin = ("history" if i < hist_end else "user") if k == 0 else "own"
            msgs.append({"role": m.get("role"), "origin": origin if m.get("role") != "tool" or k else "history",
                         "text": text(m.get("content")) + arg_text(m.get("tool_calls")),
                         "reason": m.get("reasoning_content") or "", "images": images(m.get("content")),
                         "calls": [], "result_of": m.get("tool_call_id"), "weight": 0 if k == 0 else None, "raw": m})
        rep = c["reply"]
        msgs.append({"role": "assistant", "origin": "own", "text": rep.get("content") or "", "reason": rep.get("reasoning_content") or "",
                     "images": [], "calls": [(tc["id"], tc["function"]["name"], args(tc)) for tc in rep.get("tool_calls") or []],
                     "result_of": None, "weight": 1, "rules": set(), "raw": rep})
    if restream:
        rep = restream["reply"]
        msgs.append({"role": "assistant", "origin": "own", "text": rep.get("content") or "", "reason": rep.get("reasoning_content") or "",
                     "images": [], "calls": [], "result_of": None, "weight": 1, "rules": set(), "final": True, "raw": rep,
                     "restream": True})
    own = [m for m in msgs if m["role"] == "assistant" and m["origin"] == "own"]
    if own:
        own[-1]["final"] = True
    info = {"main_calls": len(main),
            "mid_work": bool(own) and bool(own[-1]["calls"]) and not any(n == "finish_tool" for _, n, _ in own[-1]["calls"])}
    return msgs, info


def apply_rules(msgs: list[dict], info: dict, R: Counter) -> str:
    """Mark deletions (call ids) and masks (weight 0 + rule tags) in place. Returns the turn's fate."""
    if info["mid_work"]:
        return "T1 drop: ends mid-work"
    res = {m["result_of"]: m for m in msgs if m["role"] == "tool"}
    own = [m for m in msgs if m["role"] == "assistant" and m["origin"] == "own"]
    seq = [(m, cid, n, a) for m in own for cid, n, a in m["calls"]]
    rtext = lambda cid: res[cid]["text"] if cid in res else ""
    # D1 / D2: delete calls that cannot carry new information
    seen, last_status = {}, None
    ui_edited, last_do = False, None             # M7: UI edit not yet validated; (args, result) of the last browser_do
    for i, (m, cid, n, a) in enumerate(seq):
        key = (n, json.dumps(a, sort_keys=True))
        cmd = a.get("command", "") if n == "run_command" else ""
        ro = n in READ_TOOLS or (n == "run_command" and RO_CMD.match(cmd) and not SHELL_WRITE.search(cmd))
        if ro and key in seen:
            m.setdefault("delete", set()).add(cid); R["D1 redundant read-only repeat (calls)"] += 1
        elif n == "read_file" and i and seq[i - 1][2] == "write_code" and seq[i - 1][3].get("file_path") == a.get("file_path") \
                and rtext(seq[i - 1][1]).startswith("OK") and "ERRORS:" not in rtext(seq[i - 1][1]):
            m.setdefault("delete", set()).add(cid); R["D2 re-read right after a clean write_code (calls)"] += 1
        if ro:
            seen[key] = i
        else:
            seen = {}
        # M1 / M2 / M3: mask the reply that made the call
        r = rtext(cid)
        if n == "edit_code" and r and not r.startswith("OK"):
            m["rules"].add("M1 rejected edit")
        if n in ("write_code", "edit_code") and r.startswith("OK") and "ERRORS:" in r:
            m["rules"].add("M2 write/edit with Jac errors")
        if n == "preview_status":
            last_status = r
        if n == "preview_restart" and last_status and "Serving normally" in last_status:
            m["rules"].add("M3 restart of a healthy preview")
        if n == "run_command" and re.search(r"\bsleep\s+\d", cmd):
            m["rules"].add("M3 sleep")
        if n == "run_command" and SHELL_WRITE.search(cmd):
            m["rules"].add("M3 rm -rf cache" if CACHE_RM.search(cmd) and not re.search(r"(>\s*[\w./-]+\.(jac|toml)|sed -i|\b(cp|mv)\s)", cmd)
                           else "M3 shell write to project files")
        # M7: harness prohibitions
        if "node_modules/@jac" in json.dumps(a):
            m["rules"].add("M7 @jac/* looked up in node_modules")
        if any((u := PAGE_CURL.search(seg)) and not APP_PATH.match(u.group(1) or "/") and not STATUS_ONLY.search(seg)
               for seg in re.split(r"[;&|]{1,2}", cmd)):
            m["rules"].add("M7 curl of the app page")
        if n in ("write_code", "edit_code") and LLM_DIRECT.search(str(a.get("content", "")) + str(a.get("new_string", ""))):
            m["rules"].add("M7 LLM provider called directly")
        if n in ("browser_do", "browser_state") and ui_edited:
            m["rules"].add("M7 browser_do/state before browser_validate after a UI edit")
        if n in ("browser_validate", "browser_open", "browser_do", "browser_state"):
            ui_edited = False
        if n in EDIT_TOOLS and UI_FILE.search(str(a.get("file_path", ""))):
            ui_edited = True
        if n in EDIT_TOOLS or n in ("preview_restart", "run_command"):
            last_do = None                       # the app may have changed: a retry is no longer the same action
        if n == "browser_do":
            sig = json.dumps(a, sort_keys=True)
            if last_do and last_do[0] == sig and BROWSER_FAIL.search(last_do[1][:600]):
                m["rules"].add("M7 failing browser action retried")
            last_do = (sig, r)
    # M4: same error class seen FLAIL_AT times with a state change in between -> mask until its last occurrence
    occ, changed_since = defaultdict(list), defaultdict(bool)
    for i, (m, cid, n, a) in enumerate(seq):
        if n in EDIT_TOOLS or n in ("preview_restart", "run_command"):
            for s in occ:
                changed_since[s] = True
        for s in error_classes(n, a, rtext(cid)):
            if not occ[s] or changed_since[s]:
                occ[s].append(i)
                changed_since[s] = False
    flail_start = None
    for s, idx in occ.items():
        if len(idx) >= FLAIL_AT:
            R[f"M4 class: {s}"] += 1
            lo, hi = idx[FLAIL_AT - 1] + 1, idx[-1]
            flail_start = lo if flail_start is None else min(flail_start, lo)
            for j in range(lo, hi + 1):
                seq[j][0]["rules"].add("M4 flailing on a repeated error")
    # T2: budget exhausted -> cut where flailing began
    fate = "keep"
    if info["main_calls"] >= BUDGET and flail_start is not None:
        cut = seq[flail_start][0]
        k = msgs.index(cut)
        del msgs[k:]
        fate = "T2 truncated: budget exhausted, cut at flailing start"
    own = [m for m in msgs if m["role"] == "assistant" and m["origin"] == "own"]
    if not own:
        return "T2 dropped: nothing left before flailing"
    final = own[-1]
    edits = [i for i, (m, cid, n, a) in enumerate(seq) if n in EDIT_TOOLS and m in own]
    after = seq[edits[-1] + 1:] if edits else []
    vals = [rtext(cid) for m, cid, n, a in after if n == "browser_validate" and m in own]
    # T3 / M5 on the final answer
    # with a restream, the finish_tool reply before it carries the same answer text
    finals = [final] + [m for m in own if any(n == "finish_tool" for _, n, _ in m["calls"])]
    answer = final["text"] + "".join(json.dumps(a) for m in finals for _, n, a in m["calls"] if n == "finish_tool")
    rule = ("T3 final answer on a broken app" if vals and "Status: rendered" not in vals[-1] else
            "M5 unverified claim in final answer" if edits and not vals and CLAIM.search(answer) else None)
    if rule:
        for m in finals:
            m["rules"].add(rule)
    return fate


def visible_before(msgs: list[dict], k: int, lo: int) -> str:
    out = []
    for m in msgs[lo:k]:
        t = LINE_NO.sub("", m["text"]) if m["role"] == "tool" else m["text"]
        for _, _, a in m["calls"]:
            t += "\n" + "\n".join(v for v in a.values() if isinstance(v, str))
        out.append(t)
    return "\n".join(out)


def grounding(msgs: list[dict], lo: int, roots: set[str]) -> list[int]:
    """Indices of own replies whose file path / old_string is not visible in msgs[lo:k] (G rule)."""
    bad = []
    for k, m in enumerate(msgs):
        if k < lo or m["role"] != "assistant" or m["origin"] != "own":
            continue
        need = []
        for _, n, a in m["calls"]:
            p = a.get("file_path")
            if n in ("read_file", "edit_code", "delete_code") and isinstance(p, str):
                for r in roots:
                    p = p[len(r):].lstrip("/") if p.startswith(r) else p
                if p not in ("main.jac", "jac.toml"):
                    need.append(p)
            if n == "edit_code" and isinstance(a.get("old_string"), str) and a["old_string"]:
                need.append(a["old_string"])
        if need:
            vis = visible_before(msgs, k, lo)
            if any(s not in vis for s in need):
                bad.append(k)
    return bad


def pct(xs: list, p: float):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, round(p / 100 * len(xs) + 0.5) - 1))] if xs else 0


def stats(in_dir: str, tok_name: str) -> None:
    tok = Tok(tok_name, in_dir)
    R, fates = Counter(), Counter()
    W = {w: Counter() for w in WINDOWS}
    lens = defaultdict(list)
    files = sorted(glob.glob(f"{in_dir}/**/*.json.gz", recursive=True))
    for f in files:
        d = json.load(gzip.open(f))
        msgs, info = build(d)
        roots = set(re.findall(r"Working directory: (\S+)", " ".join(m["text"] for m in msgs if m["role"] == "user")))
        before = sum(tok(m["text"]) + tok(m["reason"]) for m in msgs if m["role"] == "assistant" and m["origin"] == "own")
        R["trainable tokens before cleaning"] += before
        fate = apply_rules(msgs, info, R)
        fates[fate.split(":")[0]] += 1
        if fate.startswith(("T1", "T2 dropped")):
            continue
        # apply deletions
        dele = set().union(*(m.get("delete", set()) for m in msgs))
        for m in msgs:
            m["calls"] = [c for c in m["calls"] if c[0] not in dele]
        msgs = [m for m in msgs if not (m["role"] == "tool" and m["result_of"] in dele)
                and not (m["role"] == "assistant" and m["origin"] == "own" and not m["calls"] and not m["text"] and m.get("delete"))]
        for m in msgs:
            m["tokens"] = tok(m["text"]) + tok(m["reason"]) + sum(tok.image(u) for u in m["images"])
        total = sum(m["tokens"] for m in msgs)
        for w in WINDOWS:
            S = W[w]
            lo, cut = 0, 0
            if w and total > w:
                S["samples truncated"] += 1
                lo, run = 1, total                # keep msgs[0] (system prompt), drop oldest after it
                while run > w and lo < len(msgs):
                    run -= msgs[lo]["tokens"]
                    lo += 1
                if any(m["origin"] == "user" for m in msgs[1:lo]):
                    S["samples whose own turn alone exceeds the cap (user message cut)"] += 1
            S["samples"] += 1
            kept = msgs[:1] + msgs[lo:] if lo else msgs
            lens[w].append(sum(m["tokens"] for m in kept))
            g = set(grounding(msgs, max(lo, 1) if lo else 0, roots))
            for k, m in enumerate(msgs):
                if m["role"] != "assistant" or m["origin"] != "own" or (lo and k < lo):
                    continue
                rules = set(m["rules"]) | ({"G path/old_string not visible in the sample"} if k in g else set())
                t = m["tokens"]
                S["own replies"] += 1
                if rules:
                    for r in rules:
                        S[f"masked by {r} (replies)"] += 1
                        S[f"masked by {r} (tokens)"] += t
                    S["masked tokens (any rule)"] += t
                else:
                    S["trainable tokens"] += t
                    S["trainable replies"] += 1
            S["context tokens (sum over samples)"] += sum(m["tokens"] for m in kept)
    n = len(files)
    print(f"turns {n}: " + ", ".join(f"{k} {v}" for k, v in fates.most_common()))
    print(f"trainable tokens before cleaning (own assistant text+reasoning+args): {R['trainable tokens before cleaning']:,}")
    for k in ("D1 redundant read-only repeat (calls)", "D2 re-read right after a clean write_code (calls)"):
        print(f"  deleted: {k} {R[k]}")
    for w in WINDOWS:
        S = W[w]
        print(f"\n== cap {'none (full turn)' if w is None else f'{w // 1024}k'} ==")
        print(f"  samples {S['samples']}, truncated {S['samples truncated']}, "
              f"own turn alone over cap {S['samples whose own turn alone exceeds the cap (user message cut)']}")
        print(f"  sample length (tokens): p50 {pct(lens[w], 50):,} p90 {pct(lens[w], 90):,} max {max(lens[w]):,}; "
              f"context sum {S['context tokens (sum over samples)']:,}")
        print(f"  own replies {S['own replies']}, trainable {S['trainable replies']} "
              f"({100 * S['trainable replies'] / max(1, S['own replies']):.0f}%), trainable tokens {S['trainable tokens']:,}, "
              f"masked tokens {S['masked tokens (any rule)']:,}")
        for k in sorted(k for k in S if k.startswith("masked by") and k.endswith("(replies)")):
            r = k[len("masked by "):-len(" (replies)")]
            print(f"    {r:45s} replies {S[k]:5d}  tokens {S[f'masked by {r} (tokens)']:>9,}")
    print("\nM4 error classes that triggered flailing (turns):")
    for k, v in sorted(((k, v) for k, v in R.items() if k.startswith("M4 class")), key=lambda kv: -kv[1])[:15]:
        print(f"  {v:3d}  {k[len('M4 class: '):]}")


def apply_deletions(msgs: list[dict]) -> list[dict]:
    dele = set().union(*(m.get("delete", set()) for m in msgs))
    for m in msgs:
        m["calls"] = [c for c in m["calls"] if c[0] not in dele]
    return [m for m in msgs if not (m["role"] == "tool" and m["result_of"] in dele)
            and not (m["role"] == "assistant" and m["origin"] == "own" and not m["calls"] and not m["text"] and m.get("delete"))]


def unify_final(msgs: list[dict]) -> list[dict]:
    """The final answer becomes one plain-text assistant message: a restream replaces the finish_tool call before it;
    without a restream, finish_tool's final_output becomes the reply text."""
    fin = {cid: a for m in msgs if m["origin"] == "own" for cid, n, a in m["calls"] if n == "finish_tool"}
    if not fin:
        return msgs
    restream = any(m.get("restream") for m in msgs)
    for m in msgs:
        if m["origin"] != "own" or m["role"] != "assistant":
            continue
        for cid, n, a in [c for c in m["calls"] if c[1] == "finish_tool"]:
            if not restream:
                out = a.get("final_output")
                m["text"] = (m["text"] + "\n\n" if m["text"] else "") + (out if isinstance(out, str) else json.dumps(out))
                m["final"] = True
        m["calls"] = [c for c in m["calls"] if c[1] != "finish_tool"]
    return [m for m in msgs if not (m["role"] == "tool" and m["result_of"] in fin)
            and not (m["role"] == "assistant" and m["origin"] == "own" and not m["calls"] and not m["text"].strip())]


def invalid_args(msgs: list[dict], schema: list[dict]) -> None:
    """M6: a call naming an argument the tool does not have (or no such tool) is a model error; mask that reply."""
    props = {t["function"]["name"]: t["function"]["parameters"]["properties"] for t in schema}
    for m in msgs:
        if m["origin"] == "own" and m["role"] == "assistant":
            if any(n not in props or any(k not in props[n] for k in a) for _, n, a in m["calls"]):
                m["rules"].add("M6 invalid tool arguments")


def parts(c, in_dir: str):
    """Logged content -> training content: text stays text, image_url parts become {"type": "image", "image": path}."""
    if not isinstance(c, list):
        return c if isinstance(c, str) else ""
    out = []
    for p in c:
        if isinstance(p, dict) and p.get("type") == "image_url":
            out.append({"type": "image", "image": f"{in_dir}/{p['image_url']['url']}"})
        elif isinstance(p, dict) and p.get("type") == "text":
            out.append({"type": "text", "text": p.get("text", "")})
    return out


def to_train(m: dict, in_dir: str) -> dict:
    raw = m["raw"]
    if m["role"] == "tool":
        return {"role": "tool", "tool_call_id": m["result_of"], "content": parts(raw.get("content"), in_dir)}
    if m["role"] != "assistant":
        return {"role": m["role"], "content": parts(raw.get("content"), in_dir)}
    if m["origin"] == "own":
        by_id = {tc["id"]: tc for tc in raw.get("tool_calls") or []}
        calls = [{"id": cid, "type": "function", "function": {"name": n, "arguments": by_id[cid]["function"]["arguments"]}}
                 for cid, n, _ in m["calls"]]
        text = m["text"]
    else:
        calls = [{"id": tc["id"], "type": "function", "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}}
                 for tc in raw.get("tool_calls") or []]
        text = raw.get("content") or ""
    out = {"role": "assistant", "content": text if isinstance(text, str) else parts(text, in_dir)}
    if m["reason"]:
        out["reasoning_content"] = m["reason"]
    if calls:
        out["tool_calls"] = calls
    return out


class Length:
    """Exact sample length: the chat template rendered with tools, plus each image's expanded token count."""
    def __init__(self, tok, processor_dir: str):
        from transformers import AutoImageProcessor
        self.tok, self.ip, self.img = tok, AutoImageProcessor.from_pretrained(processor_dir), {}

    def image(self, path: str) -> int:
        if path not in self.img:
            with Image.open(path) as im:
                g = self.ip(images=[im.convert("RGB")], return_tensors="np")["image_grid_thw"][0]
            self.img[path] = int(g[0] * g[1] * g[2]) // (self.ip.merge_size ** 2)
        return self.img[path]

    def __call__(self, conv: list[dict], tools: list[dict]) -> int:
        msgs = []
        for m in conv:
            m = dict(m)
            if "tool_calls" in m:
                m["tool_calls"] = [{**c, "function": {**c["function"], "arguments": json.loads(c["function"]["arguments"])}}
                                   for c in m["tool_calls"]]
            msgs.append(m)
        text = self.tok.apply_chat_template(msgs, tools=tools, tokenize=False)
        imgs = [p["image"] for m in conv if isinstance(m.get("content"), list) for p in m["content"] if p.get("type") == "image"]
        return len(self.tok(text, add_special_tokens=False)["input_ids"]) + sum(self.image(p) - 1 for p in imgs)


def make_sample(msgs: list[dict], info: dict, tools: list[dict], in_dir: str, tok: Tok, length: Length,
                cap: int, R: Counter, log: dict) -> dict | None:
    """Apply every rule to one agent run and return a training record, or None (with the reason counted in R).
    `log` receives the run's fate and its length before truncation."""
    fate = apply_rules(msgs, info, R)
    R[f"fate: {fate.split(':')[0]}"] += 1
    log["fate"] = fate.split(":")[0]
    if fate.startswith(("T1", "T2 dropped")):
        return None
    msgs = unify_final(apply_deletions(msgs))
    invalid_args(msgs, tools)
    roots = set(re.findall(r"Working directory: (\S+)", " ".join(m["text"] for m in msgs if m["role"] == "user")))
    for m in msgs:
        m["tokens"] = tok(m["text"]) + tok(m["reason"]) + sum(tok.image(u) for u in m["images"])
    conv = [to_train(m, in_dir) for m in msgs]
    # truncate: keep the system prompt, drop the oldest messages after it (estimate first, then exact)
    lo, est, budget = 1, sum(m["tokens"] for m in msgs), cap - 8192
    log["est_tokens"] = est
    while est > budget and lo < len(msgs):
        est -= msgs[lo]["tokens"]
        lo += 1
    while True:
        while 1 < lo < len(msgs) and msgs[lo]["role"] == "tool":     # never start on a result whose call was cut
            lo += 1
        kept = conv[:1] + conv[lo:] if lo > 1 else conv
        if lo > 1 and any(m["origin"] == "user" for m in msgs[1:lo]):
            R["dropped: the turn alone exceeds the cap"] += 1
            log["fate"] = "dropped: turn alone exceeds cap"
            return None
        n = length(kept, tools)
        if n <= cap:
            break
        lo = max(lo, 1) + max(1, (n - cap) // 2000)              # step faster when far over
    g = set(grounding(msgs, lo if lo > 1 else 0, roots))
    masked = Counter()
    for k, m in enumerate(msgs):
        if m["role"] != "assistant" or (lo > 1 and 0 < k < lo):
            continue
        if m["origin"] != "own":
            conv[k]["weight"] = 0
            continue
        rules = set(m["rules"]) | ({"G path/old_string not visible in the sample"} if k in g else set())
        conv[k]["weight"] = 0 if rules else 1
        masked.update(rules)
    kept = conv[:1] + conv[lo:] if lo > 1 else conv
    trainable = sum(1 for m in kept if m.get("weight") == 1)
    if not trainable:
        R["dropped: nothing trainable left"] += 1
        log["fate"] = "dropped: nothing trainable"
        return None
    R["truncated"] += lo > 1
    log["truncated"] = lo > 1
    return {"messages": kept, "tools": json.dumps(tools, ensure_ascii=False),
            "meta": {"tokens": n, "images": sum(1 for m in kept if isinstance(m.get("content"), list)
                                                  for p in m["content"] if p.get("type") == "image"),
                     "trainable_replies": trainable, "masked": dict(sorted(masked.items()))}}   # sorted: rules are a set


def write(in_dir: str, out_dir: str, tok_name: str, cap: int) -> None:
    import random
    tok = Tok(tok_name, in_dir)
    length = Length(tok.tok, PROCESSOR)
    schemas = json.load(open(TOOLS))
    R, recs, runs_log = Counter(), [], []
    for f in sorted(glob.glob(f"{in_dir}/**/*.json.gz", recursive=True)):
        d = json.load(gzip.open(f))
        runs = [("main", build(d), schemas["MainAgent.respond"])]
        runs += [(f"planner{i}", build_calls(react, rs), schemas["PlannerAgent.do_work"])
                 for i, (react, rs) in enumerate(planner_chains(d)) if react]
        for agent, (msgs, info), tools in runs:
            R[f"runs: {agent[:7]}"] += 1
            log = {"fp": f"{d['turn_id']}#{agent}", "session_id": d["session_id"], "agent": agent[:7]}
            runs_log.append(log)
            rec = make_sample(msgs, info, tools, in_dir, tok, length, cap, R, log)
            if rec:
                rec["meta"] = {"source": "prod", "format": "trajectory", "class": "agent", "task_type": "trajectory",
                               "fp": f"{d['turn_id']}#{agent}", "session_id": d["session_id"], "turn_number": d["turn_number"],
                               "agent": agent[:7], **rec["meta"]}
                recs.append(rec)
    sessions = sorted({r["meta"]["session_id"] for r in recs})
    random.Random(SEED).shuffle(sessions)
    valid = set(sessions[:max(1, round(len(sessions) * VALID_SESSIONS))])
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    split = {"train": [r for r in recs if r["meta"]["session_id"] not in valid],
             "valid": [r for r in recs if r["meta"]["session_id"] in valid]}
    for name, rows in split.items():
        with (out / f"{name}.jsonl").open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    masked = Counter()
    for r in recs:
        masked.update(r["meta"]["masked"])
    stats = {"cap": cap, "tools": TOOLS, "rows": {k: len(v) for k, v in split.items()},
             "sessions": {"train": len(sessions) - len(valid), "valid": len(valid)},
             "agents": dict(Counter(r["meta"]["agent"] for r in recs)),
             "tokens": {"sum": sum(r["meta"]["tokens"] for r in recs),
                        "p50": pct([r["meta"]["tokens"] for r in recs], 50), "max": max(r["meta"]["tokens"] for r in recs)},
             "trainable_replies": sum(r["meta"]["trainable_replies"] for r in recs),
             "masked_replies_by_rule": dict(sorted(masked.items(), key=lambda kv: (-kv[1], kv[0]))), "pipeline": dict(sorted(R.items())),
             "runs": runs_log}
    (out / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in stats.items() if k != "runs"}, indent=2, ensure_ascii=False))


# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--in-dir", default=IN_DIR)
    cli.add_argument("--tokenizer", default=TOKENIZER)
    cli.add_argument("--stats", action="store_true", help="print what each rule does (no files written)")
    cli.add_argument("--out-dir", default=OUT_DIR)
    cli.add_argument("--cap", type=int, default=CAP)
    a = cli.parse_args()
    if a.stats:
        stats(a.in_dir, a.tokenizer)
    else:
        write(a.in_dir, a.out_dir, a.tokenizer, a.cap)
