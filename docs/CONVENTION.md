# JacCoder conventions

Reference for how code is organised and written in this repo. Applies to all
Python under `script/`.

## What this project is

JacCoder is a training workspace for Jac-focused language models. Four
domains sit under `script/`:

- `dataset/` — turn raw source (`.jac` files, JSONL, GitHub repos, agent
  transcripts) into training-ready JSONL under `dataset/{cpt,sft}/…`.
- `train/` — CPT and SFT training loops built on Unsloth, plus a recipe
  system for multi-dataset mixes.
- `eval/` — measure a trained adapter (gating, batched inference, drift
  probes).
- `rl/` — the RL environment: load task sets from `dataset/rl/`, render
  prompts, grade completions with hidden tests, and GRPO reward functions.
  Used by both `train/grpo.py` and `eval/rl/run_eval.py`.

Top-level scripts (`inference.py`, `merge_lora.py`) provide REPL and export.


## Where code lives

```
script/
├── utils/                cross-cutting helpers (see rule below)
│   ├── classifier.py     content classifier (function/graph/osp/fullstack)
│   ├── io.py             JSONL iteration + Parquet export
│   ├── jac_block.py      extract ```jac``` fences from LLM output
│   ├── jac_cli.py        subprocess wrapper around `jac check/run/build/start/test` (+ timeout/memory cap, postgres purge)
│   └── model.py          Unsloth model load + generate
├── dataset/
│   ├── pipeline.py       shared record-write pipeline (used by every producer; write_rl_set for RL sets)
│   ├── inspect.py        JSONL schema inspector (standalone CLI)
│   ├── sample_hf.py      N random rows per group of a local HF parquet dataset → Markdown (standalone CLI)
│   ├── statistics.py     per-dataset statistics writer (statistic.json)
│   ├── repo_stats.py     codebase statistics of raw/repo (raw/repo/stats.json)
│   ├── cpt/              CPT producers, one per input shape
│   ├── sft/              SFT producers, one per task type
│   ├── rl/               RL task-set producers, one per upstream (kodcode.py)
│   ├── parser/           parsers/transformers used by producers
│   │   ├── chunk.py
│   │   ├── md2ast.py
│   │   └── repo.py       repo walker, Jac scaffold extractor, declaration/symbol index
│   └── template/         prompt_template.json, ds_report.json
├── rl/
│   ├── task.py           load dataset/rl/<task>/<set> splits → HF Dataset(prompt, task_*)
│   ├── harness.py        render prompt; completion → workspace files (format / forbidden screen)
│   ├── rewards.py        TRL reward funcs, per-step grading cache, rollout log
│   └── graders/          one grader per task type + plain-assert self-test
├── train/                a package: scripts import `train.utils`, `train.mixer` (`utils` = script/utils)
│   ├── cpt.py            run_cpt(config, ds) + single-dataset CLI
│   ├── sft.py            run_sft(config, ds) + single-dataset CLI
│   ├── grpo.py           run_grpo(config, ds) + single-set CLI
│   ├── mixer.py          recipe → mixed HF Dataset (concat / interleave / sequential)
│   ├── train.py          --recipe CLI dispatcher
│   ├── utils.py          load_trainable / ensure_chat_template / finalize_out_dir / model_source / print_gpu_banner / save_adapter
│   └── recipe/           *.yaml / *.py recipe files + README.md
├── eval/
│   ├── gate.py           pass/fail gating from generated jac
│   ├── batch.py          batched adapter inference
│   ├── compare/          confusion matrix / taxonomy / heatmap comparison
│   ├── infer/            adapter + openrouter inference backends
│   ├── probe/            loss / SVD / adapter probes
│   ├── rl/               RL task-set eval (pass@k, readiness)
│   └── Nitin-test/       vendored hidden-test harness (see PROVENANCE.md)
├── spike/                experimental scripts (own README + spike_utils.py)
├── inference.py          REPL chat
├── merge_lora.py         LoRA merge + export
└── plot_loss.py, plot_usage.py   training-loss / resource-usage charts
```


## Where a helper belongs

- `script/utils/` is for helpers used across at least two of `dataset/`,
  `train/`, `eval/`, and the top-level scripts. Every current entry qualifies:
  `classifier` and `io` are used by every dataset script; `jac_block` is used
  by `dataset/sft/{qa,osp}.py` and `eval/gate.py`; `jac_cli` is used by `eval/gate.py`
  (and is the intended entry point for any code that shells out to `jac`);
  `model` is used by `inference.py` and multiple `eval/` scripts.
- Helpers used by one domain only live inside that domain:
  - `dataset/parser/` — dataset-side parsers/transformers.
  - `train/utils.py` — training-only helpers.
  - `eval/…` — evaluation-only helpers stay under `eval/`.
- Standalone CLIs (no importers) live at the top of the folder they
  belong to (`dataset/inspect.py`, `dataset/statistics.py`, top-level
  `inference.py`, `merge_lora.py`), not in `utils/`.


## Dataset script structure

Every producer under `dataset/cpt/` and `dataset/sft/` follows the same
shape:

```python
import ..., sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from utils.io         import iter_sources
from utils.classifier import classify_structural as classify
from dataset.pipeline import load_prompts, report, split_and_write

# Setting =================================================
DS_FORMAT  = "jac"
DS_NAME    = "..."
SOURCE     = "code"
TASK_TYPE  = "..."               # sft only
...
DS_ROOT    = f"{Path(__file__).resolve().parent}/../../../dataset"
IN_DIR     = f"{DS_ROOT}/raw/{DS_FORMAT}/{DS_NAME}"
OUT_DIR    = f"{DS_ROOT}/{cpt|sft}/{...}/{DS_NAME}"
PROMPT     = f"{Path(__file__).resolve().parent}/../template/prompt_template.json"
VALID_SIZE = 0.2                 # 0.0 for CPT
SEED       = 3407

# Functions ===============================================
def build_record(fp, ..., prompts, rng) -> dict:
    """Task-specific: raw fields -> one output record dict."""
    return {"messages": [...], "meta": {...}}

def <verb>(in_dir=IN_DIR, out_dir=OUT_DIR, format=OUT_FORMAT):
    # 1. Read raw source into `samples`
    # 2. Load prompts + shuffle
    # 3. records = [build_record(...) for ... in samples]
    # 4. counts = split_and_write(records, out_dir, VALID_SIZE, format)
    # 5. report(counts, out_dir)

# Run =====================================================
if __name__ == "__main__":
    <verb>()
```

The `Setting` / `Functions` / `Run` banner sections are used by every
producer. `pipeline.split_and_write` owns shuffle-invariant split + write +
optional Parquet conversion; the script owns the raw read and the shape of
one record.

The `meta` block inside a record is standardized across producers:
`{"source", "format", "class", "task_type", "fp"}` for SFT, and
`{"source", "format", "class", "fp"}` for CPT. Extra task-specific fields
(`files`, `chars`, etc.) go alongside these standard keys.


## Training recipe format

`script/train/train.py --recipe <path>` accepts YAML (`.yaml`, `.yml`) or
Python (module that defines `RECIPE = {…}`). The full schema and mixing
strategies are documented in `script/train/recipe/README.md`.

Under `train/`, `cpt.py`, `sft.py` and `grpo.py` expose two entry points:

- `default_config()` — returns the flat config dict with all defaults
- `run_cpt(config, train_ds, eval_ds=None)` / `run_sft(...)` / `run_grpo(...)` — runs one
  training loop over given HF Dataset objects

Their `if __name__ == "__main__":` block builds a config from CLI flags and
loads a single dataset. `train.py` builds a mixed dataset via `mixer.py`
and calls the same runner functions — recipes never go through subprocess.


## Coding style

### Naming

- `snake_case` for functions and variables.
- `CONSTANT_CASE` for module-level tunables, declared at the top under a
  `# Setting =====` banner.
- Public function names have no leading underscore. Module-internal
  helpers are named plainly (they are already scoped by the module).
- Filenames match the domain concept: task-name lowercase
  (`js2jac.py`, `osp.py`, `farm.py`) for task producers, input-granularity
  lowercase (`file.py`, `repo.py`) for CPT producers.

### Types

- PEP 604 unions: `list[str] | None`, `str | Path`. `typing.Optional` is
  not used.
- Type hints on public function signatures. Local variables are only
  annotated when the type is not obvious from initialization.

### Imports

- Grouped stdlib | third-party | local, one blank line between groups.
- Stdlib imports may share a line: `import argparse, os, re`.
- Third-party and local imports are one per line.
- Multiple names from the same module use one `from X import a, b, c`
  when short, or aligned parenthesized form when long.
- `sys.path.append(...)` shim goes between the third-party and local
  import groups.
- `from __future__ import annotations` is not used.

### Layout

- Section banners between top-level regions:
  `# Section =================================================` (≥50 char bar).
- The two banners used by every dataset producer are `# Setting` and
  `# Functions`; the entry point sits under a `# Run` banner.
- Aligned `=` inside blocks of related assignments:
  ```python
  DS_NAME    = "..."
  VALID_SIZE = 0.2
  SEED       = 3407
  ```
- Aligned keyword arguments in long calls (`UnslothTrainingArguments`,
  `FastLanguageModel.get_peft_model`).

### Docstrings and comments

- Module-level docstring: one line, describes the file's role.
- Function docstring: one line for helpers; short paragraph for
  module-level public functions, listing args and side effects.
- Comments explain **why** — a hidden constraint, a workaround for a
  specific bug, a non-obvious invariant. See the `config.architectures`
  restoration comment in `utils/model.py:load_model` for the shape.
- Trailing inline comments for individual tunable rationale are welcome.
- Comments that explain **what** the code does (visible from the
  identifiers) are not written.

### Defensive checks

- Validate inputs at true boundaries (user CLI args, external APIs, file
  I/O of untrusted content).
- Do not validate values that can only come from a module-level constant
  or from within the same script — the natural error surfaces the same
  information more clearly.
- `try/except` catches a **specific** exception the caller can respond
  to. Bare `except:` and `except Exception:` are not used except in the
  HTTP retry loop of `eval/infer/openrouter.py`.


## Filesystem layout used by dataset scripts

Every producer resolves paths relative to a computed `DS_ROOT`:

```
dataset/
├── raw/                          # unprocessed source material (gitignored)
│   ├── jac/<DS_NAME>/            # jsonl or .jac files
│   ├── repo/<repo_name>/         # runnable repos
│   ├── agent-synth/*.jsonl       # LLM-generated seed data
│   ├── hf/<name>/                # `hf download --local-dir` copies of HF datasets (parquet)
│   ├── markdown/                 # markdown corpora
│   ├── diff/, session/           # git diffs / session logs
├── cpt/<DS_NAME>/                # CPT output (train.jsonl only)
├── sft/<TASK_TYPE>/<DS_NAME>/    # SFT output (train.jsonl + valid.jsonl)
└── rl/<TASK_TYPE>/<SET_NAME>/    # RL tasks: meta.json (per set), tasks/<id>/ (model-visible), tests/<id>/ (grader-only), splits/*.txt
```

`raw/` is gitignored. The `train.jsonl` / `valid.jsonl` under `cpt/` and
`sft/…/` are checked in; `statistic.json` sits alongside them.
