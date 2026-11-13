"""Shared pieces of the teacher-intervention spike: paths, prompts, tasks, the student client, the journal."""

import json, os, time, urllib.error, urllib.request
from pathlib import Path

# Setting =================================================
SPIKE       = Path(__file__).resolve().parent
ROOT        = SPIKE.parents[2]
PROMPTS     = SPIKE / "prompts"
TASKS       = SPIKE / "tasks"
OUT_ROOT    = ROOT / "output/spike/1105-teacher-intervention"
WS          = "/workspace"                         # the path the student sees; mapped onto the episode's real dir
JAC_VERSION = "0.36.1"
STUDENT_URL = os.environ.get("STUDENT_URL", "http://127.0.0.1:8080/v1/chat/completions")
KEY_FILE    = Path.home() / ".config/jacllm/llama_api_key"
SUPPORT     = [{"path": "jac.toml", "purpose": "Configure Jac 0.36.1 with [project] kind web-app, entry-point main.jac."}]


# Functions ===============================================
def prompt(name: str) -> str:
    return (PROMPTS / name).read_text()


def tools() -> list[dict]:
    """The revdev student schemas plus the prod lookups (list_files, grep_search, find_symbol, analyze_project) and the
    prod delete_code."""
    return [t for f in ("tools.json", "lookup_tools.json", "delete_tool.json") for t in json.loads((PROMPTS / f).read_text())]


def load_task(slug: str) -> dict:
    return json.loads((TASKS / f"{slug}.json").read_text())


def student(messages: list[dict], tool_schemas: list[dict] | None, max_tokens: int, thinking: bool = True,
            temperature: float = 0.6, retries: int = 3) -> dict:
    """One chat completion from the served student (llama-server, OpenAI format). Returns the raw response."""
    body = {"model": "local", "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
            "top_p": 0.95, "chat_template_kwargs": {"enable_thinking": thinking}}
    if tool_schemas:
        body["tools"] = tool_schemas
    req = urllib.request.Request(STUDENT_URL, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {KEY_FILE.read_text().strip()}"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=1800) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as ex:
            detail = ex.read().decode(errors="replace")
            if ex.code == 500 and "Failed to parse tool call arguments as JSON" in detail:
                raise RuntimeError("student server could not parse a tool call in the conversation history") from ex
            if attempt == retries - 1:
                raise RuntimeError(f"student server HTTP {ex.code}: {detail[:240]}") from ex
            print(f"student call failed (HTTP {ex.code}); retrying", flush=True)
            time.sleep(10)
        except (urllib.error.URLError, TimeoutError) as ex:   # server restarting or a dropped connection
            if attempt == retries - 1:
                raise RuntimeError(f"student server unavailable: {ex}") from ex
            print(f"student call failed ({ex}); retrying", flush=True)
            time.sleep(10)


class Journal:
    """Append-only episode log: one JSON object per line, flushed per row (what happened, in order, by whom)."""
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.f, self.seq = path.open("a"), 0

    def write(self, actor: str, kind: str, **data) -> None:
        self.seq += 1
        self.f.write(json.dumps({"seq": self.seq, "time": time.time(), "actor": actor, "kind": kind, **data},
                                ensure_ascii=False) + "\n")
        self.f.flush()
