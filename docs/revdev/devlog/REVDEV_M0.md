# Reverse Development M0: local harness compatibility

Status: local compatibility spike passed on 2026-10-27. This is a probe of the
checked-out JacBuilder runtime, not proof that a remote JacHammer deployment
has the same build. No dataset examples were generated in M0.

Repository convention was checked against the first `docs/CONVENTION.md`
revision (`7394f77`, 2026-09-09) as well as the current file. The original
producer shape, `dataset/sft/<task_type>/<DS_NAME>/` output layout, standard
SFT `meta` keys and shared `dataset.pipeline` remain the baseline for M1–M4.
Later trajectory code supplies the tool-event format because the original
convention did not cover tool-use records. Git commit author metadata alone
does not identify which lines were drafted by a person or an assistant.

## Runtime and evidence

- JacBuilder commit: `0ef5cd23`; project Jac pin: `0.34.27`. The global `jac`
  executable is `0.36.1`, so the probe used the downloaded 0.34.27 binary.
- [m0_capture.jac](../../../script/dataset/revdev/m0_capture.jac) ran with a
  deterministic MockLLM and actual JacCoder functions. Its captured first
  MainAgent request, complete tool schemas, one byLLM `dispatch_batch` result,
  direct tool returns and scaffold statuses are in the local-only,
  gitignored `script/dataset/trajectory/harness/jaccoder.m0.json`. The full
  prompt and schemas must not be committed, per the existing trajectory
  harness convention.
- The existing `plan_build_file_checks.jac` passed (five tests), including a
  real planner `write_code` call. The M0 probe also captured a successful
  `plan_build` return and confirmed `.jaccoder/build_plan.json` exists.
- The existing `recorder_verify_checks.jac` passed: interception of
  `BaseLLM.dispatch_batch` retained a large complete argument and returned
  text. That test truncates the result to 4,000 characters for its own
  assertion; the M0 capture does not truncate it. M3 must likewise retain the
  entire result.

## Snapshot comparison

The historical `script/dataset/trajectory/harness/jaccoder.json` has 25
tools. The live byLLM request has 27: the same 25 plus `mcp_call` and the
injected `finish_tool`. All 25 shared tool descriptions differ. Two shared
parameter schemas differ in descriptions (`clarify_intent`, `preview_status`),
although their parameter names and required lists are the same. The live
system message is 39,833 characters; the snapshot is 39,931 characters. The
live message includes a byLLM instruction prefix and also differs after that
prefix. M3 should capture each run's request schema from the pinned runtime;
the historical JSON is not a valid source of truth for new trajectories.

## Real tool behavior

The probe ran in a fresh `/tmp` workspace with JacCoder's sandbox root set to
that workspace. It captured these exact responses:

| Call | Captured result |
| --- | --- |
| `write_code(main.jac, ...)` | `OK: main.jac (3 lines)` |
| `read_file(main.jac, 0, 20)` | Numbered source lines 1–3 |
| `edit_code(main.jac, "Tasks", "My tasks")` | `OK: main.jac (1 edit)` |
| `run_command("pwd", workspace, 10, False)` | The disposable workspace path |
| `plan_build("Build a small task tracker")` | Reports the written plan path and write order; the plan file exists |

The `write_code` call also ran through MainAgent's actual byLLM tool dispatcher.
The recorded tool message has `role=tool`, `name=write_code`, and the exact
`OK: main.jac (3 lines)` content. The MockLLM emits an empty tool call ID, so
the probe does not establish how a real provider assigns IDs.

Scaffold behavior under the same 0.34.27 `write_code` path:

| Form | Auto-check result | Plan status |
| --- | --- | --- |
| `def title() -> str;` | Passed | `done` |
| `def title() -> str { ... }` | Syntax error: missing `;` | `todo` |
| `def title() -> str { raise NotImplementedError(); }` | Passed | `done` |

The declaration-only form and explicit raise both pass the harness check, yet
neither provides a working body. This confirms the artifact design's separate
`scaffolded` and `implemented` states. A plan `done` flag only means the latest
write passed JacCoder's check. The scaffold preview in `REVDEV.md` now uses the
accepted explicit raise form.

## Checkpoint and token probe

The five files in the workspace (four `.jac` files and the plan) were copied
to a second directory and matched by SHA-256. A separate Jac process then
set its sandbox root to the restored directory, read the edited `main.jac`,
ran `pwd`, and parsed the plan successfully. See
[m0_restore.jac](../../../script/dataset/revdev/m0_restore.jac). This proves the
basic filesystem handoff; M3 still needs checkpoint metadata, environment
fingerprints and a full resumed build.

[m0_token_probe.py](../../../script/dataset/revdev/m0_token_probe.py) rendered a
five-message representative exchange with the SFT default tokenizer
`ornith-ai/Ornith-1.5-9B`: 15,733 tokens, including the live system message,
all 27 schemas, a write call and its actual result text. The script constructs
the assistant tool-call wrapper for this rendering check; it is not an
exported training trajectory. The current trainer default is 4,096 tokens,
so the future 65,536-token recipe must set `max_seq_length` explicitly and
be validated on the training machine.

## M1 handoff

Use the pinned 0.34.27 runtime for the first extractor fixture. Keep the
captured live schema as a compatibility test fixture, but record actual
request schemas and complete dispatch results per run. Treat a successful
scaffold check as syntax evidence only. Before bulk generation, confirm the
remote target harness build matches this local commit or run the probe against
that exact build.
