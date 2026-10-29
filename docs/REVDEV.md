# Reverse Development SFT dataset: plan and preview

Status: M0–M4 retain the 8-record, five-type Mindcraft pilot. M5 module expansion has 21 accepted real-tool trajectories across 3 repos (14 train / 7 repo-heldout valid); rank16 continuation training and paired evaluation completed, with no measured behavioral improvement. The two-record smoke covers GhostBoard two-file replay and an A2-Pulse date test (4/4). Two longer connected two-file records now pass original behavior tests and replay: A2-Pulse editor (34,733-token valid) and m-local context (24,456-token train, plus an independent mixed-state oracle). Their splits are separated by repository. See [multifile smoke](revdev/devlog/REVDEV_MULTIFILE_SMOKE.md), [A2-Pulse log](revdev/devlog/REVDEV_A2PULSE_TWOFILE.md), and [m-local log](revdev/devlog/REVDEV_MLOCAL_CONTEXT.md). Full-app expansion remains pending. See [scale-up log](revdev/devlog/REVDEV_SCALEUP.md). Runtime remains pinned to Jac 0.34.27.
Mindcraft passed a Jac 0.34.27 fullstack HTTP/API and JacCoder tool smoke probe;
see [REVDEV_M3_SMOKE.md](revdev/devlog/REVDEV_M3_SMOKE.md). Git history also
yielded one reproducible debugging diff; see
[REVDEV_GIT_DIFF_CANDIDATES.md](revdev/devlog/REVDEV_GIT_DIFF_CANDIDATES.md).
Examples for scaffolding, function implementation and resume below are design
previews, not captured SFT rows. The two real M2 task/plan artifacts and their
limits are documented in [REVDEV_M2.md](revdev/devlog/REVDEV_M2.md).
The isolated JacBuilder 0.36.1 uplift probe found compatibility blockers;
see [REVDEV_JACBUILDER_0361.md](revdev/devlog/REVDEV_JACBUILDER_0361.md). No runtime pins
were changed.
The concrete module contracts, milestones and acceptance gates are in
[REVDEV_IMPLEMENTATION_PLAN.md](REVDEV_IMPLEMENTATION_PLAN.md).
The proposed JSON field contracts are in
[REVDEV_ARTIFACTS.md](REVDEV_ARTIFACTS.md).

## Goal

Use an existing, verified Jac application as hidden ground truth to produce
five separate SFT datasets: planning, scaffolding, dependency-aware function
implementation, complete application construction, and continuation from a
partially built project. Verification is part of the execution trajectories,
not a separate dataset.

The student's initial workspace must not contain the reference repository.
Reference code may guide the offline generator and validate the outcome, but it
must not appear as an unseen tool result or hidden prompt attachment.

## Current architecture

- `dataset/raw/repo/` has 35 repos. `script/dataset/parser/repo.py` currently
  admits 28; `dataset/raw/repo/meta.json` has an older, stricter list of 11.
  Neither count proves an application can be reconstructed or run today.
- `script/dataset/parser/repo.py` and `script/dataset/repo_stats.py` provide
  repo walking, body extraction and statistics. Their regex-based declaration
  and cross-file-reference helpers are useful for comparison, not authoritative
  compiler dependency edges.
- The local Jac compiler checkout at `/home/imrui/Documents/Jaseci/jac` has
  `jac/jaclang/compiler/tools/code_intel.jac` (`CodeIntelligence`: files,
  symbols, signatures, references, entry points, diagnostics) and
  `jac/jaclang/compiler/frontend/parser/frontend.jac` (AST parsing). A complete
  file/function dependency graph is now captured by `extract.jac` and
  `extract.py`, with unresolved edges retained.
- `script/dataset/sft/scaffold2impl.py` and `tool_fim.py` provide partial reuse:
  scaffolds, temporary workspaces, token checks and record writing. They do
  not reconstruct a full application from a clean workspace.
- `script/dataset/trajectory/common.py` defines raw event rows and conversion
  to chat messages; `script/dataset/sft/tool_use.py` handles SFT windowing.
- `script/dataset/trajectory/harness/jaccoder.json` is a historical prompt
  snapshot. M0 captured a live schema and planner prompt in the gitignored
  `script/dataset/trajectory/harness/jaccoder.m0.json`; see
  [REVDEV_M0.md](revdev/devlog/REVDEV_M0.md). `plan_build` itself runs a planner LLM, so
  its output must be captured from a real execution if included in a trajectory.

## Code location

Use `script/dataset/revdev/` for this multi-stage generator:

| Module | Responsibility |
| --- | --- |
| `extract.py` | Compiler-backed manifest: files, symbols, signatures, imports, references, source locations and unresolved dependencies. |
| `tasks.py` | Generate M2 grounded task wording, private evidence and JacCoder-compatible planning targets. |
| `execute.py` | Start a clean workspace, invoke the selected harness tools, and record actual calls, results and file states. |
| `validate.py` | Compare reconstructed output to the reference and run suitable checks with captured exit codes and output. |
| `export.py` | Write separate planning and tool-use SFT sets using existing trajectory and dataset helpers. |

`extract.py` and `tasks.py` are implemented. The later modules remain planned;
their interfaces may change after the first real run.

## Phases and gates

1. **Pilot selection and baseline.** Pin repo commit, Jac version, harness
   version and dependency versions. Re-run source checks/tests. A historical
   `jac check` result alone is not a working-app certificate. Reject or mark
   unsupported when the reference needs unavailable services or assets.
2. **Compiler extraction.** Build a manifest from compiler symbols and AST.
   Record import, type, function-use and entry-point edges with source spans;
   identify cycles and unresolved/dynamic references. Do not silently guess
   an edge from matching text.
3. **Grounded request and plan.** Derive feature claims from the reference and
   map every planned file and function to evidence. The plan covers the whole
   scoped application: file manifest, purposes, exports, imports, dependency
   groups, write order and verification flow. Exact code bodies belong to
   implementation; exact signatures are emitted during scaffolding. Sort
   acyclic file groups leaves first. Keep evidence and source text in
   generator-only metadata.
4. **Clean-room execution.** Start with an empty workspace or the exact target
   harness template. Once the complete plan exists, create the scoped file
   scaffolds via real write tools in dependency order, then implement their
   bodies. The selected JacCoder workflow may require real skill-loading calls
   between `plan_build` and the first write; retain them if they occur. Issue
   only schema-valid tool calls. Capture each real result immediately,
   including errors and auto-validation from write tools.
   Inspect a dependency after it exists and before its first dependent
   implementation call. Reuse that observation in the same trajectory until
   the relevant dependency changes; do not insert repeated reads merely to
   make every function example look self-contained. If a signature-only stub
   cannot pass the real harness check, record the failure and use a valid stub
   or complete the blocking leaf before proceeding; record the plan revision.
5. **Verification and export.** Run appropriate Jac checks, tests and, when
   feasible, an app-level flow. Store stdout, stderr, exit code, command and
   environment fingerprint. Never substitute an expected success message for
   a failed call. Split train/valid by repo; planning and tool-use are separate
   task types. Long implementation runs may be windowed only at response/tool
   result boundaries, preserving required context.

### Inspection and verification policy

- Dependency order is a partial order, not one mandatory inspection script.
  Any actual call order is valid when the referenced definition exists before
  its dependent use and an actual `read_file` or focused symbol lookup of the
  relevant version is visible in the model's context. The assistant's own
  earlier write establishes the target scaffold's exact text, but does not
  replace first-use inspection of a dependency. Evaluate these invariants,
  not whether calls exactly match one recorded sequence.
- Track inspected dependencies by path/symbol and content version. A focused
  `find_symbol` or bounded `read_file` can establish that a definition exists;
  record which real result supplied the evidence. The assistant's own earlier
  `write_code` call can establish the text of the file being edited, so
  re-reading that target is only needed when exact current text is uncertain.
- Re-inspect only when the consumed signature/body changed, the tool reported
  an unexpected edit or failure, a different symbol is needed, or a new SFT
  episode begins without the prior observation in its context. Windows from
  one app run retain their workspace version and prior evidence identifiers.
- In the current JacCoder source, `write_code` and `edit_code` already invoke
  compiler validation for `.jac` files and return its result. A queued later
  write to the same file may defer that check to the final content. Record this
  actual result; do not issue an extra `jac check` after every successful
  write. Resolve reported errors before dependent work.
- At dependency-group or application milestones, run additional checks only
  when they cover a real remaining risk: cross-file imports, `jac test`, build,
  launch or a user-visible flow. Use tools actually exposed by the selected
  harness. The current MainAgent exposes `run_command` and `jac_run`; its
  `jac_check` implementation exists in source but is not in MainAgent's tool
  list. A final `jac check` command, if used, must go through the live
  `run_command` schema and its real result.

## Dataset boundaries

| Dataset / task type | Unit | Student-visible starting state | Target |
| --- | --- | --- | --- |
| `revdev_plan` | One scoped application request | User story, target harness context | Complete grounded implementation plan; no tool calls required. |
| `revdev_scaffold` | One planned file or connected file group | User story, approved plan, files already built earlier in the plan | Import structure and signature-only Jac scaffold. Existing dependencies may be inspected; output uses target write tools if trained as tool-use. |
| `revdev_function` | One function or tightly coupled group | User story, plan, scaffolded workspace with dependency files present | Read the definitions it uses, implement via tool calls, capture write-tool checks and explicit verification. |
| `revdev_app` | First segment of one app attempt, at most 64k training tokens | Clean workspace or exact target template; no reference source | Plan → scaffold → inspect → implement, ending at a real checkpoint or final verification. |
| `revdev_resume` | Each later segment of that run, or another valid unfinished-app checkpoint | Actual partial workspace, saved plan and user request; no reference source | Read plan and relevant files, reconcile real state, continue missing work and eventually verify. |

The first three are separate training mixtures because each teaches a different
transition and can fit shorter contexts. The fourth teaches the long-horizon
workflow from a clean workspace. The fifth teaches handoff and recovery from
partial state. A source repo may provide one plan example, many file
scaffolds, many function examples, one initial app segment and zero or more
resume segments. The raw run remains complete even when its SFT export spans
multiple records. Actual counts depend on filtering and token limits. Split
by repo so these related records never cross train/valid.

### 64k training cap and continuation

- **64k (default 65,536 tokens) is the hard cap for each exported SFT record**,
  including the rendered
  system prompt, tool schemas, user/context messages, tool results and assistant
  targets under the actual training chat template. Aim to stop earlier (for
  example around 60k) so the final response/result pair fits. Count with the
  pinned tokenizer and template, then reject any record over the configured
  cap.
- Choose a checkpoint only after all tool calls in one assistant response have
  their results, preferably after a complete file or dependency group. Do not
  split a tool call from its result or interrupt a file edit. Save the actual
  workspace, plan, harness version, environment and run/segment IDs.
- Export segment 0 as `revdev_app`. Restore that checkpoint and start the
  actual harness again with a continuation request to produce segment 1 as
  `revdev_resume`; repeat as needed. The resume agent must inspect the saved
  plan and relevant files. Its read results are generated by the real tools
  against that snapshot. It does not receive the hidden reference code or an
  invented summary of previous model reasoning.
- A plain suffix cut from the original conversation is **not** a valid resume
  sample: it may depend on context that the resumed model cannot see. Existing
  `sft/tool_use.py` token counting and response-boundary helpers can be reused,
  but resume segments need checkpoint restoration and fresh execution.
- A segment ending before the app is finished is labeled as a continuation,
  not as a completed application. Final success is attributed only to a later
  segment with observed checks. If one atomic response/result group alone
  exceeds 64k, shrink the task or reject it rather than truncating evidence.

For `revdev_resume`, take filesystem and plan snapshots only at actual tool
result boundaries. Prefer checkpoints after a complete file or dependency
group for the first pilot. The JacCoder write tools can mark a plan file
`done` as soon as a scaffold passes its check, so `done` alone cannot prove
the reference implementation is present. Compare plan status, file content
and remaining tasks before admitting a checkpoint. Reject inconsistent states
or preserve the inconsistency as an explicit issue that the continuation must
discover and correct through real tools. Do not present a generator-private
diff against the reference to the student.

The planning target should be complete at the *architecture* level, not a
transcription of every source line. It should name features, files, contracts,
dependencies and checks, while leaving body logic and detailed signatures for
later stages. Generate natural requests with different legitimate scope and
wording from the same verified app; avoid a single fixed request template and
avoid inserting internal file names into the user's voice without reason.
Keep the plan schema stable enough for JacCoder, but do not treat a single
reference path name or one topological ordering as the only valid answer.

Pilot acceptance: one repo passes a fresh reference baseline; extracted edges
have source evidence; the request/plan do not leak hidden source; all tool calls
validate against the captured harness schema; replay reaches the same recorded
tool results; and final reconstructed files pass the selected verification.

## Five example previews (design examples, not generated rows)

All five use `Rui/pm` at reference commit `e93a47f`. Its stored metadata says
23/23 Jac files passed `jac check` under Jac 0.36.1. The M1 pilot freshly ran
`jac check main.jac` under Jac 0.34.27 and it passed with warnings; see
[REVDEV_M1.md](revdev/devlog/REVDEV_M1.md).
The examples deliberately show a small slice of the app. They do not claim
that any reconstructed workspace has passed a check.

### 1. `revdev_plan`: request → implementation plan

**Student input:** “Build a project and task manager where users create nested
projects and tasks, review draft items, and delete tasks.”

**Assistant target (excerpt of the plan JSON):**

```json
{
  "files": [
    {"path": "models/Task.jac", "exports": ["Task"], "imports_from_plan": [], "write_order": 1},
    {"path": "models/Project.jac", "exports": ["Project", "create_root_project"], "imports_from_plan": ["Task"], "write_order": 2},
    {"path": "walkers.jac", "exports": ["delete_task", "approve_task"], "imports_from_plan": ["Project", "Task"], "write_order": 3}
  ],
  "dependency_graph": {
    "models/Project.jac": ["models/Task.jac"],
    "walkers.jac": ["models/Project.jac", "models/Task.jac"]
  },
  "write_order": ["models/Task.jac", "models/Project.jac", "walkers.jac", "...", "main.jac"]
}
```

Stored at `dataset/sft/revdev_plan/<name>/{train,valid}.jsonl` as ordinary
`messages` plus `meta`. The actual plan must fill every required field of the
selected JacCoder plan schema and include all files in scope. The `...` above
marks omitted preview content, not a value to put in a dataset row.

### 2. `revdev_scaffold`: plan → imports and signatures

**Student input:** the complete plan, `models/Task.jac` already scaffolded in
the workspace as an earlier step in the same ordered scaffold pass, and the
instruction to create `models/Project.jac` without its function bodies.

**Assistant target (file preview):**

```jac
import from .Task { Task }

node Project {
    has name: str = "PROJECT_NAME",
        tldr: str = "What's the goal of this project.",
        is_draft: bool = False;

    def:pub create_task(title: str) -> Task { raise NotImplementedError(); }
}

def:pub create_root_project(name: str, tldr: str) -> Project { raise NotImplementedError(); }
def:pub get_projects -> list[Project] { raise NotImplementedError(); }
```

The scaffold captures imports, type fields and signatures from the reference;
`raise NotImplementedError()` is an explicit stub accepted by the pinned Jac
0.34.27 `write_code` auto-check in the M0 probe. A passing scaffold write
already marks that file `done` in JacCoder's plan, so the generator separately
tracks whether bodies have been implemented. A scaffold write that fails the
harness auto-check is recorded as a failure, then repaired or rejected. In
the tool-use variant, the code above is the `content` argument of a real
`write_code` call, not a prose-only response.

### 3. `revdev_function`: signature → inspect dependency → implementation

**Student input:** scaffolded `models/Project.jac`, existing
`models/Task.jac`, and the instruction to implement
`Project.create_task(title: str) -> Task`.

**Required observable order:**

```text
read_file(models/Task.jac)  [first use of this version of Task]
  → inspect Task and the exact methods needed by create_task
use the exact Project.create_task stub kept from the earlier write_code call
edit_code(models/Project.jac, old_string=<exact stub>, new_string=<implementation>)
  → save the real auto-check result; repair if it reports errors
run an additional check only if another risk remains
```

**Implementation from the reference, after those reads:**

```jac
def:pub create_task(title: str) -> Task {
    task = Task(title=title);
    self ++> task;
    try {
        task.update_alias(task.gen_alias(task.get_title()));
    } except Exception as e {
        print(f"[Warn] alias generation failed for task {jid(task)}: {str(e)}");
    }
    print(f"[Create] task {task.get_alias()}, parent is {self.name}");
    return task;
}
```

Stored at `dataset/sft/revdev_function/<name>/{train,valid}.jsonl` with
`messages`, exact harness `tools`, and metadata linking every inspected symbol
to the reference. The actual `tool_result` content is captured at execution;
the arrow descriptions here are not fabricated results. If the Task definition
was already inspected earlier in the same app trajectory and has not changed,
the function episode must retain that earlier observation as context instead
of issuing a duplicate read.

### 4. `revdev_app`: first segment from a clean workspace

**Student input:** the same user request and an empty workspace or the exact
JacCoder template, with no reference files. **Assistant target:** one ordered
trajectory that calls the real `plan_build` (if using JacCoder), writes all
scoped scaffolds in dependency order, inspects dependencies on demand, and
fills bodies until either the app is verified or the next safe checkpoint is
reached before 64k tokens. Raw data uses
`dataset/raw/trajectory/revdev-<name>.jsonl` with `meta` and ordered `rows`;
converted SFT lives under `dataset/sft/revdev_app/<name>/`. An unfinished first
segment records its checkpoint ID and continuation status, with no fabricated
final success reply.

This fourth dataset cannot be assembled by concatenating unrelated examples
from the first three: every tool call and result must belong to one replayable
execution of the clean workspace.

### 5. `revdev_resume`: partial project → inspect and continue

**Student input:** “Continue building the project and task manager according
to the existing plan.” The workspace is a snapshot from a real build after
`models/Task.jac` and `models/Project.jac` are complete, while `walkers.jac`
and UI files remain pending. It contains `.jaccoder/build_plan.json` and the
files written so far; it does not contain the reference checkout. This
checkpoint may be where the first segment approached 64k tokens.

**Assistant target (observable sequence; exact results captured at runtime):**

```text
read_file(.jaccoder/build_plan.json)
list_files(.)
read_file(models/Project.jac)     [inspect the existing API needed by walkers]
read_file(models/Task.jac)        [inspect the Task API needed by walkers]
write_code(walkers.jac, <complete content from the planned contracts>)
... continue remaining planned files and verify the final app ...
```

Stored at `dataset/sft/revdev_resume/<name>/{train,valid}.jsonl` as a tool-use
record with a checkpoint ID, source run ID, workspace file hashes, plan hash,
remaining task IDs and actual call/result rows. On replay, restoring that
checkpoint and applying the recorded calls must reproduce the recorded
results. If the plan's `done` flags disagree with the files, the model must
observe and resolve that disagreement; the generator must never silently
claim the project is more complete than its snapshot shows.

## Decisions before implementation

- Target the deployed JacCoder runtime by default; capture its actual system
  prompt and tool schemas. If a fixed local runtime is the target instead,
  pin that version explicitly.
- Begin with one small repo selected after fresh baseline checks. Expand to
  other repos only after the pilot passes replay and verification.
- Keep the offline oracle manifest private to the generator. A plan that the
  student is meant to see must be emitted as assistant output or a genuine
  harness tool result, never injected as invisible ground-truth context.
