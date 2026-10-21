# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

JacLLM is a training workspace for LoRA-tuning LLMs (`ornith-ai/Ornith-1.5-9B`, a Qwen-family VLM wrapper, and `unsloth/Qwen3-Coder-30B-A3B-Instruct`, a MoE model) on the Jac language, built on Unsloth. It is a collection of runnable Python scripts, not an installable package: there is no build step, linter, or test suite. Everything under `script/` needs an NVIDIA GPU and the pinned Unsloth/Transformers/TRL stack, except the dataset producers and `graders/`.

`docs/CONVENTION.md` is the authoritative style and layout guide for all Python under `script/`. Read it before adding or restructuring code.

At the start of a task, grep `docs/` and the READMEs and `PROVENANCE.md` under `script/` for the task's keywords, and read only the matching sections, not whole files. Past pitfalls and their fixes are recorded there, for example the grader memory cap and timeout in `docs/CLOUD_GPU.md` and `script/eval/Nitin-test/PROVENANCE.md`, and staged resume in `script/train/recipe/README.md`. Reuse existing code in `script/utils/`, `train/utils.py` and `dataset/pipeline.py`, and add or extend a helper there when a second caller needs it. New code (e.g. RL) treats `script/eval/Nitin-test/` as reference only: don't import it, copy it or modify it.

## Environment

```bash
bash setup_env.sh [ENV_NAME]     # mamba env, Python 3.12, uv with --torch-backend=auto
TORCH_BACKEND=cu130 bash setup_env.sh jacllm   # CUDA 13.2 drivers: auto picks cu132 and silently installs CPU torch
mamba activate <ENV_NAME>
```

- Pins live in `requirement.txt`. Never pin torch, torchvision, triton, or xformers there; `setup_env.sh` lets uv choose builds that match the GPU.
- The `jac` CLI must be on PATH for eval. `script/utils/jac_cli.py` is the only place that should shell out to `jac`. The pinned version (0.36.1) is not on PyPI; see `docs/CLOUD_GPU.md` for installing it.
- On a rented GPU (RunPod), read `docs/CLOUD_GPU.md` first: what survives a restart, HF token scopes, prefetching weights from the network volume, disk budget.

## Common commands

Run everything from the repo root.

```bash
# Multi-dataset training (preferred): a YAML/py recipe drives the stage, hyperparams and dataset mix
python script/train/train.py --recipe script/train/recipe/<name>.yaml [--adapter <dir>]
python script/train/train.py --resume <run>/checkpoint-N     # recipe comes from <run>/recipe.<ext>
python script/train/train.py --recipe script/train/recipe/dev/smoke_sft.yaml     # smoke test

# Single-dataset training (in-file config block + CLI overrides)
python script/train/cpt.py --ds <ds> [--steps N]
python script/train/sft.py --task js2jac --ds <ds> --epochs 3 --lr 2e-4

# Build a dataset split from dataset/raw/... (edit the Setting block first)
python script/dataset/sft/<task>.py
python script/dataset/cpt/{file,repo}.py

# RL (GRPO) on an RL task set: grader self-test first, then a recipe with stage: grpo
python script/rl/graders/test_functions.py [--workers 8]
python script/train/train.py --recipe script/train/recipe/dev/smoke_grpo.yaml     # 5-step plumbing smoke
python script/train/grpo.py --task functions --ds spike-sample-20 --adapter <sft adapter> --steps N

# RL eval / readiness: n samples per task graded with hidden tests → pass@k, per-task pass counts
python script/eval/rl/run_eval.py --adapter <adapter> --split dev --n-samples 8 --temperature 0.8

# SFT eval: infer + `jac check` gate across EVAL_SET tasks
python script/eval/batch.py --adapter output/adapter/<run>/adapter --limit 100 [--tasks osp] [--checks check,run]
python script/eval/gate.py --pred <predictions.jsonl>

# Function-level test-suite eval (vendored Nitin harness)
python script/eval/Nitin-test/run_eval.py --adapter <adapter> --split dev --limit 20

# Unit tests (plain asserts, no pytest)
python script/eval/Nitin-test/report/test_attribute.py
python script/rl/graders/test_functions.py

tensorboard --logdir output/adapter/<run>/runs
```

`script/eval/README.md` maps each eval task to the command that runs it. `script/eval/Nitin-test/USER_MANUAL.md` covers the full generate → wash_refs → taxonomy → report → plot pipeline.

## Architecture

**Data flow:** `dataset/raw/` (gitignored) → a producer in `script/dataset/{cpt,sft}/` → checked-in `dataset/cpt/<ds>/train.jsonl` or `dataset/sft/<task>/<ds>/{train,valid}.jsonl`, with a `statistic.json` next to each → training → `output/adapter/<MM-DD_HH-MM>-<name>/` (checkpoints, `runs/`, `adapter/`) → eval → `output/eval/<task>/<ds>/<tag>_<stamp>/`.

**Dataset producers** all have the same shape: `# Setting` / `# Functions` / `# Run` banners, a task-specific `build_record()`, then the shared `dataset/pipeline.py` (`load_prompts`, `split_and_write`, `report`). Prompts come from `script/dataset/template/prompt_template.json`. Records are `{"text": ...}` for CPT or `{"messages": [...]}` for SFT. Both carry a standardized `meta` block (`source, format, class, fp`, plus `task_type` for SFT), where `class` comes from `utils/classifier.py`.

**Training:** `cpt.py`, `sft.py` and `grpo.py` each expose `default_config()` and `run_cpt(cfg, train_ds, eval_ds)` / `run_sft(...)` / `run_grpo(...)`. When run as scripts, their `__main__` blocks handle single-dataset runs. `train.py` loads a recipe, `mixer.build_from_recipe()` resolves the dataset entries and mixes them (`concat` / `interleave` / sequential), and then the same runner functions are called in-process, never through a subprocess. The recipe schema is strict: unknown keys are rejected, and it is documented in `script/train/recipe/README.md`. Hyperparameter keys map to `default_config()` fields. Shared training helpers live in `train/utils.py` (`load_trainable` loads the model and adds a LoRA unless one comes with it; `save_adapter` optionally pushes to HF).

**Eval:** backends in `eval/infer/` (`adapter.py` for local HF/Unsloth models, `openrouter.py` for hosted models or any OpenAI-compatible server via `--base-url`, e.g. a local `llama-server` serving a GGUF export) all write `predictions.jsonl` in one schema. `gate.py` scores it along the ladder parse → check → run (it short-circuits at the first failure) and writes `report.json`. `compare/` and `probe/` work on those outputs or on adapter weights, so a new backend only needs to write the same predictions schema. `script/eval/Nitin-test/` is a separate vendored harness that grades against hidden unit tests; see `PROVENANCE.md` there before changing vendored files.

**RL:** `dataset/rl/<task>/<set>/` holds hand-written tasks: `meta.json` holds the harness-only fields (shared ones once, per-task `tasks: {<id>: {entrypoints, difficulty}}`), `tasks/<id>/{request.md, starter.jac}` is model-visible, `tests/<id>/{tests.jac, solution.jac}` is grader-only, `splits/*.txt` assign every id to exactly one split. `rl/task.py` turns a split into rows (`prompt`, `task_id`, `task_dir`, `task_type`); `mixer.py` does this for `stage: grpo`, and `train/grpo.py:run_grpo` runs TRL's (Unsloth-patched) `GRPOTrainer`. `rl/rewards.py` grades each completion once per step (`rl.graders.grade_many`, a thread pool of `jac` subprocesses), logs weight-0 metric rewards (compile/format/pass/infra rate) and writes `rollouts/step_<N>.jsonl` + `rollouts/stats.jsonl`. `rl/harness.py:materialize` requires exactly one ```` ```jac ```` block and rejects `test` blocks and forbidden imports; `rl/graders/functions.py` runs `jac check`, then the hidden tests, reward `0 | passed/total`. `eval/rl/run_eval.py` uses the same grading path. All `jac` calls go through `utils/jac_cli.py` (`execute`: process-group kill on timeout, per-call cgroup memory cap or RSS watchdog; `test`: per-test verdicts; `purge_pg`).

**Model loading:** `utils/model.py:load_model` is the one loader used by inference and eval. It restores `config.architectures` (an Unsloth text-only VLM bug) and merges adapters in RAM, except MoE adapters with LoRA on expert parameters (`target_parameters`), which stay attached because merging them into the 4-bit base silently yields the base model.

## Gotchas

- **`text_only=True` must match between training and loading.** Ornith is a processor-wrapped VLM. If an adapter is trained without `text_only`, its keys include `.language_model.`, they silently fail to match at load time, and eval quietly runs the base model (every checkpoint then shows identical loss). See `docs/DEBUG.md`.
- `--resume` (a `checkpoint-N/` directory with full trainer state) and `--adapter` (weights only, fresh optimizer) are mutually exclusive. `--resume` loads the model from the checkpoint (LoRA shape included) and the recipe from `<run>/recipe.<ext>`. A loaded adapter freezes the LoRA shape (`--rank`, target modules, alpha, rslora). To change the shape, merge first with `script/merge_lora.py` and retrain on the merged base.
- In-training eval (`DO_EVAL`) is off because it OOMs on 16GB. Use `script/eval/probe/cpt_loss.py` or `batch.py` after training. When loading several models in one loop, call `gc.collect()` and `torch.cuda.ipc_collect()`, not just `empty_cache()`.
- With `interleave` + `all_exhausted`, small datasets can be resampled many times (see `docs/CONCERN.md`).
- Never train on `script/eval/Nitin-test/data/**/private/`. It holds the hidden tests and reference solutions.
- Adapters trained in sequence without a merge share the same LoRA subspace (see `SPIKE.md`). Keep this in mind when you interpret multi-stage results.
- **Merging a MoE expert-LoRA adapter into the 4-bit base gives the base model.** On Qwen3-Coder-30B-A3B, `merge_and_unload()` generated exactly like the untrained model; `load_model` keeps these adapters unmerged. For exports (GGUF, deployment), merge into 16-bit with `save_pretrained_merged(..., "merged_16bit")` and check a training prompt still gets the trained answer. See `docs/DEBUG.md`.
- **`mixing.strategy: sequential` relies on `train_sampling="sequential"`** (set by `mixer.py`); HF `Trainer`'s default random sampler would reshuffle the curriculum. Runs before commit `31da523` were effectively concat.
- **`script/train/` is a package.** Train scripts put `script/` on `sys.path` and import `train.utils` / `train.mixer`, so `utils` always means `script/utils/` (the RL modules need `utils.jac_cli` inside a training process).
- **`jac test` leaves about one postgres database per test block per run** (tens of MB per graded sample; `~/.cache/jac/pg/main` once reached 1.1TB). Graders call `jac_cli.purge_pg()` between batches (GRPO: every `purge_pg_steps`), and `jac_cli.start_pg()` afterwards so the shared postmaster starts outside any per-test cgroup scope. Never purge while a `jac` process is running.
- **RL workspaces need the server-codespace `jac.toml`** (`jac_cli.SERVER_TOML`): without it jac 0.36.1 lowers plain functions to native and returns wrong values. Also in 0.36.1, a `lambda` inside a `def` raises `UnboundLocalError` at runtime, so completions that use one fail those tests.
- **TRL 0.24 does not drop `None` rewards**: it `nansum`s across reward functions, so a `None` becomes 0 when any other reward function returns a number. `rl/rewards.py` gives grading crashes (`infra_error`) the group mean instead (advantage 0).
- **Ornith's chat template opens a `<think>` block unless `enable_thinking` is false**, and TRL renders GRPO prompts without template kwargs. `grpo.py` defaults it to false in the in-memory template (matching eval) and restores the native template before saving.
- **GRPO rollouts are slow** (~300 s for 16 completions of ~150 tokens on the 5080, vs ~66 s for 112 via `utils/model.generate_batched`); the log reports the fla/causal-conv1d fast path for Ornith's linear attention as missing. Budget steps from a short timing run.
- **Packed SFT builds labels per conversation** (`sft.py:tokenize_with_assistant_mask`). Don't reintroduce `train_on_responses_only` on packed data: it trains the next conversation's system prompt.
