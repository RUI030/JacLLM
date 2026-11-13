# Live Teacher recovery candidates: replay audit

Date: 2026-10-30. This is an evidence review of archived experiments, not a training export.

## Source and executed checks

`script/dataset/sft/audit_live_teacher_candidates.py` verifies the immutable external snapshot manifest and the exact three-case pilot summary, then reconstructs each pre-edit file from the archived Teacher edit and final source. It uses the existing `utils/jac_cli.py` with pinned Jac 0.34.28 in disposable workspaces. Full commands, exit codes, stdout/stderr and source hashes are saved in the local-only `dataset/sft/jacbuilder/live-teacher-candidate-audit-v1/audit.json`.

| Case | Failure family | Baseline `check/run` | Repaired `check/run/extra` | Candidate Teacher actions |
| --- | --- | --- | --- | --- |
| `off_by_one` | arithmetic boundary | 0 / 1 | 0 / 0 / 0 | read `broken.jac`, replace `x - 1` with `x + 1` |
| `positive_filter` | list filtering | 0 / 1 | 0 / 0 / 0 | read `broken.jac`, replace `>= 0` with `> 0` |
| `walker_accumulation` | graph traversal state | 0 / 1 | 0 / 0 / 0 | read `broken.jac`, replace assignment with accumulation |

Additional inputs exercise negative/zero/large integers, repeated positives and all-zero lists, and a Walker graph containing positive, negative and zero values. The archived Teacher performed one `read_file(offset=0)` before each edit. All three source diffs are unique exact replacements. The Student and Teacher invocation starts expose identical system messages and tool schemas in these three raw episodes.

## Why these are not yet SFT targets

The Student model in this pilot was a scripted failure fixture (`openai/student-slice`), not the actual fine-tuned JacLLM. It repeated a deliberately nonexistent `old_string` three times; its failure behavior must not be mistaken for a measured Student distribution. The Student-visible context before Teacher's first read contains the failed edit observations but not the source contents. Thus the Teacher's **first read** is a plausible recovery action to review; the later edit is grounded by that read and must not be spliced directly after the pre-read Student history. Any derived sequence must preserve that read, its exact observation and actor/provenance labels, mask the scripted Student failures, and use a Student-compatible prompt/tool format.

These three cases still use tiny `broken.jac` fixtures and public checks. They add behavior families to the review queue, but do not establish general app debugging, independent validation, or a 500k-token corpus. No candidate was approved for training here. Reserve distinct task/template families for evaluation before selecting targets.
