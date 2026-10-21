# JacLLM

JacLLM is a small training workspace for Jac-focused language model work. It currently centers on:

- continual pretraining (CPT) and supervised fine-tuning (SFT) with Unsloth
- recipe-driven multi-dataset training
- adapter evaluation (`jac check` gate, hidden-test harness)
- local adapter inference
- LoRA merge/export
- dataset storage and preprocessing

The repo is organized so that most day-to-day work happens in three folders:

- `script/`: runnable Python scripts
- `docs/`: notes and reference docs
- `dataset/`: training data and raw source material

## Repo Layout

```text
JacLLM/
├── dataset/
│   ├── cpt/              # text-only training datasets
│   ├── sft/              # instruction / response datasets
│   └── raw/              # unprocessed source material
├── docs/
│   ├── CONVENTION.md     # code layout and style (authoritative)
│   ├── DATASET.md        # dataset format notes
│   ├── SCRIPT.md         # script notes
│   └── reference/        # notebooks and external references
├── script/
│   ├── train/
│   │   ├── cpt.py        # CPT training entrypoint
│   │   ├── sft.py        # SFT training entrypoint
│   │   ├── train.py      # recipe-driven training (recipe/)
│   │   └── recipe/       # training recipes + README.md
│   ├── dataset/
│   │   ├── cpt/          # raw → CPT split builders (file.py, repo.py)
│   │   ├── sft/          # raw → SFT split builders (js2jac.py, osp.py, farm.py, ...)
│   │   ├── parser/       # chunking / AST helpers for raw sources
│   │   ├── template/     # prompt_template.json, ds_report.json
│   │   └── statistics.py # dataset stats
│   ├── eval/             # inference backends, gate, probes, Nitin-test harness
│   ├── utils/            # shared helpers (model loading, jac CLI, jac blocks)
│   ├── inference.py      # local chat/inference
│   └── merge_lora.py     # merge LoRA adapter into a standalone model
├── output/               # training outputs and checkpoints
├── requirement.txt
└── setup_env.sh
```

## Setup

### 1. Prerequisites

- Linux with NVIDIA GPU recommended
- `mamba` installed
- Python 3.12
- enough disk space for base models, checkpoints, and merged exports

### 2. Create the environment

From the repo root:

```bash
bash setup_env.sh
```

To use a custom environment name:

```bash
bash setup_env.sh myenv
```

Then activate it:

```bash
mamba activate jacllm
```

If you used a custom name, replace `jacllm` with that name.

## Dataset Format

### CPT

`script/train/cpt.py` expects JSONL files with a `text` field:

```json
{"text":"training sample"}
```
For more details, please see [`docs/DATASET.md`](docs/DATASET.md).

## How To Use

### Run CPT training

Defaults (base model, LoRA and training hyperparameters) live in `default_config()` in [`script/train/cpt.py`](script/train/cpt.py). Pick the dataset and common overrides from the CLI:

```bash
python script/train/cpt.py --ds <dataset> [--steps N] [--epochs N] [--lr 5e-5] [--rank 128]
```

Outputs go into `output/adapter/<MM-DD_HH-MM>-<run_name>/`.

#### Continue training

Two flavors, pick the one that matches your intent:

**`--resume <checkpoint-N path>`** — resume the exact same run
- Restores adapter weights **and** optimizer state, LR scheduler, RNG, step counter
- Loss curve continues seamlessly from where the run left off
- Use for: recovering from a crash, adding more steps to a run
- Path must be a `checkpoint-N/` folder (Trainer's full state), NOT the top-level `adapter/`

```bash
python script/train/cpt.py --ds <dataset> --resume output/adapter/<run>/checkpoint-100
```

**`--adapter <adapter path>`** — start a fresh run on top of an existing adapter
- Loads adapter weights only; optimizer restarts from zero, LR schedule re-runs warmup, step counter resets to 0
- Loss will visibly jump at step 0 (warmup + Adam moments = 0) — this is expected, **not** a continuation of the previous curve
- Use for: fine-tuning a released adapter on a new dataset, second-stage training

```bash
python script/train/cpt.py --ds <new_dataset> --adapter output/adapter/<run>/adapter
```

`--resume` and `--adapter` are mutually exclusive.

**Frozen by the loaded adapter in both modes** (silently ignored if you pass them): `--rank`, `target_module`, `lora_alpha`, `rslora`. These define the adapter's tensor shapes and cannot change mid-life.

To change any shape-affecting param, **merge the adapter into the base first**, then start a fresh run:

1. `python script/merge_lora.py` — merge the old adapter into a standalone model
2. Point `base_model` (in `default_config()` or the recipe) at the merged output
3. Run without `--adapter` / `--resume` (from-scratch on top of the merged base) with the new hyperparameters

To see training loss, see
```bash 
tensorboard --logdir path/to/tensorboard
```
under `run` folder in the adapter folder, default path is 
```bash
tensorboard --logdir JacLLM/output/adapter/<YOUR_EXPERIMENT_NAME>/runs
```


### Run SFT training

`script/train/sft.py` trains on instruction/response JSONL under `dataset/sft/<task>/<dataset>/{train,valid}.jsonl`. Build these first with a script in `script/dataset/sft/` (see [Prepare an SFT dataset](#prepare-an-sft-dataset)).

Defaults live in `default_config()` in [`script/train/sft.py`](script/train/sft.py). Pick the task (folder under `dataset/sft/`) and dataset from the CLI:

```bash
python script/train/sft.py --task js2jac --ds Nitin-js2jac --epochs 3 --lr 2e-4
```

Continue training uses the same `--resume` / `--adapter` semantics as CPT — see [Continue training](#continue-training) above; they are mutually exclusive and the LoRA shape params (`--rank`, `target_module`, `lora_alpha`, `rslora`) are frozen by any loaded adapter.

`do_eval` is off by default (SFT eval OOMs on 16GB VRAM); evaluate post-hoc with `script/eval/batch.py` (see [`script/eval/README.md`](script/eval/README.md)).

### Run recipe training

For multi-dataset runs, a recipe sets the stage, hyperparameters and dataset mix:

```bash
python script/train/train.py --recipe script/train/recipe/<name>.yaml
```

See [`script/train/recipe/README.md`](script/train/recipe/README.md) for the schema and mixing strategies.

#### Prepare an SFT dataset

Each builder under `script/dataset/sft/` reads raw JSONL from `dataset/raw/<format>/<name>/` and writes an 80/20 split into `dataset/sft/<task>/<name>/{train,valid}.jsonl`:

| Builder | Task | Raw input |
| --- | --- | --- |
| `js2jac.py` | `js2jac` | `dataset/raw/jac/Nitin-3k-js2jac-idiom/` |
| `code_complete.py` | `code_completion` | `dataset/raw/jac/Nitin-9k-py2jac-idiom/` |
| `osp.py` | `osp` | `dataset/raw/jac/Nitin-1k-osp/` |
| `farm.py` | `farm` | `dataset/raw/jac/Nitin-2k-farm/` |
| `scaffold2impl.py` | `scaffold2impl` | `dataset/raw/repo/` |
| `qa.py` | routes to `qa` / `py2jac` / `code_gen` | `dataset/raw/agent-synth/sft_train.jsonl` |

Edit the config block at the top of the chosen script (`DS_NAME`, filter fields, `VALID_SIZE`, `SEED`, `OUT_FORMAT`) then run e.g.:

```bash
python script/dataset/sft/js2jac.py
```

Prompt templates live in `script/dataset/template/prompt_template.json`.

### Run local inference

Edit the model settings in [`script/inference.py`](script/inference.py):

- `BASE_MODEL`
- `MODEL_PATH` (merged model or adapter dir)
- generation settings such as `MAX_NEW_TOKENS` and `TEMPERATURE`

Then run:

```bash
python script/inference.py
```

This opens a terminal chat loop. Use `/clear` to reset conversation history.

### Merge a LoRA adapter

```bash
python script/merge_lora.py --adapter output/adapter/<run>/adapter [--out output/model/<name>] [--no-4bit] [--gguf q4_k_m]
```

Merged outputs are written to `output/model/<adapter_dir_name>` unless `--out` is given. Defaults sit in the Setting block of [`script/merge_lora.py`](script/merge_lora.py).

## Recommended Workflow

1. Prepare or verify datasets under `dataset/cpt/` and `dataset/sft/`.
2. Run `script/train/train.py --recipe ...` (or `cpt.py` / `sft.py`) to produce adapter checkpoints in `output/adapter/`.
3. Evaluate with `script/eval/` (see [`script/eval/README.md`](script/eval/README.md)), or point `script/inference.py` at a checkpoint.
4. Run `script/merge_lora.py` when you need a merged export.

## Related Docs

- [`docs/CONVENTION.md`](docs/CONVENTION.md)
- [`docs/DATASET.md`](docs/DATASET.md)
- [`docs/SCRIPT.md`](docs/SCRIPT.md)
- [`docs/DEBUG.md`](docs/DEBUG.md)
