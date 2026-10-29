"""Read a training recipe, resolve dataset paths, build a mixed HF dataset.

A recipe is YAML (.yaml/.yml) or a Python module exporting a `RECIPE` dict.
See `recipe/README.md` for schema details.

The mixer returns (stage, config, train_ds, eval_ds). It never loads models —
that is train.py's job (via run_cpt / run_sft / run_grpo). A `grpo` entry is an
RL task set (dataset/rl/<task>/<set>/) loaded through rl.task, one row per task.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml
import pyarrow as pa
from datasets import (
    Dataset,
    Features,
    concatenate_datasets,
    interleave_datasets,
    load_dataset,
)

DATASET_ROOT = Path(__file__).resolve().parent.parent.parent / "dataset"
PROMPT       = Path(__file__).resolve().parent.parent / "dataset" / "template" / "prompt_template.json"


# Recipe I/O ================================================================
def load_recipe(path: str | Path) -> dict:
    """Parse a recipe file (.yaml/.yml or .py) into a dict."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Recipe not found: {p}")
    if p.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    if p.suffix.lower() == ".py":
        spec = importlib.util.spec_from_file_location(p.stem, p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not hasattr(mod, "RECIPE"):
            raise ValueError(f"Python recipe {p} must define RECIPE = {{...}}")
        return mod.RECIPE
    raise ValueError(f"Unsupported recipe format: {p.suffix}")


# Dataset resolution ========================================================
def resolve_names(stage: str, task: str | None, names) -> list[Path]:
    """Return the list of dataset directories a single recipe entry expands to.

    stage: "cpt", "sft" or "grpo"
    task:  subdir name under sft/ or rl/ (ignored when stage == "cpt")
    names: str, list[str], "*" or None
    """
    if stage == "cpt":
        base = DATASET_ROOT / "cpt"
    elif stage == "sft":
        if not task:
            raise ValueError("SFT recipe entry requires `task`")
        base = DATASET_ROOT / "sft" / task
    elif stage == "grpo":
        if not task:
            raise ValueError("GRPO recipe entry requires `task`")
        base = DATASET_ROOT / "rl" / task
    else:
        raise ValueError(f"Unknown stage: {stage}")

    if not base.is_dir():
        raise FileNotFoundError(f"Missing dataset dir: {base}")

    if names in (None, "*", []):
        return sorted(d for d in base.iterdir() if d.is_dir())
    if isinstance(names, str):
        names = [names]
    return [base / n for n in names]


TRAIN_COLUMNS = ("text", "messages", "tools", "prompt", "task_id", "task_dir", "task_type")  # columns the trainers consume


def load_splits(ds_dir: Path, splits: list[str]) -> Dataset | None:
    """Load and concatenate the requested splits under one dataset dir.

    Non-training columns (everything except `text` and `messages`) are dropped
    so that mixing across datasets can't fail on mismatched `meta` schemas.
    """
    files = [str(ds_dir / f"{s}.jsonl") for s in splits if (ds_dir / f"{s}.jsonl").is_file()]
    if not files:
        print(f"[mixer] WARNING: skipping {ds_dir}; none of these splits exist: {splits}")
        return None
    ds = load_dataset("json", data_files=files, split="train")
    drop = [c for c in ds.column_names if c not in TRAIN_COLUMNS]
    return ds.remove_columns(drop) if drop else ds


def load_rl_splits(set_dir: Path, splits: list[str], seed: int) -> Dataset:
    """Task rows of an RL set (prompt messages + task columns), via rl.task."""
    from dataset.pipeline import load_prompts
    from rl.task import load_split, to_dataset
    prompts = load_prompts(PROMPT, "system", "rl_functions")
    return to_dataset([t for s in splits for t in load_split(set_dir, s)], prompts, seed)


def entry_datasets(entry: dict, stage: str, kind: str, seed: int = 3407) -> list[tuple[str, Dataset, float, int]]:
    """Expand one recipe entry into (label, dataset, weight, repeat) tuples.

    kind: "train" or "valid" — picks the split list. GRPO has no valid split
    (eval runs through eval/rl/run_eval.py), so it yields nothing for "valid".
    """
    task   = entry.get("task")
    names  = entry.get("name") or entry.get("names")
    splits = entry.get("split") or entry.get("splits") or ["train"]
    if isinstance(splits, str):
        splits = [splits]
    if kind == "valid":
        splits = ["valid" if s == "train" else s for s in splits]

    weight = float(entry.get("weight", 0)) or 0.0
    repeat = int(entry.get("repeat", 1))

    out: list[tuple[str, Dataset, float, int]] = []
    if stage == "grpo" and kind == "valid":
        return out
    for ds_dir in resolve_names(stage, task, names):
        ds = load_rl_splits(ds_dir, splits, seed) if stage == "grpo" else load_splits(ds_dir, splits)
        if ds is None or len(ds) == 0:
            continue
        label = f"{task or 'cpt'}/{ds_dir.name}"
        out.append((label, ds, weight, repeat))
    return out


# Mixing ====================================================================
def mix(items: list[tuple[str, Dataset, float, int]], mixing: dict, seed: int) -> Dataset | None:
    if not items:
        return None
    # Planning conversations lack tool fields; Arrow must align nested message
    # structs before mixing them with tool-use conversations. Nulls are removed
    # by sft.chat_inputs before rendering, preserving the original conversation.
    features = Features.from_arrow_schema(pa.unify_schemas(
        [ds.features.arrow_schema for _, ds, _, _ in items]
    ))
    aligned = []
    for label, ds, weight, repeat in items:
        for column in features:
            if column not in ds.column_names:
                ds = ds.add_column(column, [None] * len(ds))
        aligned.append((label, ds.cast(features), weight, repeat))
    items = aligned
    strategy = (mixing.get("strategy") or "concat").lower()

    if strategy == "concat":
        parts = []
        for _, ds, _, repeat in items:
            for _ in range(max(1, repeat)):
                parts.append(ds)
        return concatenate_datasets(parts).shuffle(seed=seed)

    if strategy == "sequential":
        # Preserve recipe order: each task runs to completion before the next.
        # Rows within a task are shuffled (seeded) so on-disk sort order
        # (source, length, ...) doesn't leak into consecutive steps.
        parts = []
        for _, ds, _, repeat in items:
            for _ in range(max(1, repeat)):
                parts.append(ds.shuffle(seed=seed))
        return concatenate_datasets(parts)

    if strategy == "interleave":
        datasets = [ds for _, ds, _, _ in items]
        weights  = [w for _, _, w, _ in items]
        if any(w <= 0 for w in weights):
            raise ValueError("Every dataset entry needs a positive `weight` under interleave.")
        total = sum(weights)
        probs = [w / total for w in weights]
        stopping = mixing.get("stopping", "all_exhausted")
        return interleave_datasets(
            datasets, probabilities=probs, seed=seed, stopping_strategy=stopping,
        )

    raise ValueError(f"Unknown mixing.strategy: {strategy}")


# Config assembly ===========================================================
MODEL_KEYS      = ("base_model", "adapter", "resume_from", "run_name", "out_dir",
                   "seed", "max_seq_length", "load_in_4bit", "text_only",
                   "dtype",
                   "chat_template", "merge", "save_method", "push_hf",
                   "hf_org", "hf_repo", "hf_token", "report_to", "log_freq")
HYPERPARAM_KEYS = ("epochs", "batch_size", "grad_acc", "optimizer",
                   "lr", "embed_lr", "scheduler", "warmup_steps", "max_steps",
                   "weight_decay", "save_steps", "save_total_limit",
                   "eval_steps", "do_eval",
                   "lora_rank", "lora_alpha", "lora_dropout", "target_module",
                   "rslora", "bias", "grad_checkpt", "packing",
                   "instruction_part", "response_part")
# Allowed only under `stage: grpo` (train/grpo.py default_config), so SFT/CPT recipes stay strict.
GRPO_MODEL_KEYS = ("enable_thinking",)
GRPO_KEYS       = ("max_grad_norm", "num_generations", "temperature", "top_p", "top_k", "min_p",
                   "repetition_penalty", "max_prompt_length", "max_completion_length", "beta",
                   "num_iterations", "loss_type", "importance_sampling_level", "epsilon",
                   "epsilon_high", "scale_rewards", "mask_truncated_completions",
                   "shuffle_dataset", "log_completions", "reward", "grade_workers",
                   "grade_mem_gb", "grade_timeout", "purge_pg_steps")

TOP_LEVEL_KEYS = {"recipe", "hyperparams", "mixing", "datasets"}
MIXING_KEYS = {"strategy", "stopping"}
DATASET_KEYS = {"task", "name", "names", "split", "splits", "weight", "repeat"}


def reject_unknown(section: str, values: dict, allowed) -> None:
    """Reject recipe keys outside the documented schema."""
    unknown = sorted(set(values) - set(allowed))
    if unknown:
        raise ValueError(f"Unknown key(s) in {section}: {', '.join(unknown)}")


def validate_recipe(recipe: dict) -> None:
    """Validate recipe structure before resolving datasets."""
    if not isinstance(recipe, dict):
        raise ValueError("Recipe root must be a mapping.")
    reject_unknown("recipe root", recipe, TOP_LEVEL_KEYS)

    sections = ("recipe", "hyperparams", "mixing")
    for section in sections:
        if section in recipe and not isinstance(recipe[section], dict):
            raise ValueError(f"`{section}` must be a mapping.")
    grpo = (recipe.get("recipe", {}).get("stage") or "").lower() == "grpo"
    reject_unknown("recipe", recipe.get("recipe", {}),
                   MODEL_KEYS + ("name", "stage") + (GRPO_MODEL_KEYS if grpo else ()))
    reject_unknown("hyperparams", recipe.get("hyperparams", {}),
                   HYPERPARAM_KEYS + ("max_seq_len",) + (GRPO_KEYS if grpo else ()))
    reject_unknown("mixing", recipe.get("mixing", {}), MIXING_KEYS)

    datasets = recipe.get("datasets", [])
    if not isinstance(datasets, list):
        raise ValueError("`datasets` must be a list.")
    for index, entry in enumerate(datasets):
        if not isinstance(entry, dict):
            raise ValueError(f"datasets[{index}] must be a mapping.")
        reject_unknown(f"datasets[{index}]", entry, DATASET_KEYS)


def merge_config(recipe: dict) -> dict:
    """Flatten [recipe] + [hyperparams] into the flat config dict runners expect."""
    r  = recipe.get("recipe", {})
    hp = recipe.get("hyperparams", {})
    cfg: dict = {}
    for k in MODEL_KEYS + GRPO_MODEL_KEYS:
        if k in r:
            cfg[k] = r[k]
    for k in HYPERPARAM_KEYS + GRPO_KEYS:
        if k in hp:
            cfg[k] = hp[k]
    if "max_seq_len" in hp and "max_seq_length" not in cfg:
        cfg["max_seq_length"] = hp["max_seq_len"]
    if not cfg.get("run_name"):
        cfg["run_name"] = r.get("name", "recipe")
    return cfg


# Public entry point ========================================================
def build_from_recipe(path: str | Path) -> tuple[str, dict, Dataset, Dataset | None]:
    """Read a recipe file → (stage, config, train_ds, eval_ds)."""
    recipe = load_recipe(path)
    validate_recipe(recipe)
    r = recipe.get("recipe", {})
    stage = (r.get("stage") or "").lower()
    if stage not in ("cpt", "sft", "grpo"):
        raise ValueError(f"recipe.stage must be 'cpt', 'sft' or 'grpo', got: {stage!r}")

    cfg  = merge_config(recipe)
    seed = int(cfg.get("seed", 3407))

    entries = recipe.get("datasets") or []
    if not entries:
        raise ValueError("Recipe has no `datasets` entries.")

    train_items, valid_items = [], []
    for entry in entries:
        train_items.extend(entry_datasets(entry, stage, "train", seed))
        if cfg.get("do_eval"):
            valid_items.extend(entry_datasets(entry, stage, "valid", seed))

    mixing = recipe.get("mixing", {}) or {"strategy": "concat"}
    train_ds = mix(train_items, mixing, seed)
    # Trainer's default RandomSampler reshuffles every epoch, which would undo
    # the curriculum order that `sequential` builds.
    if (mixing.get("strategy") or "concat").lower() == "sequential":
        cfg["train_sampling"] = "sequential"
    if train_ds is None:
        raise ValueError("Recipe produced no training rows.")

    # valid: always concat + shuffle (interleave-with-loop makes no sense for eval)
    eval_ds = mix(valid_items, {"strategy": "concat"}, seed) if valid_items else None

    print(f"[mixer] stage={stage} strategy={mixing.get('strategy','concat')} "
          f"train_rows={len(train_ds)} eval_rows={len(eval_ds) if eval_ds else 0}")
    for label, ds, w, rep in train_items:
        extra = f"weight={w:.3f}" if mixing.get("strategy") == "interleave" else f"repeat={rep}"
        print(f"  {label}  rows={len(ds)}  {extra}")

    return stage, cfg, train_ds, eval_ds
