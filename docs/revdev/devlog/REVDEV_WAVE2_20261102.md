# Revdev wave 2: seven hackathon backend slices (2026-11-02)

Follows [REVDEV_WAVE1_20261102.md](REVDEV_WAVE1_20261102.md). Recipe rules:
[RECIPE_BRIEF_WAVE2.md](../RECIPE_BRIEF_WAVE2.md). New rules agreed with the
user before this wave:

- `by llm` functions stay in the slice and are tested with `MockLLM`, injected
  by patching the defining module (`m.llm = MockLLM(...)`); the teacher
  PROTOCOL says the same.
- Python: a repo whose Python lines exceed 30% of its Jac lines is dropped; a
  slice may carry at most 100 lines of Python helpers. Claimora and DepGraph
  (both 42%) were removed from `accepted` for this; 11 of 19 wave-2 candidates
  were dropped (45-411%).
- Upstream clone files are the source; jac-data-gen repairs are used only when
  the upstream file fails 0.36.1 check. Edits are deletion-only, plus the
  `byllm` -> `jaclang.byllm` import path and `.sv.jac` -> `.jac` renames.

## Outcome

| Slug | Source | `by llm` | Result | Teacher calls | Cost |
| --- | --- | ---: | --- | ---: | ---: |
| nourish_backend | Viktor-Nedev/Nourish | 0 | accepted | 11 | $1.57 |
| umadeit_backend | UMadeIt (Ann Arbor) | 4 | accepted | 17 | $2.82 |
| agewise_backend | Anay162/agewise | 2 | accepted | 23 | $3.16 |
| campussync_backend | CampusSync (Ann Arbor) | 0 | accepted | 22 | $5.21 |
| unibank_backend | Uni-bank (JacHack 2026) | 0 | accepted | 16 | $2.86 |
| flair_backend | Flair (JacHack Spring) | 1 | v1 tool crash, v2 accepted | 28 | $7.24 |
| insuraagent_backend | fozagtx/insuraAgent | 5 | v1, v2 rejected; v3 accepted | 96 | $18.36 |

Total 213 teacher calls, $41.21. All seven apps accepted (InsuraAgent on v3). FutureOS has a
recipe but was not run: its backend is one module with no cross-file edge.

Unified `accepted`: 72 -> 97 records. `accepted-dedup`: 97 records, 1,048,137
context tokens, 22 source groups, audit passed
(`output/eval/revdev/wave2-dedup-audit-20261102.json`). Mindcraft is now
about 24% of the serialized message text.

## Failures and fixes

- **Relative `--wave` path.** `wave_run.py` crashed in its log line after the
  first teacher attempt, so retries and gates never ran. The wave path is now
  resolved first.
- **Scaffold guard vs `by llm`.** `dispatch.jac` read every ability body as a
  statement list; a `by llm` declaration's body is a call, so the guard raised
  and the step ended `execution_interrupted` (Flair v1). Such bodies are now
  skipped. Flair was rerun from scratch as v2.
- **Trailing `}` in teacher JSON** (InsuraAgent, twice; DepGraph in wave 1).
  `claude_adapter.py` now parses the first JSON object and ignores trailing
  braces and whitespace only; any other tail still fails.
- **InsuraAgent** failed the same two assertions in both runs: the stored
  letter must be `f"{salutation}\n\n{body}\n\n{closing}"`. v1 dropped empty
  parts; v2 stored only the body. The plan states the format, but inside one
  long `purpose` sentence of the walker row, and both runs passed a context
  checkpoint before writing the walker. Both runs stay rejected. v3 moved the
  letter and `APL-` id contracts into the `task.json` acceptance list (tests
  unchanged, recipe rechecked) and was accepted in 28 steps.

## Next

- `1102-revdev-v135-r16-64k/sft.yaml` now reads `accepted-dedup`.
- FutureOS recipe kept, not run.
- Keep GhostWatch held out for evaluation.
