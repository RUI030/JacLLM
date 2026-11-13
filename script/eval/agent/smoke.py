"""End-to-end smoke test of a model served by serve.sh; writes output/serve/<model>/smoke.json.

1. template parity: the HF render used in training (train/sft_img.py) vs llama-server /apply-template on the
   text-only rows of --rows. Goes to the server port directly, not through the proxy, so no prod text lands in
   calls.jsonl; only match flags and offsets are saved.
2. plain chat: reasoning comes back in `reasoning_content`, separate from `content`.
3. tool call: jac_coder's MainAgent tool schema, streamed, the way byLLM calls it.
4. vision: a generated image with text the model must read.

    python script/eval/agent/smoke.py --model <model> [--rows dataset/raw/prod/sft/prod-64k/valid.jsonl]
"""

import argparse, base64, io, json, sys, time, urllib.request
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "train"))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
import sft_img                                     # imports unsloth before transformers

from PIL import Image, ImageDraw, ImageFont
from transformers import AutoTokenizer

# Setting =================================================
ROOT     = Path(__file__).resolve().parent.parent.parent.parent
PROXY    = "http://127.0.0.1:8080"
SERVER   = "http://127.0.0.1:8081"
KEY_FILE = Path.home() / ".config/jacllm/llama_api_key"
ROWS     = ROOT / "dataset/raw/prod/sft/prod-64k/valid.jsonl"
TOOLS    = ROOT / "dataset/raw/prod/tools_f14d1f1.json"     # jac_coder tool schema snapshot, keyed by agent method

# Functions ===============================================
def post(base: str, path: str, body: dict, key: str) -> tuple[str, float]:
    req = urllib.request.Request(base + path, json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        raw = r.read().decode()
    return raw, time.time() - t


def chat(body: dict, key: str) -> tuple[dict, float]:
    raw, dt = post(PROXY, "/v1/chat/completions", {"model": "local", **body}, key)
    return json.loads(raw), dt


def stream_chat(body: dict, key: str) -> tuple[dict, float]:
    """Streamed chat folded back into content, reasoning length and tool calls."""
    raw, dt = post(PROXY, "/v1/chat/completions", {"model": "local", "stream": True, **body}, key)
    content, reasoning, calls = "", "", {}
    for line in raw.splitlines():
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        choices = json.loads(line[6:])["choices"]
        if not choices:
            continue
        d = choices[0].get("delta", {})
        content += d.get("content") or ""
        reasoning += d.get("reasoning_content") or ""
        for c in d.get("tool_calls") or []:
            e = calls.setdefault(c["index"], {"name": "", "arguments": ""})
            e["name"] += c.get("function", {}).get("name") or ""
            e["arguments"] += c.get("function", {}).get("arguments") or ""
    return {"content": content, "reasoning_len": len(reasoning), "tool_calls": list(calls.values())}, dt


def template_parity(model_dir: Path, rows_path: Path, key: str) -> list[dict]:
    tok = AutoTokenizer.from_pretrained(model_dir)
    rows = [json.loads(l) for l in open(rows_path)]
    text_rows = [r for r in rows if not any(isinstance(m.get("content"), list)
                                            and any(c.get("type") == "image" for c in m["content"]) for m in r["messages"])]
    parity = []
    for r in text_rows:
        msgs, tools, _, _ = sft_img.chat_messages(r)
        hf = tok.apply_chat_template(msgs, tools=tools, tokenize=False)
        oai = [{k: v for k, v in m.items() if k != "weight" and v is not None} for m in r["messages"]]
        srv = json.loads(post(SERVER, "/apply-template", {"messages": oai, "tools": tools}, key)[0])["prompt"]
        n = next((i for i, (a, b) in enumerate(zip(hf, srv)) if a != b), min(len(hf), len(srv)))
        parity.append({"fp": r["meta"].get("fp"), "hf_chars": len(hf), "server_chars": len(srv),
                       "identical": hf == srv, "server_extends_hf": srv.startswith(hf), "first_diff_at": n,
                       "server_tail_after_hf": srv[len(hf):] if srv.startswith(hf) else None})
    return parity


def vision_probe(out_png: Path) -> str:
    """A red square and 'TODO: 7 items' as a PNG data URL (also saved to out_png)."""
    img = Image.new("RGB", (640, 360), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, 240, 240], fill="red")
    d.text((300, 120), "TODO: 7 items", fill="black", font=ImageFont.load_default(size=48))
    buf = io.BytesIO(); img.save(buf, "PNG"); img.save(out_png)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", required=True, help="name under output/model and output/serve")
    ap.add_argument("--rows", type=Path, default=ROWS)
    a = ap.parse_args()
    key = KEY_FILE.read_text().strip()
    out = ROOT / "output/serve" / a.model
    res = {}

    res["template_parity"] = template_parity(ROOT / "output/model" / a.model, a.rows, key)
    print("parity:", [(p["identical"], p["server_extends_hf"], p["server_tail_after_hf"]) for p in res["template_parity"]])

    r, dt = chat({"messages": [{"role": "user", "content": "In Jac, write a walker that visits every node connected "
                                "to root and prints it. Keep it short."}], "max_tokens": 6000}, key)
    m = r["choices"][0]["message"]
    res["plain_chat"] = {"seconds": round(dt, 1), "usage": r["usage"], "finish": r["choices"][0]["finish_reason"],
                         "reasoning_len": len(m.get("reasoning_content") or ""), "content": m.get("content"),
                         "timings": r.get("timings")}
    print("plain:", res["plain_chat"]["finish"], res["plain_chat"]["usage"], "reasoning", res["plain_chat"]["reasoning_len"])

    tools = json.loads(TOOLS.read_text())["MainAgent.respond"]
    o, dt = stream_chat({"messages": [
        {"role": "system", "content": "You are JacCoder, an agent that builds Jac apps using the provided tools."},
        {"role": "user", "content": "Working directory: /workspace/app\n\nOpen main.jac and tell me what it does."}],
        "tools": tools, "max_tokens": 4000}, key)
    res["tool_call"] = {"seconds": round(dt, 1), "n_tools_offered": len(tools), **o}
    print("tool:", o["tool_calls"], repr(o["content"][:200]))

    url = vision_probe(out / "vision_probe.png")
    r, dt = chat({"messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": url}},
        {"type": "text", "text": "What text is written in this image, and what color is the square?"}]}],
        "max_tokens": 3000}, key)
    res["vision"] = {"seconds": round(dt, 1), "usage": r["usage"], "content": r["choices"][0]["message"].get("content")}
    print("vision:", repr(res["vision"]["content"]))

    (out / "smoke.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
