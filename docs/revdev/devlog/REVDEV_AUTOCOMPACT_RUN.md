# Token-triggered full-app continuation run (2026-10-30)

## Experiment

Reran the already validated Mindcraft task from an empty workspace with the
captured JacCoder prompt, Claude CLI JSON-decision adapter, and actual JacCoder
tools. The run was deliberately kept separate from the earlier pilot:
`dataset/raw/revdev/Mindcraft/m3/runs/claude_teacher_autocompact_v1/`.
Jac was pinned to 0.34.27. The fixed step checkpoint was disabled
(`--checkpoint-step 9999`); the runner checkpointed only when its rendered
context estimate exceeded 58,000 tokens. The first segment reached 58,507
tokens by that estimate after 25 decisions, then the workspace and plan were
restored into a fresh continuation context. There was one checkpoint and two
executed segments, ending after 37 decisions.

The first segment scaffolded all five planned files, implemented the service
and client, ran the service tests (5/5), and built the client bundle. Real
scaffold and Jac syntax rejections were retained. The second segment started
by reading the saved plan and current source, reran checks and tests, then
finished. The first segment's attempted final JSON had an extra `output`
property and was rejected by the adapter; it did not stop the run. This is a
real transport error, not a successful final response.

## Independent gates

- `validate.py` passed the independent Jac check and three acceptance tests.
- The app started on localhost and built its client bundle. A Node Playwright
  runner used the locally installed browser after the Python test environment
  lacked `playwright`. Five behavior flows passed: empty island, check-in and
  placement, interaction and intention path, reset, and crisis guidance
  without an entity. No browser page error was observed. The first attempt
  used the old pilot's exact UI labels and failed to find text even though the
  new page rendered; the behavior rerun used this app's visible labels. The
  failed attempt's screenshot and the successful rerun's `browser.json` remain
  in the raw run.
- The first replay failed only at `jac build` because sandboxed Bun could not
  access its temporary directory. A replay with the same local execution
  permissions as the teacher passed: 32 executed tool calls, matching source
  hashes and diagnostic status. The initial replay's tool outputs remain in
  its temporary replay workspace; the raw run's `replay.json` contains the
  successful rerun. Final `validation.json` is `accepted`.

The exporter preview is kept under the raw run, not promoted to the active
SFT directories. After path normalization and rejection filtering, exact
training-template lengths are 50,510 tokens for `revdev_app`, 26,711 for
`revdev_resume`, 33,366 for `revdev_scaffold`, and 944 for `revdev_plan`.
The plan also has a 16k mirror, making five JSONL records but only four
distinct examples. No function projection was accepted. The quality audit
passes, but these examples share the earlier Mindcraft reference and must
stay in the same split; counting them as another independent repo would be
misleading.

## What the run teaches about compaction

The token-triggered checkpoint and fresh tool-use continuation work. The
current resume instruction is too generic: the teacher reread several whole
files and attempted compound shell commands that the adapter disallows.
Before scaling, produce a **deterministic handoff** from the checkpoint:
planned paths, actual file hashes, stub/implemented observations, and exact
verification outcomes. The resume prompt should ask for a short state audit,
read the plan plus only relevant changed or uncertain files, then continue
with one allowed command per tool call. Do not provide hidden reference code
or fabricated prior reasoning.

Supervision should distinguish (1) the app prefix that intentionally ends at
a checkpoint, (2) the resumed agent's observed reads, edits and checks, and
(3) any separately trained handoff summary, which must be produced and
validated against the snapshot. The invalid final decision above is retained
in the raw event log, excluded from SFT projection, and counted in
`projection_excluded_rejected_finals`. The next full-app run should use a
different source repo and a repo-heldout split. See
[data quality](REVDEV_DATA_QUALITY_20261030.md) for the active dataset audit
and scale-up gates.
