"""Teacher: `claude -p` reads the student's trajectory up to a repeated failure and writes the student's next turn.

The teacher runs in a scratch copy of the workspace (read tools, Edit/Write inside the copy only, `jac check` /
`jac test`) with the user's normal Claude settings (skills, MCP). It tries its fix in the copy, checks it, and proposes
one observable next turn for the student's workspace: tool calls or a final text.
"""

import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

from spike_utils import WS, JAC_VERSION

# Setting =================================================
MODEL   = "opus"
TIMEOUT = 1200
TOOLS   = ["Read", "Glob", "Grep", "Skill", "Bash(jac check:*)", "Bash(jac test:*)", "Bash(jac run:*)",
           "Bash(jac clean:*)", "Bash(jac install:*)", "Bash(jac add:*)", "Bash(jac retheme:*)", "Bash(jac --version)", "Bash(ls:*)", "Bash(fe-check)", "Bash(fe-check:*)",
           "Bash(idiom-check)", "Bash(idiom-check:*)"]
HERE    = Path(__file__).resolve().parent
CHECKS  = {"fe-check": "frontend_check.py", "idiom-check": "idiom_check.py --workspaces"}   # ours, teacher only
DENY    = ["NotebookEdit", "WebFetch", "WebSearch"]
SCHEMA  = {
    "type": "object", "additionalProperties": False, "required": ["content", "tool_calls", "diagnosis"],
    "properties": {
        "diagnosis":  {"type": "string", "description": "For the log only: what the student got wrong and why."},
        "content":    {"type": "string", "description": "Visible text of the turn; the final summary when there are no tool calls."},
        "tool_calls": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["name", "arguments"],
                       "properties": {"name": {"type": "string"}, "arguments": {"type": "object"}}}},
    },
}
INSTRUCTIONS = f"""You review a Jac {JAC_VERSION} coding task after three failed attempts at the same place.
Propose ONE next observable action that would help complete the task. Return only the requested JSON fields.

Rules for that turn:
- It must follow from what the student can see in the trajectory below. If it needs a file's content that is not in
  the trajectory, the right turn is a read_file of that file, not an edit based on content the student never saw.
  Likewise, a fix that names a module or a symbol from another file (an import, its path) needs that location in the
  trajectory; if it is not there, the right turn is a lookup (find_symbol, list_files, grep_search), not a guess.
- Pick the lookup that fits what is known (the tools' own descriptions), not one tool for everything:
  - an exact symbol name (an import, a call, a type named in an error): find_symbol. It reads the compiler's symbol
    table (definitions and uses), so it never matches comments or strings.
  - something that is not a known symbol name (message text, a string, a route, a config key, a CSS class) or a name
    only partly known (find_symbol found nothing for it): grep_search, narrowed with path / file_pattern.
  - which files or modules exist: list_files.
  - an overview of the project's archetypes (nodes, edges, objs, walkers) before a change across modules or after a
    resume: analyze_project.
  - the content of a file about to be edited: read_file of that file. Look up first, then read what the lookup
    points at; do not read every file, and do not repeat a lookup whose answer is already in the trajectory.
- Write idiomatic Jac as the Jac skills describe it, not Python or React with braces. Before writing code of a kind,
  load its skill (jac-cl-components for client components, jac-fullstack-patterns for main.jac wiring, jac-testing
  for tests, jac-by-llm for LLM functions, jac-walker-patterns / jac-node-edge-patterns for graphs). For example:
  components are `def:pub Name() -> JsxElement` with `has` state that is rebound (never mutated in place), mount
  effects in `async can with entry`, lists in `{{for x in xs {{ ... }}}}` slots, handlers as `def` methods typed with
  DOM events; the entry module exports `def:pub app`, and every component used in JSX is imported; own types are
  `obj`, enums are `enum`, a CLI entry is `with entry:__main__`; no `any` to silence a type error.
- A one-off check (a probe script to try a call) may go in a scratch file such as {WS}/scratch/check.jac, and is
  deleted with delete_code once it has answered; the task is not done while one is left. A check worth keeping is a
  `test` block in the module or its `.test.jac` annex, not a scratch file. Nothing is written outside {WS}.
- Use only the student's tools, with arguments that match their schemas exactly. Paths are absolute under {WS}.
  Code written to a file holds only the code: never a Markdown ``` fence (fences only inside .md files).
- When the task is already complete (the checks passed), the turn is a short final summary with no tool calls. Claim
  only files and checks that appear in the trajectory.
- When the student was asked something outside the workspace (network, travel, weather), the turn declines in text.
- Prefer the smallest correct step. The current directory is a disposable scratch copy of the student's workspace
  ({WS} = this directory). Before answering, apply your proposed change here with Edit/Write (exactly the content
  your tool calls will write) and run `jac check` / `jac test` on it; iterate until it passes. Only then return the
  tool calls for the student's workspace. Bash allows only single commands starting with `jac check`, `jac test`,
  `jac run`, `jac clean`, `jac install`, `jac add`, `jac retheme`, `ls`, `fe-check` or `idiom-check`, run from this directory: no `cd`, `&&`, `;`, pipes, heredocs, `sed` or `python`
  (they are denied); change files with Edit/Write. Use the Jac skills when unsure of syntax. Say in `diagnosis`
  what you ran and whether it passed.
- Two checks are yours only (the student has neither the commands nor their output): `fe-check` (does the web app's
  frontend mount: the entry module exports a client `def:pub app`, `jac build` emits JS that parses, JSX tags are
  real elements, every component module is bundled) and `idiom-check` (non-idiomatic Jac: `jac check --lint` plus
  the skills' rules). Use them to test your own change. Your turn for the student must still follow from what the
  student can see: to act on what fe-check found, read the file or run what the student has (`jac check
  --placements <entry>`), never cite fe-check or idiom-check. The student's turn never runs `jac build`: its
  compiled JS output is not part of the app, and everything the app needs is written in .jac files.
- `content` is the student's own visible text for this turn, in its voice: first person ("The import of X is
  missing, so ..."), never addressed to the student ("you", "the student").
- `diagnosis` is a brief, observable explanation for the experiment log. Do not include private reasoning or
  reconstruct any model's internal thought process.
"""


# Functions ===============================================
def render(messages: list[dict], failed: list[int]) -> str:
    """Trajectory as text for the teacher; `failed` are indexes of the failed assistant attempts."""
    out = []
    for i, m in enumerate(messages):
        tag = f"[{i}] {m['role'].upper()}" + ("  <-- FAILED ATTEMPT" if i in failed else "")
        body = []
        if m.get("content"):
            body.append(m["content"] if isinstance(m["content"], str) else json.dumps(m["content"]))
        for c in m.get("tool_calls") or []:
            body.append(f"(tool call) {c['function']['name']} {c['function']['arguments']}")
        out.append(tag + "\n" + "\n".join(body))
    return "\n\n".join(out)


def ask(messages: list[dict], failed: list[int], tool_schemas: list[dict], workspace: Path, log_dir: Path,
        note: str = "") -> dict:
    """Run the teacher once. Returns {diagnosis, content, tool_calls, raw} or raises RuntimeError."""
    log_dir.mkdir(parents=True, exist_ok=True)
    request = (INSTRUCTIONS + "\n\n# Student tool schemas\n" + json.dumps(tool_schemas) + "\n\n# Trajectory\n"
               + render(messages, failed) + (f"\n\n# Note\n{note}" if note else ""))
    (log_dir / "request.md").write_text(request)
    with tempfile.TemporaryDirectory(prefix="teacher-ws-") as d:
        snap = Path(d) / "workspace"
        shutil.copytree(workspace, snap, ignore=shutil.ignore_patterns(".jac", "node_modules", "__pycache__"))
        scratch = [f"{t}(/{snap}/**)" for t in ("Edit", "Write")]   # "//abs/path": edits only inside the copy
        cmd = ["claude", "-p", "--model", MODEL, "--output-format", "json", "--json-schema", json.dumps(SCHEMA),
               "--allowedTools", *TOOLS, *scratch, "--disallowedTools", *DENY, "--no-session-persistence"]
        bin_dir = Path(d) / "bin"
        bin_dir.mkdir()
        for name, script in CHECKS.items():
            (bin_dir / name).write_text(f'#!/bin/sh\nexec "{sys.executable}" "{HERE}/{script.split()[0]}" '
                                        f'{" ".join(script.split()[1:])} "${{@:-.}}"\n')
            (bin_dir / name).chmod(0o755)
        env = {**os.environ, "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}"}
        r = subprocess.run(cmd, input=request, cwd=snap, capture_output=True, text=True, timeout=TIMEOUT, env=env)
    (log_dir / "stdout.json").write_text(r.stdout)
    (log_dir / "stderr.txt").write_text(r.stderr)
    if r.returncode != 0:
        detail = r.stderr[-500:]
        if not detail and r.stdout:
            try:
                result = json.loads(r.stdout)
                detail = result.get("result", "")[-500:]
            except json.JSONDecodeError:
                detail = r.stdout[-500:]
        raise RuntimeError(f"teacher exit {r.returncode}: {detail}")
    data = json.loads(r.stdout)
    out = data.get("structured_output")
    if out is None:                                # older CLI: the JSON is the result text
        out = json.loads(data.get("result", "{}"))
    out["raw"] = {k: data.get(k) for k in ("total_cost_usd", "num_turns", "duration_ms", "usage", "modelUsage")}
    return out
