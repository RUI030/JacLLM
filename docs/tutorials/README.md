# JacLLM Tutorial

Related repositories:

- **Data generation:** [chess10kp/jac-data-gen](https://github.com/chess10kp/jac-data-gen)
- **Training (this repo):** [RUI030/JacLLM](https://github.com/RUI030/JacLLM)
- **Harness:** [RUI030/Jach](https://github.com/RUI030/Jach)

This folder explains what the project does, how models are trained, and why the current choices were made. It is written for anyone who has heard terms like "LoRA" or "fine-tuning" but has not worked with them. Every file starts with an **"In plain words"** summary and uses real examples from our data. Every term is defined in the **[glossary](glossary.md)**; keep it open while reading.

## What we are building

[Jac](https://github.com/jaseci-labs/jaseci) is a new language, a superset of Python with object-spatial programming (nodes, edges, walkers) and full-stack app support. General LLMs have seen very little Jac, so they hallucinate syntax, mix in Python or React idioms, and break on the compiler. The goal is a **small model that can run locally and write working Jac**. That covers functions and translations first, and eventually whole apps driven by a coding agent.

The work is split across three repositories:

| Repo | Role | Output |
|---|---|---|
| **jac-data-gen** | Builds verified Jac training data. A deterministic converter produces a "floor" (`jac tool py2jac`, a js2jac converter), then one LLM "idiomize" pass rewrites it. Every record is gated by `jac check`, `jac test` and hidden tests on Jac 0.36.1. | `data/*.jsonl` masters (see `data/MANIFEST.md` there) |
| **JacLLM** (this repo) | Turns raw data into CPT, SFT and RL sets, trains LoRA/QLoRA adapters with Unsloth, and evaluates them. | `dataset/`, recipes in `script/train/recipe/`, adapters in `output/adapter/`, reports in `report/` |
| **Jach** | A coding-agent harness built for a small fine-tuned model. The harness owns the workflow (phases, gates, small per-phase tool sets) instead of trusting the model to plan. Its run log is meant to become the trajectory training format. | Agent runs, baselines, and future trajectory data |

The loop: jac-data-gen makes data → JacLLM trains the model → Jach runs the model as an agent → agent runs expose new failure modes and produce new trajectories → back to data.

## Reading order

0. [glossary.md](glossary.md): plain-language definitions of every term. Skim it first, or look terms up as you go.
1. [model_choice.md](model_choice.md): which base models were tried, on which GPUs, and why we recommend dense models.
2. [training_methods.md](training_methods.md): CPT, SFT and GRPO. What each one is, and which data or scenario it fits.
3. [data_preparation.md](data_preparation.md): the datasets, how they are generated, and each one's share of training tokens.
4. [parameters_and_setup.md](parameters_and_setup.md): context window, LoRA, QLoRA, batch size and gradient accumulation, epochs, and curriculum ordering.
5. [bottleneck_and_current_solution.md](bottleneck_and_current_solution.md): context length, data generation and iteration speed, and what we are doing about each.

## Evidence conventions

Every claim in these files points to its source. Sources rank as follows:

1. **Recipe or report.** `script/train/recipe/*` and `report/*` are the record of what was actually trained and measured.
2. **Repo docs and logs.** `docs/*`, `logs/*` and code defaults. They are used when no recipe or report covers the point, and labelled **(doc only)**.
3. **Team-reported.** Results from colleagues or runs that are not checked into any repo. They are labelled **(team-reported, not in repo)** and give no numbers we cannot back.

External claims cite peer-reviewed papers only (conference or journal versions, not arXiv-only preprints).

## Current state at a glance (2026-11-26)

- **Main model line:** Ornith-1.5-9B (dense), recipe `1023-v135`, about 56% pass@1 on the 972-problem Nitin function suite ([report/v1.3/v13_report.md](../../report/v1.3/v13_report.md), `script/eval/Nitin-test/out/`).
- **Latest run:** Qwen3.8-27B (dense), QLoRA r32, 16k packed, CPT → SFT, on an RTX PRO 5000 48 GB (`script/train/recipe/1123-qwen27b-r32/`).
- **Plan:** first get a ~30B-class dense model (Qwen3.8-27B) good at planning, testing and debugging. Then train the 9B to solve the well-scoped tasks the plan hands it, which keeps cost down and makes progress faster than pushing the 9B to do everything. See [model_choice.md](model_choice.md#plan-a-30b-dense-model-for-the-hard-parts-the-9b-for-the-rest).
- **Main open problem:** agent trajectories are far longer than any context we can train on. See [bottleneck_and_current_solution.md](bottleneck_and_current_solution.md).
