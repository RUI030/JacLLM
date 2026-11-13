# Real Student debug diversity pilot

Date: 2026-10-30. This is a controlled, local-only JacBuilder experiment using the actual `openai/local` JacLLM Student and pinned Jac 0.34.28. The runner, fixtures, workspace copies, trajectories, and results are retained under `output/jacbuilder_collection/`; no production agent code or training data was changed. Each baseline failed its behavior assertion, and each golden fixture passed before live inference. The live runs referenced those exact preflights.

| Case | Family | Student result | Observed actions after repair | Teacher |
| --- | --- | --- | --- | --- |
| `05_increment_boundary` | arithmetic boundary | `jac check` and `jac run verify.jac` pass | Two failed redundant edits; Supervisor `OBSERVE` twice | Not invoked |
| `07_walker_sum` | Walker state | Both checks pass | Four refused writes to protected `verify.jac`; `OBSERVE` four times | Not invoked |
| `09_toggle_target_only` | list state | Both checks pass | Whole-file rewrite and one refused verifier write | Not invoked |
| `10_placeholder_recovery` | archived context | Both checks pass | Two refused verifier writes and a repeated whole-file write | Not invoked |

The independent verifier ran after Student returned, in its own ownership epoch. All four result files report `student_verified=true`, `teacher_attempted=false`, `blockers=[]`, and `sft_ready=false`. The shadow Supervisor never blocked tool execution. The protected-path refusals demonstrate that permission control remains separate from quality judgments. `OBSERVE` after a successful repair is a legitimate state; repeated refusals alone do not prove task failure.

The `09` Student first requested `read_file(offset=1)` on a one-line source and received no code, but its initial request already contained the original line inside baseline Jac diagnostics. It therefore had some source grounding. The `10` Student did not copy the archived placeholder into code, but added a nonessential `with entry` block to the repaired module. These are reasons for manual target review even when the public assertions pass. The four small synthetic cases do not measure full-app performance or establish a teacher handoff.

An additional disposable replay of the final `09` and `10` sources passed pinned `jac check` and `jac run` for both. The extra `09` checks cover a second-item target, an extra field, input preservation and a missing ID; the extra `10` checks cover all active, all completed and empty lists. Full commands, source hashes and outputs are preserved in `output/jacbuilder_collection/extra-checks-v1/results.json`. These checks improve behavioral confidence but do not approve the nonessential edits as SFT targets.

## Evidence and next gate

The exact commands, preflight fixtures, process metadata, full actor-attributed JSONL trajectories, source files, and checker stdout/stderr are in the four local batches: `logic-pilot-v1/batch-hvjurx6p`, `walker-pilot-v1/batch-nfxytypn`, `app-state-pilot-v1/batch-13mue38a`, and `placeholder-pilot-v1/batch-6fdnk9cv`. Live durations were 39, 48, 66, and 38 seconds respectively. These are successful Student controls, not Teacher demonstrations or approved SFT examples. The existing two-row import-typo dataset remains the only approved debug pilot and is still too narrow for a meaningful improvement claim.

Next, collect naturally failing, more realistic tasks with a separate held-out evaluation family. Accept a Teacher action as a training target only after checking the Student-visible grounding, exact workspace state, independent behavior tests, minimal change scope, and actor labels. Keep raw trajectories immutable and mark derived targets separately. Continue to use the existing MainAgent/byLLM loop and shadow Supervisor; do not enable automatic intervention from these four runs.
