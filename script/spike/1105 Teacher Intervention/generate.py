"""Student generation with a repetition guard: stream raw completions, and when the student starts looping, cut the
loop and write "Wait, I'm repeating myself." into its own output, then let it continue from there.

The prompt is rendered by the server's own template (/apply-template, the same Jinja as /v1/chat/completions),
then /completion streams the continuation, so the harness can stop mid-reply and resume with a prefilled prefix.
Tool calls are parsed from the raw text (Qwen3.5 XML format), as llama-server would.
"""

import json, re, urllib.request, zlib

from spike_utils import KEY_FILE, STUDENT_URL

# Setting =================================================
SERVER       = STUDENT_URL.split("/v1/")[0]
INTERJECTION = "\n\nWait, I'm repeating myself. Let me stop, check what is actually still missing, and do that instead.\n\n"
MAX_FIXES    = 2               # interjections per turn; a third loop ends the turn as capped
MIN_UNIT     = 25              # chars: shorter lines ("}", "---") repeat legitimately
REPEATS      = 3               # an identical line seen this many times = looping (the 3rd copy is cut)
TAIL         = 2400            # chars checked by the compression rule
MIN_RATIO    = 0.12            # zlib(tail)/tail below this = a loop of near-identical lines
SAMPLING     = {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0}   # serve.sh defaults


# Functions ===============================================
def post(path: str, body: dict, stream: bool = False):
    req = urllib.request.Request(SERVER + path, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {KEY_FILE.read_text().strip()}"})
    r = urllib.request.urlopen(req, timeout=1800)
    return r if stream else json.loads(r.read())


def wire(messages: list[dict]) -> list[dict]:
    """Messages as the server takes them: harness-only keys dropped."""
    return [{k: v for k, v in m.items() if k in ("role", "content", "reasoning_content", "tool_calls", "tool_call_id")}
            for m in messages]


def outside_calls(text: str) -> str:
    """Text with tool-call bodies blanked (same length), so code inside a write_code is not judged as looping."""
    return re.sub(r"<tool_call>.*?(</tool_call>|$)", lambda m: " " * len(m.group(0)), text, flags=re.S)


def loop_cut(text: str) -> int | None:
    """Where to cut a loop in the generated text, or None. Rule 1: a line of MIN_UNIT+ chars appears REPEATS times
    (cut before the last copy). Rule 2: the tail compresses below MIN_RATIO (cut in the middle of the tail)."""
    seen = {}
    for m in re.finditer(r"[^\n]+", outside_calls(text)):
        unit = re.sub(r"\s+", " ", m.group(0)).strip().lower()
        if len(unit) < MIN_UNIT:
            continue
        seen[unit] = seen.get(unit, 0) + 1
        if seen[unit] >= REPEATS:
            return m.start()
    tail = outside_calls(text)[-TAIL:]
    if len(tail) == TAIL and len(tail.strip()) > TAIL // 2 and len(zlib.compress(tail.encode())) / TAIL < MIN_RATIO:
        return len(text) - TAIL // 2
    return None


def stream(prompt: str, n_predict: int):
    """Yield text pieces; the last item is the final event dict (stop type, token counts)."""
    r = post("/completion", {"prompt": prompt, "n_predict": n_predict, "stream": True, "cache_prompt": True, **SAMPLING},
             stream=True)
    with r:
        for raw in r:
            line = raw.decode().strip()
            if not line.startswith("data: "):
                continue
            ev = json.loads(line[6:])
            if ev.get("content"):
                yield ev["content"]
            if ev.get("stop"):
                yield ev
                return


def parse_calls(text: str, schemas: dict) -> list[dict]:
    """<tool_call><function=name><parameter=k>v</parameter></function></tool_call> -> OpenAI tool_calls."""
    calls = []
    for i, block in enumerate(re.findall(r"<tool_call>(.*?)</tool_call>", text, re.S)):
        m = re.search(r"<function=([^>]+)>(.*?)</function>", block, re.S)
        if not m:
            continue
        name, body, args = m.group(1).strip(), m.group(2), {}
        props = schemas.get(name, {}).get("parameters", {}).get("properties", {})
        for k, v in re.findall(r"<parameter=([^>]+)>\n?(.*?)\n?</parameter>", body, re.S):
            typ = props.get(k, {}).get("type")
            if typ == "boolean":
                args[k] = v.strip().lower() == "true"
            elif typ in ("integer", "number"):
                try:
                    args[k] = int(v) if typ == "integer" else float(v)
                except ValueError:
                    args[k] = v
            else:
                args[k] = v
        calls.append({"id": f"call_{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}})
    return calls


def turn(messages: list[dict], tool_schemas: list[dict] | None, max_tokens: int, thinking: bool,
         max_prompt: int | None = None) -> dict:
    """One student turn. Returns {message, capped, prompt_tokens, fixes}. `message` is an assistant message with
    reasoning_content / content / tool_calls; `fixes` lists each interjection (section, the copy that was cut). A
    trainer that masks spans finds the interjection by its text (INTERJECTION) in the message."""
    body = {"messages": wire(messages), "chat_template_kwargs": {"enable_thinking": thinking}, "add_generation_prompt": True}
    if tool_schemas:
        body["tools"] = tool_schemas
    prompt = post("/apply-template", body)["prompt"]
    prompt_tokens = len(post("/tokenize", {"content": prompt})["tokens"])
    if max_prompt and prompt_tokens > max_prompt:   # caller compacts instead; no tokens spent
        return {"message": None, "capped": False, "prompt_tokens": prompt_tokens, "fixes": []}
    text, fixes, used, capped = "", [], 0, False
    while True:
        cut, final = None, {}
        for piece in stream(prompt + text, max_tokens - used):
            if isinstance(piece, dict):
                final = piece
                break
            text += piece
            if len(fixes) < MAX_FIXES and "\n" in piece and (cut := loop_cut(text)) is not None:
                break
        if cut is None:
            used += final.get("tokens_predicted", 0)
            capped = final.get("stop_type") == "limit"
            break
        used += len(text) // 3                     # aborted stream reports no count; ~3 chars per token
        section = "reasoning" if thinking and "</think>" not in text[:cut] else "content"
        fixes.append({"section": section, "dropped": text[cut:][:400]})   # the cut copy, for the log
        text = text[:cut].rstrip() + INTERJECTION
        if used >= max_tokens:
            capped = True
            break
    text = text.split("<|im_end|>")[0]
    reasoning, answer = (text.split("</think>", 1) if "</think>" in text else (text, "")) if thinking else ("", text)
    schemas = {t["function"]["name"]: t["function"] for t in tool_schemas or []}
    calls = parse_calls(answer, schemas)
    msg = {"role": "assistant", "content": re.sub(r"<tool_call>.*?</tool_call>", "", answer, flags=re.S).strip()}
    if reasoning.strip():
        msg["reasoning_content"] = reasoning.strip()
    if calls:
        msg["tool_calls"] = calls
    if fixes:
        msg["repetition_fixes"] = fixes
    return {"message": msg, "capped": capped or (thinking and "</think>" not in text), "prompt_tokens": prompt_tokens,
            "fixes": fixes}
