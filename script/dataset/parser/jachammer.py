"""Building JacHammer-format SFT rows: the logged session's prompt and tools, real tool results, message shapes."""

import difflib, json, re, subprocess, tempfile, uuid
from pathlib import Path

ROOT       = Path(__file__).resolve().parents[3]
JAC        = Path.home() / ".jacbin_pinned/jac"            # the binary JacHammer runs projects on (0.34.28)
JACBUILDER = ROOT.parent / "jacBuilder"
TOOLS_JAC  = ROOT / "script/dataset/sft/jachammer_tools.jac"
# a JacHammer session on jac 0.34.28 with the skill-loading prompt edits: system prompt, tool schemas, user wrapper
SESSION    = ROOT / "output/eval/agent/routing_blog/jaccoder-JacLLM-1107-teacher-iv-v6-on-1105_11-09_18-53/calls.jsonl"


def session_parts(session: Path = SESSION) -> tuple[str, str, str, list[dict]]:
    """(system prompt, user wrapper text, the session's project dir, tool schemas) from the last logged request."""
    last = json.loads(session.read_text().splitlines()[-1])["request"]
    req = json.loads(last) if isinstance(last, str) else last
    user = req["messages"][1]["content"][0]["text"]
    project = re.search(r"Working directory: (\S+?)\\n", user).group(1)
    return req["messages"][0]["content"], user, project, req["tools"]


def user_text(wrapper: str, project: str, fake: str, request: str) -> str:
    """The session's user message with this row's project and request (the wrapper is a Python repr)."""
    old = wrapper[wrapper.rindex("---\\n\\n") + 6:wrapper.index("\\n', '')")]
    esc = request.strip().replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    return wrapper.replace(old, esc).replace(project, fake)


def fake_root() -> str:
    """A project path shaped like the ones JacHammer's sandbox uses."""
    return f"/app/.jachome/.jac-ide/projects/{uuid.uuid4()}/prj_{uuid.uuid4().hex}"


def run_tools(reqs: list[dict]) -> list:
    """Run jachammer_tools.jac (JacHammer's own tools and check formatting) on a batch of requests."""
    with tempfile.TemporaryDirectory(prefix="jh-req-") as d:
        (Path(d) / "req.json").write_text(json.dumps(reqs))
        r = subprocess.run([str(JAC), "run", str(TOOLS_JAC), "--", f"{d}/req.json", f"{d}/res.json"], cwd=JACBUILDER,
                           env={"PATH": f"{JAC.parent}:/usr/bin:/bin", "HOME": str(Path.home()), "JACPATH": str(JACBUILDER)},
                           capture_output=True, text=True, timeout=3600, stdin=subprocess.DEVNULL)
        if r.returncode:
            raise RuntimeError(f"jachammer_tools.jac failed: {r.stderr[-800:]}")
        return json.loads((Path(d) / "res.json").read_text())


def call(name: str, args: dict) -> dict:
    return {"id": "call_" + uuid.uuid4().hex[:24], "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def turn(content: str, reasoning: str, c: dict, weight: int) -> dict:
    return {"role": "assistant", "content": content, "reasoning_content": reasoning, "tool_calls": [c], "weight": weight}


def result(c: dict, text: str) -> dict:
    return {"role": "tool", "tool_call_id": c["id"], "content": text}


def hunk_edits(before: str, after: str) -> list[tuple[str, str]]:
    """The (old_string, new_string) edit_code pairs that turn `before` into `after`, one per changed block of lines,
    in order. Each old_string carries context lines until it occurs exactly once in the file it is applied to."""
    a, b = before.split("\n"), after.split("\n")
    ops = [o for o in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if o[0] != "equal"]
    edits, cur, shift = [], list(a), 0
    for _, i1, i2, j1, j2 in ops:
        i1, i2 = i1 + shift, i2 + shift
        new = b[j1:j2]
        lo, hi = i1, i2
        while True:                                   # widen by a line above, then below, until unique
            old = "\n".join(cur[lo:hi])
            if hi > lo and old.strip() and "\n".join(cur).count(old) == 1:
                break
            if lo > 0 and ((hi - lo) % 2 == 0 or hi >= len(cur)):
                lo -= 1
            else:
                hi += 1
        repl = cur[lo:i1] + new + cur[i2:hi]
        edits.append((old, "\n".join(repl)))
        cur = cur[:lo] + repl + cur[hi:]
        shift += len(new) - (i2 - i1)
    assert "\n".join(cur) == after
    return edits
