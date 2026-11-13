# Revdev wave 1: eight hackathon backend slices (2026-11-02)

First batch run of the full revdev chain over new hackathon repos. Candidate
pool and selection rules: [REVDEV_CANDIDATES_20261102.md](../REVDEV_CANDIDATES_20261102.md).
Recipe rules: [RECIPE_BRIEF_WAVE1.md](../RECIPE_BRIEF_WAVE1.md). LLM-repaired
files from the jac-data-gen sweep count as source (user decision).

## Pipeline

1. Recipe per repo (`script/dataset/revdev/recipes/<slug>/`): backend slice of
   2-5 checked modules with cross-file imports, task, plan, provenance, and a
   source-derived `reference_acceptance.jac` that passes on the original slice.
   Each recipe was re-verified in a fresh directory (source hashes, check, test).
2. `script/dataset/revdev/wave_run.py`: Claude CLI teacher with real JacCoder
   tools (parallel), then `validate.py`, `replay.py`, `validate.py
   --accept-backend` (serial), then `export.py` into
   `dataset/sft/revdev/accepted` (serial). Teacher crashes resume up to three
   times; a crashed step executed no tool and is not exported.
3. `script/dataset/revdev/zero_overlap.py` rebuilds `accepted-dedup`, where
   assistant turns that repeat an earlier row's exact prefix are weight 0.

## Outcome

| Slug | Source | Result | Teacher calls | Cost |
| --- | --- | --- | ---: | ---: |
| trace_backend | pathakanshu/trace (Ann Arbor) | accepted | 25 | $4.34 |
| claimora_backend | debssM/Jac_2026 | accepted | 17 | $2.34 |
| repoghost_backend | Async-Avengers/repoGhost | accepted | 18 | $3.71 |
| depgraph_backend | shaileshdev4/depgraph | accepted | 38 | $7.94 |
| rentora_backend | yousefalwahami/rent_jac | accepted | 32 | $7.35 |
| civicmesh_backend | Anbu-00001/CivicMesh | accepted | 28 | $4.87 |
| careanchor_backend | push-to-production/CareAnchor | v1 rejected, v2 accepted | 52 | $9.33 |
| traceforge_backend | Dhravidk/TraceForge | v1 and v2 rejected | 51 | $14.67 |

Total 261 teacher calls, $54.54. Seven of eight apps accepted.

Unified `accepted`: 53 -> 79 records, 870,161 context tokens, 17 source
groups, audit passed (`output/eval/revdev/wave1-dedup-audit-20261102.json`).
Mindcraft fell from 42% to 27.3% of tokens. Loss-bearing `write_code` turns in
wave-1 rows contain 99 local `import from` lines, against 52 in all earlier
revdev rows.

## Failures and fixes

- **Malformed teacher JSON / CLI timeout.** DepGraph returned an extra `}`;
  one Trace call exceeded the 240 s CLI timeout. `wave_run.py` now resumes.
- **Gate skipped.** The first `wave_run.py` returned the raw status string,
  so finished teachers skipped acceptance. Fixed; affected runs were gated.
- **Tests asserted details the plan never stated** (CareAnchor HTML and dict
  keys; TraceForge fingerprint keys, phase rules, digest sentences). The fix
  added source-derived output contracts to the plan; tests were not changed,
  and the recipe authors did not read generated output. Rule for later waves:
  every value a test asserts must be derivable from task and plan.
- **TraceForge v2** failed one test where the plan states `return sorted` for
  candidate steps. That is a teacher deviation, so the run stays rejected. The
  slice is a keyword-heuristic parser whose v2 plan is 8,975 tokens; such
  slices are poor revdev targets.
- **jac-data-gen repairs.** Some repaired files use `..` relative imports that
  pass `jac check` but fail at runtime ("attempted relative import beyond
  top-level package"). CareAnchor and DepGraph slices restored the upstream
  absolute imports; "green" in that sweep does not mean runnable.

## Next

- Train from `accepted-dedup` (change the recipe dataset `name`).
- Wave 2 from the candidate list, skipping heuristic-heavy slices; keep a
  held-out unseen app (GhostWatch suggested) for evaluation.
