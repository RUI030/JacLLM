# Training recipes

A recipe is one file that describes a training run end-to-end: base model,
adapter, hyperparameters, and how to mix multiple datasets into the training
stream. `train.py` reads the recipe, `mixer.py` builds the mixed HF dataset,
and `run_cpt` / `run_sft` / `run_grpo` in `cpt.py` / `sft.py` / `grpo.py` do
the training.

For a single-dataset run, keep using `cpt.py` / `sft.py` with their own CLI
flags. Recipes exist for the multi-dataset case.

## Running

Activate the project environment before running a recipe. This also ensures
that notebook kernels, Unsloth, TRL, Transformers, and TensorBoard use the
versions installed for this project rather than packages from the base Python
environment.

```bash
mamba activate <ENV_NAME>
which python

python script/train/train.py \
  --recipe script/train/recipe/<RECIPE_NAME>.yaml
```

To keep a copy of the terminal output:

```bash
python script/train/train.py \
  --recipe script/train/recipe/<RECIPE_NAME>.yaml \
  2>&1 | tee <RECIPE_NAME>.log
```

When debugging an environment mismatch, check the active interpreter and
relevant package versions before changing project dependencies:

```bash
which python

python -c '
from importlib.metadata import version
for package in ["unsloth", "transformers", "trl", "tensorboard", "tensorboardX"]:
    try:
        print(package, version(package))
    except Exception as error:
        print(package, "MISSING", error)
'
```

`--adapter` overrides `recipe.adapter`, `--resume` overrides
`recipe.resume_from`. They're mutually exclusive with each other.

### Resume an interrupted run

Training writes a Trainer checkpoint every `hyperparams.save_steps`. These
checkpoints include adapter weights, optimizer and scheduler state, RNG state,
and the current step. The final `adapter/` directory contains model weights
for inference or a fresh training stage; it is not a resumable Trainer
checkpoint.

Pick `save_steps` by how long a step takes, not by a fixed number: one step is `batch_size * grad_acc`
sequences of up to `max_seq_length` tokens. A crash loses at most `save_steps` steps, so aim for
about 1 to 2 hours between checkpoints (rank-64 on Ornith-9B: ~690MB each). Rule of thumb on the 5080:
`max_seq_length` 4096 -> `save_steps` 200, 16384 -> 50 (one 16k step with `grad_acc` 10 is ~115 s). The
setting is read at launch, so changing a recipe does not affect a run that is already going.

Checkpoints are large (a rank-64 LoRA on Qwen3-Coder-30B-A3B is ~15GB each).
Set `hyperparams.save_total_limit: N` to keep only the N newest
`checkpoint-*/` directories; the default keeps all of them.

List the checkpoints for a run:

```bash
find <RUN_DIR> -maxdepth 1 -type d -name 'checkpoint-*' | sort -V
```

Resume from one of them:

```bash
mamba activate <ENV_NAME>

python script/train/train.py --resume <RUN_DIR>/checkpoint-<CHECKPOINT_STEP>
```

Every run keeps the recipe it started from as `<RUN_DIR>/recipe.<ext>`, and
`--resume` rebuilds the run from that copy, not from the file under `recipe/`,
which may have been edited since. Pass `--recipe` to override it on purpose;
that copy is kept beside the original as `recipe.<MM-DD_HH-MM>.<ext>`. Runs
started before this copy existed need `--recipe`.

The model loads from the checkpoint itself, so the LoRA shape (rank, alpha,
rslora, target modules) is whatever the run trained with. A stage stacked on
an earlier adapter (`adapter:` in the recipe, e.g. CPT → SFT) resumes as is:
no `adapter: ""` or `lora_alpha` edits.

Use `--adapter <ADAPTER_DIR>` instead when intentionally starting a new stage
with fresh optimizer and scheduler state. Merge the old adapter into a new
base model first if the new stage needs different LoRA shape parameters such
as rank or target modules.

## Format

Recipes are YAML (`.yaml` / `.yml`) or Python (`.py` — must export
`RECIPE = {...}` at module level). Both parse to the same dict shape.
The schema is strict: unknown keys are rejected instead of silently falling
back to a default. Start from one of the checked-in recipes when creating a
new one.

```yaml
recipe:
  name: base_sft_v1              # used to name output/adapter/<timestamp>-<name>/
  stage: sft                     # cpt | sft | grpo
  base_model: ornith-ai/Ornith-1.5-9B
  adapter: ""                    # optional continue-from adapter path
  hf_repo: ""                    # optional exact repo id; default: <hf_org>/JacLLM-<model-name>
  seed: 3407
  max_seq_length: 4096
  load_in_4bit: true
  text_only: true
  chat_template: qwen-2.5        # sft only

hyperparams:
  epochs: 1
  batch_size: 1
  grad_acc: 10
  lr: 2.0e-4
  lora_rank: 64
  lora_alpha: 16
  # ...any other field in default_config() of cpt.py / sft.py / grpo.py

mixing:
  strategy: interleave           # concat | interleave
  stopping: all_exhausted        # interleave only: first_exhausted | all_exhausted

datasets:
  - task: py2jac                 # required for sft and grpo; ignored for cpt
    name: opus-synth-v2          # str | list | "*" (or omit) for all names under task
    split: train                 # default "train"; can also be a list
    weight: 0.20                 # interleave only
    repeat: 1                    # concat oversampling (default 1)
```

## Dataset resolution

Given `stage=sft`:

| entry | resolves to |
|---|---|
| `task=py2jac, name=opus-synth-v2` | `dataset/sft/py2jac/opus-synth-v2/train.jsonl` |
| `task=osp, name=[Nitin-1k-osp]` | one dir |
| `task=js2jac` (no `name`) | every subdir under `dataset/sft/js2jac/` |
| `split=[train, valid]` | both jsonls concatenated into one HF split |

Missing dataset directories or splits are skipped with a visible warning. If
all requested training data is missing, the run stops before loading a model.

Given `stage=cpt`:

| entry | resolves to |
|---|---|
| `name=Nitin-9k-py2jac-idiom` | `dataset/cpt/Nitin-9k-py2jac-idiom/train.jsonl` |
| no `name` | every subdir under `dataset/cpt/` |

Given `stage=grpo`, an entry is an RL task set, loaded by `rl/task.py` as one
row per task (`prompt`, `task_id`, `task_dir`, `task_type`):

| entry | resolves to |
|---|---|
| `task=functions, name=spike-sample-20, split=train` | tasks listed in `dataset/rl/functions/spike-sample-20/splits/train.txt` |

GRPO has no valid split; evaluate with `script/eval/rl/run_eval.py`.

## GRPO stage

`stage: grpo` accepts the keys below on top of the shared ones (they are
rejected under `cpt`/`sft`). Defaults are in `grpo.py:default_config()`; every
key TRL would otherwise default is set explicitly.

```yaml
recipe:
  stage: grpo
  adapter: output/adapter/0926-v13-A/sft/adapter   # start from an SFT adapter
  enable_thinking: false         # Ornith's template opens <think> unless this is false

hyperparams:
  batch_size: 8                  # completions per micro-batch, NOT prompts
  grad_acc: 2                    # batch_size × grad_acc completions per update, a multiple of num_generations
  lr: 5.0e-6
  max_grad_norm: 1.0
  num_generations: 8             # group size
  temperature: 0.8
  top_p: 1.0                     # also top_k, min_p, repetition_penalty
  max_prompt_length: 1024
  max_completion_length: 512
  beta: 0.0                      # with PEFT the KL reference is the adapter-off base, not the SFT policy
  num_iterations: 1
  loss_type: dapo                # grpo | dapo | bnpo | dr_grpo
  importance_sampling_level: token   # sequence = GSPO
  epsilon: 0.2                   # epsilon_high: null
  scale_rewards: group           # group | batch | none
  mask_truncated_completions: true
  shuffle_dataset: true
  log_completions: false
  reward: functions              # functions | constant (plumbing smoke test)
  grade_workers: 8               # grade_workers × grade_mem_gb must fit in host RAM next to training
  grade_mem_gb: 3                # per-test cgroup (or RSS watchdog) cap
  grade_timeout: 20              # seconds per jac check / jac test
  purge_pg_steps: 5              # wipe jac's embedded postgres every N steps (jac test leaves ~50 MB per sample)
```

Groups per update = `batch_size × grad_acc / num_generations`. Prefer `epochs` over
`max_steps`: one epoch shows every task exactly once, i.e. `n_tasks / groups per update`
steps (14 tasks, 2 groups → 7 steps), so every task gets the same number of updates;
`max_steps` that is not a multiple of that leaves the last epoch partial. A run writes
`rollouts/step_<N>.jsonl` (completion, status, reward, grading ms) and
`rollouts/stats.jsonl` (grading time, status counts, infra-error rate, host
RAM, postgres size) next to its checkpoints. TensorBoard gets
`rewards/functions_reward/*` plus weight-0 metrics `rewards/{compile,format,pass,infra}_rate/mean`,
and TRL's `frac_reward_zero_std`. Run `python script/rl/graders/test_functions.py`
before a run. `recipe/dev/smoke_grpo.yaml` is the 5-step plumbing test.

## Mixing strategies

**concat** — pack all rows into one dataset, then shuffle. `repeat: 2` in a
dataset entry duplicates that dataset K times before concat (poor-man's
weighting). Every row is seen once per epoch × repeat.

**interleave** — at each training step, sample from a dataset according to
`weight` (normalized to a probability). Small datasets loop when
`stopping: all_exhausted` (default). Every `[[datasets]]` entry needs a
positive `weight`.

**sequential** — curriculum: datasets run to completion in the listed order;
rows within each dataset are shuffled with `seed`. The trainer's sampler is
switched to sequential so it doesn't reshuffle the whole mix (HF `Trainer`
defaults to a random sampler). With CPT packing, sequences only mix documents
across a dataset boundary within one 1000-row packing batch.

Rule of thumb: prefer `concat` when dataset sizes are close and you want each
row seen once; use `interleave` to actively control the ratio (e.g., "farm is
2k rows but I want it at 20% of the mix").

## Overrides

Command-line flags override the recipe:

```
--adapter <path>   # continue from adapter (mutex with --resume)
--resume <ckpt>    # resume training state; --recipe optional (mutex with --adapter)
```

## Output

Runs land in `output/adapter/<MM-DD_HH-MM>-<recipe.name>/`. That directory
holds checkpoints, `runs/` (TensorBoard), and `adapter/` (or `merged/` if
`recipe.merge=true`).
