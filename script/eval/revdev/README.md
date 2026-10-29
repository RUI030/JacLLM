# Revdev paired behavioral pilot

`compare.py` compares a trajectory base and its revdev adapter using identical frozen
prompts, greedy decoding (thinking disabled, repetition penalty 1.05), 16k context
without truncation, and at most 1,024 output tokens per turn. Uses shared
`utils.model.load_model`, the captured JacCoder schemas, real `dispatch.jac`, and
`utils.jac_cli`. Run models in separate processes to release VRAM.

Prepare before either model runs:

```bash
python script/eval/revdev/compare.py --out output/eval/revdev/1029-r16-v2 --prepare
python script/eval/revdev/compare.py --out output/eval/revdev/1029-r16-v2 --model output/model/JacLLM-SFT-Ornith-9B-trajectory-bf16 --tag before
python script/eval/revdev/compare.py --out output/eval/revdev/1029-r16-v2 --model output/adapter/1029-revdev-r16/sft/adapter --tag after
```

Wrap each command with `script/utils/resource_watch.py` as in the dev log. Preparation
executes the seed reads through actual tools, saves their results, and preflights both
fixture oracles. Oracle code and tests used for grading are evaluator-owned. Model
prompts receive tasks, paths and visible source/test files, not oracle bodies.

## Criteria fixed before inference

Six next-action probes (one generation each, no execution of model outputs):

- unseen dependency: read `rates.jac` before implementation;
- cached reads: edit/write `invoice.jac`, avoiding redundant reads;
- stale dependency: refresh `rates.jac`;
- resume: read the saved plan or target source (either order allowed);
- verification: execute `jac test`, not merely claim success or repeat syntax check;
- scaffolding: write the missing `report.jac` with a stub, before implementation.

Schema validity is separate from action correctness. These are instruction-following
probes, not complete dependency policy verification. Scaffold rubric also requires
manual review of imports/signature; automated stub-string score alone is insufficient.

Two planning prompts (library loans and pantry): manually grade each of five binary
criteria using the saved raw output: (1) covers requested operations/constraints,
(2) concrete coherent file responsibilities, (3) public signatures/interfaces,
(4) explicit dependencies and scaffold/implementation ordering, (5) concrete behavior
tests. A capped output is reported as capped; no imagined continuation gets credit.
Plans are not executed, so this does not establish that their APIs compile.

Two live implementation tasks (invoice and greeting): maximum six assistant turns,
real JacCoder dispatch; record schema/execution errors, inspect target and dependency
before first write, read counts, and whether the agent runs tests. Independently test
the final target in a fresh directory with the original dependency/test restored,
so editing visible tests cannot produce a false pass. Checks are deterministic,
small functional checks; they do not establish full application correctness.

New custom tasks are not sampled from a held-out repository benchmark. They were
written after training and are structurally related to desired behaviors. They were
not used for tuning this adapter, but cannot establish statistical generalization.
The two SFT records were a planning projection and a repair projection; scaffold,
app and resume exports were not included in this training run.

## Supplement: explicit contract and error feedback

After the first paired run exposed command-policy rejections, repeat only the two
live tasks for **both** models using `--feedback-rollouts --tag before-feedback`
and `--feedback-rollouts --tag after-feedback`. The system prompt now states the
exact command allowlist. Real adapter validation errors are returned as tool results,
so a model can recover within the same six-turn budget. Keep the first run's outputs;
report this supplement separately, not as a replacement selected for a higher score.

The field `schema_valid` in the initial report includes both JSON-schema checks and
adapter path/command policy. Report JSON-schema-only validity separately when analyzing
results; a policy denial is not necessarily malformed tool arguments.
