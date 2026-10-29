# Reverse Development generator: implementation plan

Status: M0–M4 retain the 8-record, five-type Mindcraft pilot. M5 module expansion has 21 accepted real-tool trajectories across 3 repos (14 train / 7 repo-heldout valid); rank16 continuation training and paired evaluation completed, with no measured behavioral improvement. Two different repos now meet the connected two-file behavior gate: A2-Pulse brief_dates → brief_editor (23 original tests, replay equal, 34,733-token valid record) and m-local context_models → context (13 original tests plus independent mixed-state oracle, 18 replayed tool calls, 24,456-token train record). Full-app expansion remains pending. See [scale-up log](revdev/devlog/REVDEV_SCALEUP.md), [A2-Pulse log](revdev/devlog/REVDEV_A2PULSE_TWOFILE.md) and [m-local log](revdev/devlog/REVDEV_MLOCAL_CONTEXT.md). Runtime remains pinned to Jac 0.34.27.
The dataset contract and five preview examples are in [REVDEV.md](REVDEV.md).
The proposed fields and visibility rules for every JSON artifact are in
[REVDEV_ARTIFACTS.md](REVDEV_ARTIFACTS.md).

## Target outcome

One command should take a pinned reference repo and produce a manifest,
validated task/plan, a real JacCoder run from a clean workspace, replayable
checkpoints, and five separate SFT exports (`revdev_plan`,
`revdev_scaffold`, `revdev_function`, `revdev_app`, `revdev_resume`). Every
exported record must fit the configured 64k training-token cap. The reference
repo remains outside the student workspace and harness context.

## Architecture and ownership

The repository convention was first recorded in `docs/CONVENTION.md` at
commit `7394f77` (2026-09-09). Its core dataset layout still matches the
current file: each task producer owns its record shape, uses
`dataset.pipeline` for split/write, keeps the standard SFT `meta` fields,
and writes under `dataset/sft/<task_type>/<DS_NAME>/`. Treat this earlier
convention as the baseline. Use later trajectory code for its actual
tool-call format and harness details where the earlier convention has no
equivalent; do not let a later helper silently redefine the original dataset
layout or record ownership. Keep full JacCoder prompts/schemas in the
gitignored `script/dataset/trajectory/harness/jaccoder.*` location.

Implement under `script/dataset/revdev/`. Reuse
`dataset.parser.repo` for file-selection policy, `utils.jac_cli` for baseline
checks, `dataset.trajectory.common` for raw event rows and redaction, and
`dataset.pipeline`/`dataset.sft.tool_use` for SFT writing and token accounting.
Do not copy their regex symbol index into the authoritative extractor or use
`tool_use.windows` alone to manufacture resume examples.

| Module | Main input → output | Boundary |
| --- | --- | --- |
| `config.py` | CLI/config → pinned repo, compiler, harness, tokenizer, cap and output paths | One immutable run config with fingerprints. |
| `extract.jac` + `extract.py` | Reference repo → compiler-backed JSON manifest | Jac bridge invokes the local compiler; Python orchestration consumes JSON. |
| `tasks.py` | Manifest → grounded user stories, task scope and oracle plan | Evidence stays generator-only; student prompt stays natural. |
| `harness.py` | Run config + clean workspace → actual JacCoder calls/results and file events | Invoke or instrument the real target harness; no hand-written success responses. |
| `checkpoint.py` | Completed response/result boundary → restorable workspace + plan + hashes | Never cut inside a tool batch, edit or result. |
| `segment.py` | Raw run + checkpoints → app prefix and executable resume jobs | Exact target tokenizer and chat template enforce 64k. |
| `validate.py` | Reference, output workspace and raw trace → acceptance/rejection report | Baseline, dependency evidence, schema, replay and final checks. |
| `export.py` | Accepted run → five SFT task types and provenance | Repo-level split; raw run remains available. |

These are proposed module contracts. A module can be combined or split after
the pilot, while preserving the data contracts below.

## Data contracts

1. **`manifest.json`** contains repo ID and commit; compiler/tool versions;
   selected file hashes; file kinds; symbols with kinds, signatures and source
   spans; import edges and resolved symbol-use edges; cycles; unresolved edges;
   baseline command results. Each dependency edge carries its source evidence.
2. **`task.json`** contains task ID, natural user request, scope, target files,
   acceptance flows, a reference-manifest hash and generator-only grounding
   IDs. Source text is not copied into the student-visible request.
3. **`plan.json`** uses the target JacCoder build-plan schema for the entire
   scoped application: file manifest, exports, imports, write order and verify
   flow. It does not include function bodies. `revdev_plan` stores it as the
   assistant target; execution uses the actual `plan_build` output and checks
   that it remains within the grounded task scope.
4. **`run.jsonl`** uses the existing `{meta, rows}` trajectory format, with
   tool calls using the captured target schema and tool results copied from
   actual execution. Run metadata includes source repo/commit, harness build,
   model, workspace ID and task ID. The raw run can exceed 64k; exported SFT
   records cannot.
5. **`checkpoint.json`** records run/segment ID, last completed event ID,
   workspace file hashes, plan hash, environment fingerprint and remaining
   work. The corresponding workspace snapshot is restorable without the
   reference repo. A plan `done` flag is checked against actual file contents;
   it is not sufficient proof that a scaffold has been implemented.
6. **`record.meta`** includes `task_type`, repo split group, task/run/segment
   IDs, token count, checkpoint ID when applicable, validation status and
   provenance hash. The SFT `tools` field is the exact target schema in the
   existing string-encoded format.

## Execution semantics

- The generator extracts the oracle from the reference; the **student-facing
  execution** starts from a clean workspace or the exact JacCoder template.
  The LLM uses actual harness tools to write planned scaffolds in dependency
  order, then implement bodies. All tool results, including auto-check errors,
  are captured from that harness.
- A dependency must be inspected on first use after it exists. Cache the
  observed path/symbol and content version within a segment; re-inspect only
  after an interface change, uncertain file state, new needed symbol or a
  continuation that lacks the earlier observation. Accept any call order that
  satisfies these invariants.
- JacCoder `write_code`/`edit_code` already validate `.jac` writes. Additional
  checks occur at dependency-group or app-level boundaries when they cover a
  distinct risk. The target MainAgent exposes `run_command`, not a standalone
  `jac_check` call in its current tool list.
- The 64k cap counts the rendered system prompt, tool schemas, user/context
  rows, tool results and assistant targets using the training model's pinned
  tokenizer. Default cap: 65,536; target a safe boundary around 60k. If the
  next complete response/result group will not fit, stop after the previous
  group and save a checkpoint. If a single group is too large, reject or
  reduce scope; never truncate a real result to make a record fit.
- Segment 0 is `revdev_app`. Restore the checkpoint and run the actual harness
  with a continuation request for segment 1 (`revdev_resume`); repeat until
  verified or honestly failed. A mere suffix cut from the original chat is
  not a valid resume: it may rely on inaccessible prior context.
- `revdev_scaffold` and `revdev_function` are extracted from accepted,
  replayable portions of this execution. Their context includes all prior
  observations needed for the target response. The planning-only target may
  be derived from the grounded oracle; never label a fabricated planner tool
  result as real JacCoder execution.

## Implementation sequence

### M0 — Compatibility spike

1. Pin the target JacCoder runtime and capture its actual system prompt, tool
   schemas and representative request/response payloads. Compare with the
   historical `trajectory/harness/jaccoder.json`; record differences.
2. Prove a disposable local workspace can invoke **real** `plan_build`,
   `read_file`, `write_code`, `edit_code` and `run_command` through that runtime,
   capture their returned text and restart from a filesystem checkpoint.
3. Test signature-only scaffold forms against that same `write_code` auto-check.
   Choose a valid form or document the dependency-first exception. Confirm
   how the plan marks files `done` after scaffold writes.
4. Render one captured tool response with the target training tokenizer and
   verify the schema, message format and exact token count. The current SFT
   trainer defaults to 4096 (`script/train/sft.py`); a future training recipe
   must explicitly set and support 65,536. This plan does not start training.

**Gate:** if a local harness invocation cannot reproduce the target tool
behavior, stop before bulk generation and choose a supported runtime adapter.

### M1 — Reference manifest

Build the Jac compiler bridge around `CodeIntelligence` plus AST traversal.
Resolve file imports, exported symbols and use sites. Add a small fixture with
two imported modules, an annex, a cycle and an unresolved/dynamic reference.
Compare extracted edges against source locations. Re-run baseline checks for
the first candidate repo; do not trust the dated whitelist alone.

**Gate:** every accepted edge has a source span; unresolved edges are listed;
the candidate has a current baseline result.

### M2 — Grounded task and plan

Generate a natural request from verified feature evidence. Build the complete
plan at architectural granularity, then validate the file manifest, exports,
dependencies and write order against the manifest. Include multiple legitimate
request scopes/wordings over time without changing the hidden ground truth.
Avoid a universal exact string target for plan filenames or topological order;
grade structural validity and grounding.

**Gate:** no reference source enters the user prompt; every planned feature
and file has evidence; no body implementation appears in the plan.

### M3 — Real run and checkpoints

Run one small repo from an empty workspace using the captured harness. Record
all tool calls/results and file hashes. Build all scoped scaffolds in valid
dependency order, then bodies with on-demand dependency inspection. Capture
real failures and corrections. Snapshot only after complete tool results,
including the plan and any generated assets.

**Gate:** tool arguments validate against the captured schema; a replay from
the starting workspace reproduces file states and result statuses; no tool
success has been synthesized.

### M4 — Segmentation and five exports

Count exact chat-template tokens. Export `revdev_app` prefix and execute
`revdev_resume` continuations from checkpoints as needed. Derive planning,
scaffold and function records with proper visible context. Preserve shared
repo split group and provenance. Write rejection reports for over-cap,
unreplayable, ungrounded and unverifiable examples.

**Gate:** every SFT record is at most 65,536 tokens; no call/result pair is
separated; each resume runs from a restorable checkpoint; train/valid have no
repo overlap.

### M5 — Pilot review and expansion

Inspect the first repo's five dataset previews, tool timeline, checkpoint
handoff and final application check. Measure accepted/rejected samples,
duplicate reads, unresolved dependencies, token distribution and verification
outcomes. Only then expand to more repos, prioritizing freshly validated
small apps. Keep full-run and per-segment failure reasons visible.

**Gate:** one pilot can be rebuilt and replayed without the hidden reference
in its workspace, and the resulting app passes the selected checks.

## Next concrete work item

The connected two-file behavior gate is complete: the A2-Pulse brief_dates → brief_editor trajectory passed 23 original tests, independently reran the four date tests, and passed checkpoint replay. See [the execution log](revdev/devlog/REVDEV_A2PULSE_TWOFILE.md). GhostBoard remains compile-only, and Orbitron remains rejected under the current pinned runtime.

The different-repository two-file gate is complete with m-local. Its 13 unchanged tests, reference diagnostic parity, READ access contract, mixed-state oracle and checkpoint replay pass; the first rejected validation and evidence-based repair remain in the same raw trajectory. See [the execution log](revdev/devlog/REVDEV_MLOCAL_CONTEXT.md). Train/valid remain separated by repository.

After that gate, attempt a longer full-app trajectory and implement actual response-boundary checkpoint/resume execution under the 65,536-token SFT cap. Produce separate planning, scaffold, function, app and resume records only when their visible context and execution evidence support them. Expand to several passing repos before another rank-16 SFT and held-out behavioral evaluation. The 0.36.1 migration remains separately tracked in [REVDEV_JACBUILDER_0361.md](revdev/devlog/REVDEV_JACBUILDER_0361.md); Git diff data remains separately scoped in [REVDEV_GIT_DIFF_CANDIDATES.md](revdev/devlog/REVDEV_GIT_DIFF_CANDIDATES.md).
