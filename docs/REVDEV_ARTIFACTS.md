# Reverse Development JSON artifact contract

Status: schema proposal, version `1`; the M1 private reference manifest has
an initial implementation, while the task/run/export artifacts remain
proposals. See [REVDEV_M1.md](revdev/devlog/REVDEV_M1.md) for the measured pilot. See
[REVDEV.md](REVDEV.md) for the five dataset examples and
[REVDEV_IMPLEMENTATION_PLAN.md](REVDEV_IMPLEMENTATION_PLAN.md) for milestones.

## Layout and visibility

```text
dataset/raw/revdev/<reference_id>/<task_id>/
  private/reference_manifest.json    # generator and validator only
  private/oracle_plan.json           # generator and validator only
  visible/task.json                 # allowed student-facing request/context
  runs/<run_id>/trajectory.jsonl    # exact model-visible event sequence
  runs/<run_id>/execution.jsonl     # tool audit sidecar, never model context
  runs/<run_id>/checkpoints/<id>/checkpoint.json
  runs/<run_id>/checkpoints/<id>/workspace/  # real filesystem snapshot
  runs/<run_id>/verification.json
  export_manifest.json              # links accepted SFT records and splits
```

The live JacCoder plan stays at `.jaccoder/build_plan.json` inside a run or
checkpoint workspace. Do not overwrite it with `private/oracle_plan.json` or
pretend the oracle plan was returned by `plan_build`. The exporter uses a
field allowlist; it never serializes `private/` content into a user prompt,
tool result or resume snapshot. A plan may appear in student context only when
the assistant produced it or a real tool exposed the workspace file.

Use POSIX relative paths within a repo/workspace. Content hashes use SHA-256
of exact bytes; timestamps use UTC ISO 8601 and are never identity keys. Each
artifact header has `schema_version: "1"` (inside `meta` for trajectory and
SFT JSONL rows); every record has stable IDs derived from pinned inputs, not
a local absolute path. Null means genuinely unknown;
absence means the field does not apply. Do not use empty strings or zero to
stand in for missing executions or token counts.

## `private/reference_manifest.json`

One immutable extraction of the pinned source repository. The AST/compiler is
authoritative for Jac syntax and resolved symbols; uncertain edges are listed
under `unresolved_dependencies` instead of guessed.

| Required field | Type | Meaning |
| --- | --- | --- |
| `reference` | object | `reference_id`, repo key, origin, commit, tree hash, local modifications, license/source metadata when known. |
| `toolchain` | object | Jac/compiler version and checkout commit, extractor version, parser mode. |
| `files` | array | Selected source files: relative path, SHA-256, language/kind, size and selection reason. |
| `excluded_paths` | array | Filtered files and pruned generated/dependency directory roots with reasons; generated trees are not enumerated. |
| `symbols` | array | Stable symbol ID, file, kind, name, signature, visibility, source span; optional archetype fields and entry-point role. |
| `dependencies` | array | From/to file or symbol IDs, edge kind (`import`, `type`, `call`, `visit`, `asset`, etc.), source span, resolution and confidence. |
| `unresolved_dependencies` | array | Source span, expression, reason and what would be needed to resolve it. |
| `cycles` | array | Strongly connected file/symbol groups for scaffold planning. |
| `baseline` | object | Fresh source check/test execution IDs; `state` is `pending`, `passed`, `failed` or `unavailable`. |

For example, the existing `Rui/pm` source has `models/Project.jac` importing
`Task` from `models/Task.jac`. A manifest edge would point from that import's
source span to the `Task` symbol ID. This is source evidence; it is not shown
to the student as an unexplained tool result.

## `visible/task.json` and `private/oracle_plan.json`

`visible/task.json` is the only generator-authored task material allowed in the
initial student prompt. Required fields: `schema_version`, `task_id`,
`reference_id`, `request`, `workspace_kind` (`empty` or pinned template),
`acceptance` (user-visible flows), and `constraints` (only facts a real user
could reasonably supply). Optional `assets_provided` lists assets explicitly
placed in the workspace. It contains no source code, hidden tests or oracle
symbol IDs.
`reference_id` here is an opaque key; the actual repo URL, commit and tree
hash stay in private provenance. The prompt renderer normally presents the
request and allowed context, not the artifact's bookkeeping fields.

`private/oracle_plan.json` is the checked target for `revdev_plan` and the
grounding validator for real runs. Required fields: `schema_version`,
`task_id`, `plan_schema` (target JacCoder plan version), `scope`, `features`,
`files`, `dependency_graph`, `write_order`, `verification`, and `evidence`.
Each file entry has path, purpose/layer, exports, imported symbols, planned
signatures or signature references, dependency group, and source evidence IDs.
The **student-facing planning answer** follows the actual JacCoder
`build_plan.json` schema. Private `evidence` and oracle-only references are
stripped from that answer. The architecture plan may specify contracts but
does not contain function body code.

Actual M2 pilot task/plan excerpt (the full private artifacts are under
`dataset/raw/revdev/Rui_pm/m2/rui_pm_core_a/`):

```json
{
  "task": {"task_id": "rui_pm_core_a", "request": "Build a project and task manager for individual accounts. Let people sign up and log in, create projects with a name and goal, open a project to add subprojects and tasks, and browse their projects and tasks."},
  "plan_excerpt": {"write_order": ["services/pm.jac", "components/LoginPage.jac", "components/HomePage.jac", "components/ProjectPage.jac", "main.jac"], "dependency_graph": {"components/ProjectPage.jac": ["services/pm.jac"], "main.jac": ["components/LoginPage.jac", "components/HomePage.jac", "components/ProjectPage.jac"]}}
}
```

The real files are separate JSON objects; this combined snippet only shows
how their IDs and content relate. `main.jac` has additional UI dependencies
omitted from the excerpt.

## `runs/<run_id>/trajectory.jsonl` and `execution.jsonl`

`trajectory.jsonl` uses the existing `dataset.trajectory.common` shape:
`{"meta": {...}, "rows": [...]}`. One logical run can have segments, each with
`schema_version`, `run_id`, `segment_index`, `task_id`, `harness`, `model`, `harness_schema_hash`,
`starting_checkpoint_id` (null for segment 0), and `ending_checkpoint_id`.
Rows preserve observed order and the existing `role`/`mode` contract. Tool
calls use the target harness's actual name and argument keys; tool results
contain exactly what the model saw, including failure text. No private
reference content is added to `meta` or rows.

`execution.jsonl` is an audit sidecar keyed by event/call ID. Required fields
for each executed call: `schema_version`, `call_id`, `tool_name`, `args_hash`, `started_at`,
`ended_at`, `outcome` (`ok`, `error`, `denied`, `timeout`, `missing`),
`model_visible_result_sha256`, `workspace_before_hash`,
`workspace_after_hash`, and optional native exit code, stdout/stderr hashes,
runtime diagnostic IDs and approval status. The model-visible result belongs
in `trajectory.jsonl`; audit fields must not be synthesized if the runtime
does not expose them.

## `checkpoint.json`

Only create a checkpoint after every call in an assistant response has a
result. Required fields: `checkpoint_id`, `run_id`, `after_event_id`,
`segment_index`, `workspace_snapshot`, `workspace_tree_sha256`,
`files` (path and hash), `plan_path`, `plan_sha256`, `plan_consistency`,
`completed_work`, `remaining_work`, `environment_fingerprint`,
`harness_schema_hash`, and `reference_id` for private provenance. `plan_consistency`
records any mismatch between plan `done` flags and real file completion;
`done` alone is never accepted as proof of implementation.

The snapshot contains only the state a real continuing agent can access:
workspace files, visible plan and allowed assets. Restore it into a new
workspace before executing a `revdev_resume` segment. Its metadata can stay
private; the model learns state by reading the restored files with real tools.

## `verification.json`

Required fields: `reference_id`, `task_id`, `run_id`, `baseline_status`,
`reconstruction_status`, `checks`, `acceptance_flows`, `file_comparison`,
`replay`, `rejection_reasons`. Each `checks` item has `check_id`, `phase`
(`reference`, `scaffold`, `group`, `final`), command/tool, cwd relative to its
workspace, exit code if available, outcome, stdout/stderr or captured output
hashes, duration and environment fingerprint. A check's `state` can be
`pending`, `passed`, `failed`, `skipped` or `unavailable`; only observed checks
may be `passed`. File comparison reports exact matches and accepted semantic
differences separately. Final acceptance requires the selected executable
checks, not byte equality alone.

## `export_manifest.json` and SFT records

`export_manifest.json` records `reference_id`, `task_id`, accepted run IDs,
schema/tool/tokenizer hashes, configured token cap, dataset counts by task
type, rejection counts by reason, train/valid split group, and the IDs/paths of
exported records. This is the audit index, not model input.

Each SFT JSONL record contains:

```json
{
  "messages": [],
  "tools": "<exact target tools JSON; omitted for planning-only records>",
  "meta": {
    "schema_version": "1",
    "sample_id": "<stable ID>",
    "task_type": "revdev_function",
    "reference_id": "<repo@commit ID>",
    "task_id": "<task ID>",
    "run_id": "<real run ID>",
    "segment_index": 1,
    "checkpoint_id": "<checkpoint ID or null>",
    "split_group": "<repo identity>",
    "tokens": 0,
    "validation_state": "<observed state>"
  }
}
```

This is a field preview, **not a valid generated training sample**: empty
`messages`, placeholder IDs and `tokens: 0` are shown only to name fields.
The exporter must write populated records and count exact rendered tokens.
`revdev_plan` has no `tools`; the other four datasets carry the real target
schema. `revdev_resume` also records the restored checkpoint ID and
continuation prompt. Records from one repo share a split group and never span
train and validation.

## Validation rules for the first implementation

1. Validate these objects with explicit schema checks before export; reject
   unknown `schema_version`, missing required fields and dangling IDs.
2. Check `dependency_graph` against manifest symbol/file IDs; validate
   topological order or declared cycle groups.
3. Ensure every tool call matches the pinned target schema and every tool
   result pairs with a call. Check execution sidecar hashes against the
   model-visible results and checkpoint file hashes against disk.
4. Render every SFT record with the pinned tokenizer and chat template;
   enforce the configured 65,536-token default cap on the actual tokenized
   result, not a character estimate.
5. Scan visible artifacts for forbidden reference paths, oracle-only evidence
   and hidden test contents. Preserve genuine errors and missing values.
