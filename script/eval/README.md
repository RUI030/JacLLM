# Eval scripts — decision tree

Full manual: `docs/EVAL.md`. This file is the "what do I run when" cheat sheet.

## Layout

```
script/eval/
  gate.py                    # scorer: predictions.jsonl → report.json (pass-rate)
  batch.py                   # loads model once, runs infer+gate over EVAL_SET
  infer/                     # producers of predictions.jsonl
    adapter.py               # local HF adapter (Unsloth-loaded)
    openrouter.py            # any OpenRouter-hosted model (Claude, GPT, …)
  compare/                   # post-hoc analysis over report.json / predictions.jsonl
    confmat.py               # per-sample pass/fail confusion matrix
    taxonomy.py              # cluster failures by check_err first-line
  probe/                     # intrinsic model analysis (no dataset scoring)
    svd_energy.py            # LoRA rank sizing via SVD of ΔW = B@A
    cpt_loss.py              # forward NLL per CPT checkpoint
    adapter_viewer.ipynb     # interactive companion to svd_energy
    sft_mask.py              # decode which tokens the real SFT trainer puts loss on
  rl/
    run_eval.py              # RL task sets: sample n per task → rl.graders → pass@k, per-task pass counts
  tool_fim/
    run_eval.py              # pi agent fills held-out stubbed Jac bodies via an OpenAI-compatible server; solved/check/similarity
    serve_eval.sh            # llama-server on a GGUF + run_eval.py
    replay.py                # replays dataset records through real pi; tool results must match the recorded ones
```

## I want to…

| Task | Command |
|---|---|
| Eval one adapter across all SFT tasks | `python script/eval/batch.py --adapter <path> --limit 0` |
| Eval one (task, ds) only | `python script/eval/batch.py --adapter <path> --tasks osp --limit 0` |
| Eval a hosted model (OpenRouter) | `python script/eval/infer/openrouter.py --model <slug> --task <t> --ds <ds>` then `gate.py --pred <path>` |
| Score existing predictions.jsonl | `python script/eval/gate.py --pred <path/to/predictions.jsonl>` |
| See which samples flipped between two runs | `python script/eval/compare/confmat.py --a A/report.json --b B/report.json` |
| Cluster failures by error type | `python script/eval/compare/taxonomy.py --a A/report.json --b B/report.json` |
| Eval a GGUF export (llama-server + gate) | `bash script/eval/gguf_eval.sh <gguf> <tag> <limit>` |
| Tool-use FIM through the real pi agent on a GGUF (held-out stubbed bodies) | `bash script/eval/tool_fim/serve_eval.sh <gguf> <tag> [limit]` (`tool_fim/run_eval.py`: solved = stub replaced + `jac check`) |
| Nitin function tests on a GGUF | `bash script/eval/Nitin-test/run_gguf.sh <gguf> <tag> test` (see `docs/CLOUD_GPU.md`) |
| Check tool_fim records replay byte-identical through pi (dataset sanity, no model) | `python script/eval/tool_fim/replay.py --split valid --limit 20` |
| Which tokens an SFT dataset trains on (packed / unpacked masking) | `python script/eval/probe/sft_mask.py --ds tool_fim/repo-all-pi --n 1 [--packed]` |
| Check LoRA rank utilization | `python script/eval/probe/svd_energy.py --adapter <adapter_dir>` |
| CPT loss per checkpoint | `python script/eval/probe/cpt_loss.py --run <cpt-run> --ds <ds>` |
| RL task set (hidden tests), pass@k | `python script/eval/rl/run_eval.py --adapter <path> --split dev --n-samples 8 --temperature 0.8` |
| RL: re-grade saved predictions after a grader/test change (no GPU) | `python script/eval/rl/run_eval.py --regrade output/eval/rl/<task>/<set>/<run>` (old results kept as `results.prev.jsonl`) |
| RL readiness: which train tasks give GRPO signal | `python script/eval/rl/run_eval.py --adapter <sft adapter> --split train --n-samples 8 --temperature 0.8 [--emit-split]` |

## Adding a new eval

**New task or dataset** → edit `EVAL_SET` in `batch.py`. Dataset lives at `dataset/sft/<task>/<ds>/valid.jsonl`.

**New inference backend** (vLLM, GGUF, another API) → add `infer/<backend>.py` producing predictions.jsonl in the same schema as `infer/adapter.py`. Nothing else changes — `gate.py`, `compare/*`, `probe/*` all work.

**New analysis on predictions** → add to `compare/`.

**New analysis on weights** → add to `probe/`.

## Output convention

All eval output lands under `output/eval/<task>/<ds>/<tag>_<stamp>/` where `<tag>` is the adapter parent dir name (or model slug for OpenRouter). Same shape regardless of backend → any `compare/*` script works cross-backend.

RL eval lands under `output/eval/rl/<task>/<set>/<tag>_<split>_<stamp>/` (`predictions.jsonl` with `sample_id`, `results.jsonl` with `per_test: [{name, passed, expected?, actual?, error?}]`, `summary.json`); `<tag>` is `<run>-<stage>` for `output/adapter/<run>/<stage>/adapter`. It grades with the same `rl.graders` path as GRPO rewards.

## Revdev paired behavior evaluation

See [revdev/README.md](revdev/README.md) for frozen next-action/planning probes and live JacCoder rollouts comparing the trajectory base with the revdev adapter. Preserve command-policy denials separately from schema and functional correctness.
