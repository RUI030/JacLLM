# Checkpoint handoff and next reference (2026-10-30)

`checkpoint.resume_handoff` now derives a fresh continuation context from
the saved checkpoint and observed `run_command` results. It lists each
planned file's presence, SHA256, size, and detected `NotImplementedError`
stub, plus up to eight actual command/result excerpts. It explicitly says
that file presence and hashes do not prove behavior. The adapter writes
`handoff.json` beside `checkpoint.json`, restores the workspace, and asks
the teacher to read the plan once and inspect only files needed for its next
edit or whose state is uncertain. It also asks for one permitted command per
tool call. The raw tool transcript remains unchanged.
Stub detection reads planned `.jac` file bytes even when the plan still says
`pending`; a `pending` status cannot hide an existing scaffold body.

The existing Mindcraft auto-compaction checkpoint produced a five-file,
five-command handoff of about 3.3 KB. This is a deterministic preview, not
evidence that a teacher will actually read less. The 12 revdev unit tests
pass with the pinned Jac 0.34.27.

The first teacher A/B run failed before its first decision: sandboxed Claude
CLI returned `EAI_AGAIN` after about 178 seconds. It produced no tool calls
and is not exportable. A retry with network access was rejected by automatic
approval review because the task, plan, checkpoint, and repository-derived
context would be sent to Claude's external service without explicit
approval of that payload. The user subsequently authorized the Claude CLI
teacher run. The earlier rejection was not bypassed.

For the next cross-repo run, `script/dataset/revdev/recipes/a2pulse_week/`
contains a reviewable user task, grounded JacCoder plan, and source
provenance. The scope is a clean-workspace weekly brief date app with a
service, client component, style, config, and entry file. Its dependency
order passes `tasks.validate_plan`. The unmodified A2-Pulse reference
passes `jac check main.jac` on Jac 0.34.27. An isolated copy built its
client and served `GET /` with HTTP 200. Chromium rendered its welcome page
with visible onboarding text and zero page or console errors; raw browser
output and screenshot are in `dataset/raw/revdev/A2Pulse/preflight/`.
The earlier original date-service tests passed 4/4. The subsequent teacher
reconstruction now passes the original tests, 55-call replay, and actual
Chromium date-preview flow. Its validation status is `accepted`; the isolated
export and preview are described in `REVDEV_RENDERED_EXAMPLES.md`.
`validate.py` now accepts an alternate original acceptance file and its
destination/test target, so this repo can reuse the same independent Jac
check and test gate without hardcoding Mindcraft's fixture. The A2-Pulse
date test should be copied as `services/brief_dates.test.jac` and run through
`jac test services/brief_dates.jac` in a verification copy.
