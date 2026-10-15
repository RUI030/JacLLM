# Agent trajectories → SFT

Convert coding-agent session logs (Claude Code, opencode, pi, …) into one flat JSONL format. At train time, `common.to_template_input` turns it into chat messages, and the model's own chat template (its Jinja) renders them. We never write a template ourselves.

| file | role |
|---|---|
| `claude.py` | Claude Code logs (`~/.claude/projects`) → trajectory JSONL. **Reference converter**: copy its shape for a new harness. |
| `common.py` | Shared helpers: `redact` (secrets), `responses`, `mask`, `mark_loops`, `stats`, `write_trajectories` (validates role/mode, redacts, writes stats), and `to_template_input` (rows → what the chat template takes). |
| `harness/pi.json` | pi 1.0.4's exact system prompt (`{cwd}` placeholder) and tool schemas, captured from the request body it sends to an OpenAI-compatible endpoint. Used by `sft/tool_fim.py`; recapture after a pi upgrade (the eval runs pi with `--no-mcp --no-context-files --no-skills --no-extensions --no-prompt-templates`, which gives this same prompt). |

```bash
python script/dataset/trajectory/claude.py                       # all projects -> dataset/raw/trajectory/claude.jsonl (+ .stats.json)
python script/dataset/trajectory/claude.py --project '*JacCoder'  # one project
```

To add a harness:

1. Write `<harness>.py` that turns its logs into the rows below.
2. Run `common.mark_loops(rows)` on each trajectory.
3. Finish with `common.write_trajectories(trajs, "dataset/raw/trajectory/<harness>.jsonl")`.

## Format

Each line is one trajectory: `{"meta": {...}, "rows": [...]}`. Each row is **one event**, in the order the model saw it. `role` says **who** produced it, and `mode` says **what** it is:

| role | mode | fields | trained? |
|---|---|---|---|
| `user` | `prompt` | `content`: what the human typed | no |
| `user` | `command` | `content`: a user action the model sees (interrupt, `!` shell input) | no |
| `harness` | `system` | `content`: system prompt (only for a harness we don't know, see rules) | no |
| `harness` | `context` | `content`: text the harness injected as a user turn; optional `ref` | no |
| `harness` | `tool_result` | `content`, `status` | no |
| `assistant` | `think` | `content` | **yes** |
| `assistant` | `reply` | `content` | **yes** |
| `assistant` | `tool_call` | `name`, `args` (object), optional `id` | **yes** |

The loss mask is just `role == "assistant"`. An assistant row can also carry `"weight": 0` and `"masked": "<reason>"`: it stays in the context but gets no loss.

### Responses and tool calls

- **Consecutive `assistant` rows form one model response** (one assistant turn). Any `user` or `harness` row ends the response.
- **Several `tool_call` rows in one response** means the model sent them all at once, before seeing any result. Calling, reading the result and calling again shows up as separate responses, with `tool_result` rows between them.
- **Results pair with calls by order.** The `tool_result` rows after a response answer its `tool_call`s one-to-one, in call order. No ids are needed.
- **What the chat template actually uses:**
  - a call is rendered from `name` + `args` (Ornith: `<tool_call><function=NAME><parameter=KEY>VALUE</parameter>…`);
  - a result is rendered from `content` (`<tool_response>…</tool_response>`).
  - Everything else in the source log (timings, UI copies) is dropped.
- **`status`** isn't rendered; it's for filtering and analysis.

  | status | meaning |
  |---|---|
  | `ok` | the tool ran |
  | `error` | the tool reported an error (Claude `is_error`, opencode `state.status == "error"`, pi `isError`) |
  | `denied` | the user rejected the call; the response also gets `weight: 0` |
  | `missing` | the log has no result |
- **`id`** on a `tool_call` is optional: the source log's call id. It is used only to link a subagent trajectory to the call that spawned it.

```json
{
  "meta": {"harness": "claude", "model": "claude-opus-4-7", "session_id": "288058de-…", "segment": 0, "parent": null},
  "rows": [
    {"role": "user",      "mode": "prompt",      "content": "Add a /health endpoint to main.jac and check it builds."},
    {"role": "assistant", "mode": "think",       "content": "Need to see the walkers first."},
    {"role": "assistant", "mode": "reply",       "content": "Let me look at the file."},
    {"role": "assistant", "mode": "tool_call",   "name": "Read", "args": {"file_path": "main.jac"}},
    {"role": "harness",   "mode": "tool_result", "content": "1\twalker hello { … }", "status": "ok"},
    {"role": "assistant", "mode": "tool_call",   "name": "Edit", "args": {"file_path": "main.jac", "old_string": "walker hello", "new_string": "walker health { … }\n\nwalker hello"}},
    {"role": "assistant", "mode": "tool_call",   "name": "Bash", "args": {"command": "jac check main.jac"}},
    {"role": "harness",   "mode": "tool_result", "content": "The file main.jac has been updated.", "status": "ok"},
    {"role": "harness",   "mode": "tool_result", "content": "Error: line 3 …", "status": "error"},
    {"role": "harness",   "mode": "context",     "content": "<system-reminder>\nThe user sent a new message while you were working:\nalso add a /version endpoint\n</system-reminder>"},
    {"role": "assistant", "mode": "reply",       "content": "Fixing line 3 and adding /version."},
    {"role": "assistant", "mode": "tool_call",   "name": "Edit", "args": {"file_path": "main.jac", "old_string": "…", "new_string": "…"}},
    {"role": "harness",   "mode": "tool_result", "content": "The file main.jac has been updated.", "status": "ok"},
    {"role": "assistant", "mode": "reply",       "content": "Done: /health and /version, `jac check` passes."}
  ]
}
```

In this example:

- The Edit and the Bash calls belong to one response: both were sent before any result came back.
- The two results that follow answer them in order.

### Rules

- **`meta.harness`** is `"claude"`, `"opencode"` or `"pi"`. We supply the system prompt and tool schemas for these three, so don't add a `harness/system` row.
  - **Any other harness:** add its system prompt as the first row (`harness/system`) and its tool schemas as a top-level `"tools"` list in OpenAI function-schema format. Without them we can't train on it.
- **`meta.model`** is the model that produced the assistant rows. Drop responses from any other model, e.g. our own `JacLLM-*` running inside the harness.
- **Order within a response:** `think` → `reply` → `tool_call`(s). Then one `tool_result` per call. Harness `context` that arrived together with the results (e.g. a message queued mid-turn) comes after them.
- **`think`:** write it only when the log has the reasoning text. Most Claude thinking blocks are redacted (signature only), so they produce no row. Never put reasoning into a `reply`.
- **`user/command`:** user actions that leave text in the model's context:
  - "[Request interrupted by user]";
  - `!` shell input (`<bash-input>`; its output is `harness/context`).

  Slash commands (`/clear`, `/model`, `/mcp`, `/login`, `/cd`, `/compact`, …) are dropped, because the model is told not to respond to them. Their effects still show up:
  - `/compact` → a segment split, with the summary as `harness/context`;
  - `/cd` → a working-directory reminder;
  - `/clear` → a new session.
- **`harness/context`:** keep only injected text that carries task information:
  - a user message queued mid-turn;
  - background-task notifications (`<task-notification>`);
  - files or IDE selections shown to the model;
  - skill bodies loaded by a slash command or the Skill tool;
  - project instructions (CLAUDE.md / AGENTS.md);
  - compaction summaries;
  - `!` shell output.

  Drop harness bookkeeping: date, token counts, output style, tool/skill listings, mode switches. It carries no task signal, and the harness we deploy into won't inject it.
- **`ref` on a `harness/context` row** is set when the row is a background-task notification. It holds the `id` of the `tool_call` that started the task (async `Agent`, background `Bash`, `Monitor`).
  - These results arrive turns later, as a user-turn message. They are not tool results, so they stay `context` at the position the model saw them.
  - Folding a subagent into its call later means replacing the call's "launched" `tool_result` with the notification's `<result>` and dropping the notification.
- **Keep tags verbatim** (`<system-reminder>`, `<task-notification>`, `<bash-input>`, …). The rows are masked, but the tags are how the model tells harness notices apart from the user.
- **Images** become the text `[image]`.
- **`weight: 0`** goes on every assistant row of a response the model shouldn't learn from:
  - denied calls (`masked: "denied"`);
  - loops (`masked: "loop"`, set by `common.mark_loops`): the same tool calls 3+ responses in a row, or the same long reply repeated.

  Don't delete these rows: later rows refer to them.
- **Secrets:** `write_trajectories` redacts API-key patterns (`<REDACTED>`) and personal email addresses (`<EMAIL>`); `example.com` and `noreply@` addresses are kept. Report anything else sensitive.

## Session structure

- **Flatten to the path actually taken.** If the log is a tree, keep the path from the root to the final leaf and count the abandoned branches. (In Claude Code the tree comes from `uuid` / `parentUuid`; a rewind or retry creates a sibling.)
  - SFT doesn't use the abandoned branches. They are what the user rejected, so they could later become preference data.
  - **Claude Code quirk:** parallel tool results hang off sibling records, not off the active chain. Look them up by `tool_use_id`.
- **Compaction splits a session into segments** (`meta.segment` 0, 1, …). A new segment starts with the summary as a `harness/context` row.
- **A segment needs a `user/prompt` row before its first assistant row.** Otherwise the chat template refuses it (`No user query found in messages`).
- **Subagents are separate trajectories** with `meta.parent = {"session_id", "tool_call_id", "agent_type"}`.
  - `tool_call_id` is the `id` of the spawning `tool_call` in the parent (`Agent` / `Task` / `task`).
  - In the parent, that call stays a normal tool call, and its result is the subagent's report.
  - How subagent trajectories will be used is still open; they will probably be folded into tool calls. **Report their counts.**

## Dropped from Claude Code logs

| what | how to recognize it |
|---|---|
| UI / bookkeeping records | `type` ∈ `mode`, `permission-mode`, `atis-latch`, `ai-title`, `last-prompt`, `queue-operation`, `file-history-*`, `bridge-session`, `relocated`, `cost-state` |
| status records | `type: system` except `compact_boundary` |
| slash commands and their output | user text starting with `<command-name>`, `<command-message>`, `<command-args>` or `<local-command-…>` |
| failed / synthetic responses | `model` not `claude-*` (`<synthetic>`, `JacLLM-*`), `isApiErrorMessage`, `isAbortedMidStream` |
| bookkeeping / private attachments | `SKIP_ATTACHMENTS` in `claude.py`: `environment` (Claude's env block, cwd updates), `session_context` (user email, git status), `date`, `task_reminder`, `total_tokens_reminder`, `output_style*`, `deferred_tools_*`, `skill_listing`, `agent_listing_delta`, `mcp_instructions_delta`, `auto_mode`, `model`, `command_permissions`, `credential_org`, `prompt_snapshot`, `silent_turn_reminder`, `thinking_drop`, `remote_session_change`, `bridge_status` |

The remaining attachments become `harness/context` rows holding their `rendered` text, which is exactly what the model saw.

Persisted large outputs (`<persisted-output> … Preview …`) stay as the preview, since the model only saw the preview.

## Tags the model sees (Claude Code)

This is every tag found in model-visible user and attachment text across all local logs, and where it ends up. Tool output is not listed: it is arbitrary (HTML, logs) and is kept verbatim in `tool_result`.

| tag | what | becomes |
|---|---|---|
| `<system-reminder>` | harness notice wrapper | `harness/context` when it carries task info (queued user message, file / IDE selection, CLAUDE.md, compaction note, `/cd`); dropped for bookkeeping types (`SKIP_ATTACHMENTS`) |
| `<total_tokens>` | context-budget counter | dropped |
| `<task-notification>` (`<task-id>`, `<tool-use-id>`, `<output-file>`, `<status>`, `<summary>`, `<event>`, `<note>`, `<result>`, `<usage>`) | background task / Monitor event / async subagent finished | `harness/context` + `ref` |
| `<new-diagnostics>` | IDE diagnostics | `harness/context` |
| `<bash-input>` | user's `!` shell command | `user/command` |
| `<bash-stdout>`, `<bash-stderr>` | its output | `harness/context` |
| `<command-name>`, `<command-message>`, `<command-args>`, `<local-command-stdout>`, `<local-command-caveat>` | slash commands and their output | dropped |
| `[Request interrupted by user]` (not a tag) | user pressed Esc | `user/command` |
| HTML / `<think>` etc. inside a human message | pasted content | kept inside `user/prompt` |

## Field map: Claude Code → rows

| Claude Code | keep? | becomes |
|---|---|---|
| `user.message.content` (string / `text` block) | ✅ | `user/prompt`; `user/command` for interrupts and `<bash-input>`; `harness/context` for `<system-reminder>`, `<task-notification>`, `<bash-stdout>` |
| `user.isMeta` | ✅ | `harness/context` (skill bodies, `/cd` reminders) |
| `user` block `tool_result{tool_use_id, content, is_error}` | ✅ | `harness/tool_result{content, status}`, placed after its response in call order |
| `user.toolUseResult` | ❌ | a richer UI copy of the result |
| `user.toolDenialKind` | 🔧 | `status: "denied"`; `weight: 0` on the response |
| `user.isCompactSummary` | ✅ | first `harness/context` row of the next segment |
| `assistant` block `thinking{thinking, signature}` | ✅ if it has text | `assistant/think` |
| `assistant` block `text` | ✅ | `assistant/reply` |
| `assistant` block `tool_use{id, name, input}` | ✅ | `assistant/tool_call{id, name, args: input}` |
| `assistant.message.id` | 🔧 | groups one response's blocks (Claude Code writes one record per block); not emitted |
| `assistant.message.model` | ✅ | `meta.model` (most common in the segment) |
| `message.usage`, `stop_reason`, `requestId`, `effort`, … | ❌ | |
| `attachment.rendered` | ✅ unless skipped | `harness/context` |
| `uuid`, `parentUuid`, `logicalParentUuid` | 🔧 | flattening; not emitted |
| `system.subtype == compact_boundary` | 🔧 | segment split |
| `subagents/agent-*.jsonl` + `.meta.json` (`toolUseId`, `agentType`) | 🔧 | separate trajectory + `meta.parent` |
| `sessionId` | ✅ | `meta.session_id` |
| `cwd`, `gitBranch`, `version`, `timestamp`, `entrypoint`, `userType`, `slug`, `permissionMode`, … | ❌ | |

## Stats

`write_trajectories` writes `<out>.stats.json`. Send it along with the data. It contains:

- trajectories and subagent trajectories;
- rows per `role/mode`;
- responses, plus masked responses by reason;
- calls per tool name, including the subagent tools (`tool:Agent`, `tool:Task`, `tool:task`);
- results per `status`;
- the converter's own counts (sessions, abandoned branches).

## Training side (ours, not the converter's)

`common.to_template_input(traj, system)` turns rows into chat messages:

| rows | message |
|---|---|
| one response's `assistant` rows | one `assistant` message (`reasoning_content`, `content`, `tool_calls` with generated ids, `weight`) |
| `harness/tool_result` | a `tool` message, paired with the next pending call |
| `user/*` + `harness/context` | one `user` turn |
| `harness/system`, or the harness's prompt file | first message |

All 28 Claude trajectories render through the Ornith template, and every assistant prefix renders identically inside the full conversation.

Still to do:

- system prompts and tool schemas per harness;
- mapping tool names between harnesses (Claude `Bash` → pi `bash`, …);
- `sft.py` mask support for `tools=` and `weight`;
- windowing long trajectories: the median Claude trajectory is ~69k tokens, the longest ~275k.
