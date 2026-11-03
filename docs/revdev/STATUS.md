# Reverse Development dataset: current status

Updated 2026-11-02. This is the short handoff for the next work session;
the design and evidence remain in `REVDEV_IMPLEMENTATION_PLAN.md` and
`revdev/devlog/`.

## Goal and current boundary

Generate grounded, real JacCoder tool trajectories from reference repos:
request -> Markdown plan -> all-file scaffold -> dependency-aware implementation
-> checks -> working app. Preserve actual failures and results. Keep the
reference outside the student workspace, and keep each training example within
64k tokens. All accepted stages of one source app go into the single revdev
train dataset; evaluate on other, unseen apps.

The generator, Jac AST extraction, checkpoint/resume, real harness adapter,
clean-workspace replay, independent acceptance, browser checks, stage
projections, one-dataset assembly, and SFT audit all exist. This proves technical feasibility, not
reliable bulk production or model improvement.

## Verified data and outcomes

| Scope | Verified result | Training status |
| --- | --- | --- |
| Active `dataset/sft/revdev/accepted` | 53 non-mirror train records, 560,416 context tokens, quality audit passed | One dataset; `meta.stage` distinguishes stages; no `valid.jsonl` |
| Historical M5 module scale-up | 21 accepted trajectories across 3 repos; formerly 14 train, 7 repo-heldout valid | Earlier rank-16 continuation trained only its old train subset; fixed probe showed no measured behavioral improvement |
| Connected two-file tasks | A2-Pulse and m-local passed replay and original/independent behavior checks | Accepted examples within existing active data |
| Mindcraft full-app continuation | Checkpoint, clean replay, browser behavior and independent acceptance passed | Isolated raw preview; not another independent repo |
| A2-Pulse Jac 0.36.1 week-planner pilot | 37 real JacCoder calls replayed; original tests, `jac build`, browser weekday/weekend flows passed; `accepted` | Four stage rows in unified train; historical 16k mirrors excluded |
| Rui/pomodoro backend slice | 19 real JacCoder calls replayed; original behavior acceptance 3/3 passed; `accepted` | Four stage rows in unified train; mirrors excluded |
| Orbitron fleet UI slice | 38 real JacCoder calls replayed; source and generated browser flows passed the same filter spec; `accepted` | Six stage rows in unified train; mirrors excluded |
| JacProjectFactory paper-library backend slice | 32 real JacCoder calls replayed; source-derived behavior acceptance 5/5; `accepted` | Three stage rows in unified train; mirrors excluded |
| ClaudeLogViewer core parser slice | 18 real JacCoder calls replayed; source-derived behavior acceptance 3/3; `accepted` | Three stage rows in unified train; mirrors excluded |
| Rui/pm | Raw teacher trajectories and independent source-derived checks retained | Pending clean replay and final gate; not active SFT |

The reusable 64k rank-16 training recipe is
`script/train/recipe/1102-revdev-v135-r16-64k/sft.yaml`. It starts a fresh
rank-16 LoRA on the merged v1.35 bf16 weights and loads the
single 53-row dataset (560,416 context tokens; 115,513 exact assistant
loss-bearing tokens under the current trainer mask; longest 52,697) and has
not been trained yet. The former stage directories and 16k mirrors were moved
to `archived/revdev-stage-exports-20261102/` as historical evidence, not
training inputs. New exports update the unified dataset directly.
Here "16k mirrors" means exact duplicate copies of records already at most
16,384 tokens, created for an older 16k training recipe. All 16 copies match
their originals' messages and tool schemas. The old 69-row total included
102,964 context tokens from these copies: 663,380 - 102,964 = 560,416 tokens
in the 53-row unified dataset. No unique record was dropped.
The former Aegis and A2-Pulse valid rows are now train rows, so their earlier
heldout results must not be reused to assess a model trained on this dataset.

## Diversity and v1.35 training decision

v1.35 is a Jac CPT+SFT model whose CPT included 28 app repositories, but its
release notes say it was not trained on agent trajectories. The unrun revdev
recipe now starts a fresh rank-16 LoRA on its merged bf16 weights; it does not
load the older r16 adapter built on `trajectory-bf16`. The two local tokenizers
render all 53 current records to identical token IDs, and the v1.35 tokenizer
audit passes the same 64k cap.

The 53 rows cover ten source groups, but only six are first app segments;
many others are stage projections from the same source runs. Mindcraft alone
contributes 237,225 / 560,416 context tokens (42.3%) and 33,320 / 115,513
assistant loss tokens (28.8%). The top three sources contribute 59.2% of loss
tokens. This is enough for a focused pilot on tool-use behavior, not evidence
of broad app-building coverage. Evaluate against a different app absent from
both this dataset and v1.35's earlier training corpora before claiming gain.
Seven of these ten source groups (A2-Pulse, Alongside, GhostBoard, Orbitron,
ClaudeLogViewer, JacProjectFactory, and pomodoro) also appear in v1.35's
`Rui-jacapp-5` CPT corpus and `Rui-jacapp-scaffold` SFT corpus. Their revdev
trajectories can teach tool-use, but outcomes on those same apps would not
measure unseen-app generalization.

The A2-Pulse week planner is a small adaptation of the original app's date
service and fullstack pattern, not a reconstruction of the entire original
A2-Pulse product. No standalone `revdev_function` sample was exported from
this full-app pilot. Its earlier `valid` label was only a historical stage
export policy. It was not a globally unseen-repo evaluation: A2-Pulse also
appears in older `scaffold2impl` and `tool_fim` train data. Its accepted,
non-mirror rows are now train; do not evaluate unseen-app generalization on it.

## Why recent work looked like bug fixing

The A2-Pulse pilot exposed four correctness gaps: Jac 0.34.27 needed explicit
client runtime dependencies while 0.36.1 injects them; the adapter advertised
one Jac version while `run_command` could execute another; the old Jac skill
suggested `cl`/`sv` markers removed in 0.36.1; and the SFT exporter could
emit schema-rejected, nonexecuted tool proposals. These were fixed or gated
and the failures remain in raw evidence. A replay attempted inside the
restricted sandbox changed Bun/Jac cache behavior; replay in the teacher's
execution environment passed. None of these fixes by itself increases repo
coverage or proves the student learned the desired behavior.

## Next work, in order

1. Freeze the unified 53-row dataset and train it with the 64k rank-16 recipe
   on the capable machine. Compare against
   the fixed dependency-aware tool-use probe; the previous scale-up increased
   loss tokens without a measured capability gain.
2. Use a genuinely unseen app outside this training dataset for validation.
   Never split one app's stages between train and validation.
3. Before unattended bulk production, make source selection and preflight
   repeatable across the whitelisted pool. Each selected slice still needs
   independent source behavior checks, clean replay, browser evidence when it
   has a UI, and the same 64k/schema audit. PM remains pending those gates.
4. Measure accepted yield, failure taxonomy, dependency reads, and unique
   loss-bearing tokens per source; only then increase the source count.

The 2026-11-01 power interruption removed temporary `/tmp` runtime files but
did not remove accepted raw runs or SFT exports. The Jac 0.34.27 harness binary
was restored into ignored `output/runtime/jac-v0.34.27/` with its official
SHA-256, and all 18 revdev unit tests pass with that pinned binary. The
unified audit is `output/eval/revdev/unified-audit-20261102.json`.
JacProjectFactory's completed raw run passed local replay and was exported.
Rui/pm's fullstack run remains pending browser and replay gates; its backend
restart has no executed tool calls and is not exportable. ClaudeLogViewer's
first teacher attempts preserved sandbox network and harness startup failures.
After the user explicitly authorized sharing its teacher prompt, task, and
plan with Claude, the same external call passed review and the corrected run
passed all local gates. Unattended bulk yield and student capability gain
remain unmeasured. The working tree contains many uncommitted revdev changes
and generated data; review scope before committing or promoting datasets.
The [distribution review](devlog/REVDEV_DISTRIBUTION_REVIEW.md) records the
first-batch candidate matrix and the settings still needing repair.
