# Model Choice

> **In plain words.** There are two kinds of model:
>
> - **Dense:** every part of the model works on every token.
> - **MoE (mixture of experts):** the model is many smaller "experts", and only a few of them work on each token.
>
> "30B-A3B" means 30B parameters in total, but only 3B **active** per token. Think of a 30-person company where only 3 people handle any one job, versus a 9-person team where everyone works on everything.
>
> For writing code in one new language, our results suggest the dense team does better: what counts is how many parameters actually work on each token, not the total. Unfamiliar terms are in the [glossary](glossary.md).

## Models tried

| Model | Type | Where it was trained | Method | Evidence |
|---|---|---|---|---|
| Qwen3-Coder-30B-A3B | MoE, 30B total / 3B active | (a) Apple Silicon Mac, MLX (b) RunPod RTX PRO 6000 96 GB | (a) 4-bit MLX, LoRA r16, SFT only (b) bnb 4-bit QLoRA r64, CPT → SFT | (a) [report/Qwen30BA3B/08/](../../report/Qwen30BA3B/08/), [report/v1.2/0916Weekly/outline.md](../../report/v1.2/0916Weekly/outline.md) (b) `script/train/recipe/0922-qwen3coder-trueseq-r64/` |
| Ornith-1.5-9B | dense | RTX 5080 16 GB; later also the RTX PRO 5000 48 GB for 64k runs | QLoRA, r64 | `1023-v135/`, [report/v1.3/](../../report/v1.3/), [report/weekly/1026.md](../../report/weekly/1026.md) |
| Qwen3.8-27B | dense | RTX PRO 5000 48 GB (shared server) | QLoRA, r32, 16k | `1123-qwen27b-r32/` |
| inkling2 mini | MoE, about 30B | 1× DGX Spark | (team-reported, not in repo) | colleague's run |
| GLM-5.3-Flash | MoE | 2× DGX Spark | (team-reported, not in repo) | colleague's run |

The Mac run is Ayush's experiment "08": 4-bit MLX with the routers kept at 8-bit, rank 16 on 16 of 48 blocks including experts, max_seq 3072, about 0.65 epoch, 28.2 GB peak, about 4.3–5 h.

## Results we can compare

**Ornith 9B vs Qwen3-Coder 30B-A3B, same 3,081 validation rows, `jac check` pass rate** ([report/v1.2/check_report.md](../../report/v1.2/check_report.md), [report/v1.2/qwen3coder-sft-v1.2-q4km-check-heatmap.png](../../report/v1.2/qwen3coder-sft-v1.2-q4km-check-heatmap.png)):

| | overall | code_completion | py2jac | js2jac | osp | code_gen |
|---|---:|---:|---:|---:|---:|---:|
| Ornith 9B v1.2 (dense) | **87.0%** | 92.6% | 92.5% | 85.3% | 98.1% | 61.7% |
| Qwen3-Coder 30B-A3B v1.2 (MoE) | 80.0% | 93% | 59% | 70% | 73% | 51% |

**Same pair, 1,000-problem hidden-test suite** ([report/v1.2/0916Weekly/outline.md](../../report/v1.2/0916Weekly/outline.md)):

| | jac check | all tests pass | correct when it compiles |
|---|---:|---:|---:|
| Ornith 9B v1.2 | 81.1% | 49.8% | 61.4% |
| Qwen3-Coder 30B (Mac MLX run) | 71.5% | 54.9% | 76.8% |

The report itself warns that this is "not a controlled model-size ablation": the two runs used different data, methods and Jac versions.

**Nitin function suite** (972 problems, Jac 0.36.1, completion and translation are 486 problems each):

| | pass@1 | completion | translation |
|---|---:|---:|---:|
| Ornith 9B v1.35 | 56.1% | 32.1% | 80.0% |
| Qwen3.8-27B r32 (SFT stopped at step 90 of 103, unmerged) | 39.0% | 46.9% | 31.1% |
| inkling2 mini | — | about 32% (team-reported) | — |
| GLM-5.3-Flash | — | similar to Qwen3-Coder 30B (team-reported) | — |

Sources: `script/eval/Nitin-test/out/*/summary.json` (doc only, no report file yet for the 27B). The 27B was trained on the `-nofence` SFT sets and stopped early, so its weak translation score may come from the run rather than the model (see the known data issues in [data_preparation.md](data_preparation.md)).

## Recommendation: dense models

Our reading of the numbers above:

- **Ornith 9B vs inkling2 mini.** The dense 9B (32.1% completion) performs about the same as inkling2 mini (about 32%), even though inkling2 has about 30B total parameters.
- **Ornith 9B vs Qwen3-Coder 30B-A3B.** The dense 9B beats the 30B-A3B MoE on `jac check` on the same rows (87.0% vs 80.0%).
- **GLM-5.3-Flash.** It lands near another model of similar active size rather than near its total parameter count.

**Hypothesis.** For a narrow domain like coding in one new language, what matters is the number of **activated** parameters per token, not the total. An MoE spends its capacity across many experts, but each token only uses a few of them. MoE models do have huge total parameter counts at roughly constant compute per token (Fedus et al., JMLR 2022). Whether the Jac knowledge actually ends up in a few experts is **not tested**. To test it, analyse which experts the router sends Jac tokens to, and where the LoRA updates concentrate (for example with `script/eval/probe/svd_energy.py`).

**This is an interpretation of the data, not a controlled result.** The comparisons differ in data version, method (MLX vs bnb), Jac version and evaluator. A clean test would train a dense and an MoE model of similar active size on the same recipe and evaluate both on the same suite.

**Practical reasons that also favour dense models:**

- **Merging.** MoE adapters with LoRA on expert parameters cannot be merged into a 4-bit base: the merge silently yields the base model (`utils/model.py`). They must be served unmerged.
- **Serving.** A 9B dense GGUF serves the full 262k context on one 48 GB card. Memory and speed are predictable on local hardware, which is where the model is meant to run.
