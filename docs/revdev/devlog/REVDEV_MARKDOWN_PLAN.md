# Revdev plan: Markdown for the student, JSON for the harness

The previous `revdev_plan` pilot made the assistant output the JacCoder
`.jaccoder/build_plan.json` schema. That reflected the current JacCoder
implementation, but it taught the student to write a machine manifest as its
main engineering plan. The new target is `docs/plan.md`.

The Markdown plan contains the user goal, a Mermaid `flowchart LR` of `.jac`
modules, an explicit provider-to-importer edge for each dependency, separate
frontend and backend `.jac` module lists, Jac module build order, public
interfaces, and verification steps. Configuration and CSS remain support files
for implementation, outside the module graph and lists. The plan describes
module responsibilities without copying reference implementation bodies.
The current grounded layout preview is `output/render/revdev-a2pulse-plan-v4.md`.

The `SYSTEM` and `USER` labels in `script/dataset/render.py` output are SFT
message boundaries. They are not written into `docs/plan.md`.

| Reader | `docs/plan.md` | `.jaccoder/build_plan.json` |
| --- | --- | --- |
| Student/teacher model | Writes and reads it; follows the graph and file order | Hidden by the Markdown adapter |
| JacCoder harness | Can read it as an ordinary file | Reads it for automatic file-progress status and preview/tool bookkeeping |
| Revdev generator/validator | Checks the Mermaid nodes and dependency edges | Keeps a grounded internal manifest for deterministic checks and checkpoint inventory |

For new teacher runs, the adapter seeds the machine manifest as recorded
`bootstrap.json` setup, then requires the teacher to write `docs/plan.md`
before application files. It rejects direct reads and writes of the machine
manifest. Replay seeds the same manifest before executing captured tool calls.
The SFT exporter targets the actual Markdown `write_code` content for
`revdev_plan` and uses a student system prompt without the legacy JSON planner
instructions. Validation requires the Markdown file and checks its grounded
Mermaid graph. The old accepted JSON runs remain unchanged and are still
exported through the legacy path.

The earlier A2-Pulse Markdown preview (`/run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/revdev-render-pre-module-plan-20261030/revdev-a2pulse-plan-v3.md`)
was a deterministic rendering of the grounded recipe with support files in
the module list. Its accepted teacher run is rendered at
`/run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/revdev-render-pre-module-plan-20261030/revdev-a2pulse-markdown-plan.md`:
its Markdown came from an actual `write_code` call. That run created every
planned scaffold file before implementation, passed the original reference
date tests, replayed 26 executed harness calls, and passed Chromium weekday
and weekend previews. The isolated SFT export has one planning, one scaffold,
one app-prefix, and one resume record. The 16k plan/resume copies bring the
audit to six records, 66,948 tokens, with no schema/path/token issues.

The previous accepted JSON examples remain unchanged. The Markdown examples
are still under the run's isolated `export-preview/`, pending a deliberate
training-split update and source-repo leakage check. One invalid compound
command and a repeated check remain visible in the trajectory; no result was
rewritten as a success.

The new module-only format is `markdown_mermaid_v2`; the accepted run above is
`markdown_mermaid_v1` and remains unchanged. The v2 renderer and validator
have unit coverage. The first v2 teacher run stopped after it invented
`styles/global.css` instead of the grounded `styles.css` scaffold path. The
adapter now supplies exact non-Jac support paths separately from the Markdown
module plan, including after checkpoint resume.

The new `claude_teacher_markdown_modules_v2b` run wrote all planned scaffold
paths, then continued after a checkpoint. The original service acceptance
tests and `jac check` passed, and the independent validator reported
`checks_passed_pending_fullstack`. Its `jac build` failed because Vite could
not resolve `@tanstack/react-form`. The grounded `jac.toml` scaffold recipe
omitted that Jac client-runtime dependency and `zod`. After the teacher added
`@tanstack/react-form` at `^0.41.0`, the generated package manifest changed,
but the existing `node_modules` did not; `jac install` was blocked by the
adapter. In an isolated `/tmp` copy, a clean build with
`@tanstack/react-form = "^1.33.0"` and `zod = "^4.3.6"` installed both and
passed `jac build`. The raw run remains unaccepted and unexported; its original
failure results are unchanged. Browser acceptance must still be rerun on a
new real teacher trajectory before v2 can be used for training.

The subsequent `claude_teacher_markdown_modules_v2c` run includes those two
client dependencies in the grounded recipe. The adapter allowed its recorded
`jac install` call after `jac.toml` existed. The teacher's `jac check`,
`jac build`, and 10 Jac tests passed. Independent reference acceptance,
clean-workspace replay (26 executed calls), and Chromium preview of a weekend
and weekday date all passed; `validation.json` is `accepted` with no issues.
The first browser attempt failed because the checker required a
`data-testid="preview"` wrapper that the new UI did not use. The reusable
checker now locates the preview section from `preview-label`; the failed
attempt remains in `browser-attempt-1`, and `browser-final` holds the passing
result. A second browser launch inside the restricted sandbox stalled before
writing evidence; the final run used the existing browser execution route.
The isolated SFT export contains one plan, one scaffold, one app-prefix, and
one resume sample; no function sample met the current export criteria. With
16k copies, the audit found six records, 76,526 tokens, and no issues. These
remain isolated pilot samples, not a multi-repository validation split.

Jac 0.36.1 changes the client dependency contract. In an isolated minimal
web-app with no `[dependencies.npm]` section, `jac build main.jac` generated a
client package manifest containing React, `@tanstack/react-form`, Zod, and
Vite, installed them, and completed the bundle. The original A2-Pulse repo
also declares these packages and uses shadcn, but the smaller week-planner
adaptation does not use shadcn primitives. The 0.34.27 dependency declarations
remain valid evidence for that pinned run; they should not become a general
Jac UI rule. Recipe `plan_md_v4.json` and task `task_md_v4.json` target 0.36.1,
use Jac's automatic client runtime dependencies, and require inferred
placement. The previous v2c source cannot be rebuilt unchanged under 0.36.1
because its explicit `cl {}` placement syntax was removed; a new teacher
trajectory is required before exporting 0.36.1 examples.

The Claude adapter now reads `--jac --version`, rejects a recipe claiming a
different Jac version, records that version in run metadata and checkpoint
context, and passes the target binary to JacCoder `run_command`. For a newer
target, `--harness-jac` can keep JacCoder dispatch on its compatible binary.
An isolated real JacCoder `run_command` with dispatch on 0.34.27 and target
`jac check` on 0.36.1 passed.

That 0.36.1 teacher run is now
`dataset/raw/revdev/A2Pulse/runs/claude_teacher_markdown_modules_jac036_v1b`.
The generated `jac.toml` contains only project and serve settings, with no
manually declared React, TanStack, Zod, Vite, or shadcn packages. The teacher
read a 0.34.27 skill and initially wrote removed `cl`/`sv` markers. Its real
0.36.1 `jac check` rejected them; it corrected the files and passed the check,
9 date-service tests, 3 app-level tests, and `jac build`. One app-level test
initially returned HTTP 500 when JacTestClient built from a temporary base
path; it passed after the teacher set the project base path. The adapter
protocol now explicitly warns about skill/target version mismatches.

Independent reference acceptance passed. Clean-workspace replay passed all
37 executed JacCoder calls and matched final source hashes. The first replay
attempt is retained as `replay-attempt-1.json`: it failed only on build/test
diagnostic comparison when the restricted environment made Jac's global cache
read-only and blocked Bun. The second replay used the teacher execution
environment. Chromium passed the weekend and weekday preview flows with no
page errors. Final `validation.json` is `accepted`, with no issues.

The raw teacher log retains two schema-rejected proposals: an `edit_code`
missing required `replace_all` and a final answer with an extra `output`
field. Neither ran as a harness tool. The shared exporter now omits such
nonexecuted adapter validations from the SFT projection and records their
count in metadata; the later valid decisions and every executed tool result
remain. The isolated export has one plan, one scaffold, one app-prefix, and
one resume sample, plus eligible 16k copies of plan and scaffold. Audit:
six records, 75,077 tokens, zero issues. No standalone function sample met
the current exporter criteria; this is still a single-repository train-only
pilot, not a validation split.

Subsequent distribution review corrected the isolated 0.36.1 export's split:
A2-Pulse was already assigned to valid in active SFT. The train-side preview
above remains as a historical attempt; current `export-preview` is valid-side,
states Jac 0.36.1 in the planning system context, and audits at six records,
75,101 tokens. The active-plus-preview split audit also passes. See
`REVDEV_DISTRIBUTION_REVIEW.md` for the scale gate.

Completed generated logs and traces through October 25 were moved to
`/run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/logs-pre-20261030`.
Its manifest records SHA-256 for 80 verified files (12,659,593 bytes). Five
Git-tracked record files remain under `logs/`.
