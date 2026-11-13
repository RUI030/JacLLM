# JacBuilder debug SFT smoke and evaluation baseline

Date: 2026-10-30. This is a one-step training-path test, not a claim of debugging improvement.

## Input and preflight

`dataset/sft/jacbuilder/debug-pilot-v2-projected/train.jsonl` contains two approved Teacher edit rows from one import-typo family, 50,437 rendered tokens total and 217 active target tokens. The original v1 and external raw trajectory archive remain unchanged. `training-collator-preflight.json` in the v2 directory records executed CPU agreement between the actual VLM collator and text SFT helper: both rows have identical input IDs and loss masks, with 25,131/25,306 tokens and 108/109 active labels. A 32,768-token limit fits both without truncation.

## Bounded GPU execution

The exact launcher and requested configuration are retained under `output/adapter/jacbuilder-debug-v2-smoke-20261030T030539Z/`. It invoked the existing `train/sft_img.py:run_sft_img` with the local m7 merged VLM base and its local chat template, 4-bit loading, language LoRA rank 8, batch size 1, gradient accumulation 1, learning rate 1e-5, and `max_steps=1`. It ran inside a user systemd scope with `MemoryMax=14G`, `MemorySwapMax=0` and a 600-second process timeout. No dependency was installed, model server stopped, or training recipe changed.

**Observed:** exit 0, one optimizer step, `train_loss=0.018578609`, `grad_norm=0.417394`, no skipped rows, and approximately 41.9 seconds of Trainer runtime. The adapter and checkpoint were saved. The adapter has 256 LoRA tensors; all 128 B tensors have nonzero values after the update. Its weight-file SHA256 is `2fdeab549df3cb6c0740d103545ed2e63556a50d582170caf7afced0f18d131e`. This confirms a parameter update, not that both records were seen: with one step and batch size one, only one of the two rows contributes to this run.

During the run, a sampled GPU observation showed 45,313 MiB used across both processes, leaving 3,174 MiB free; the training process accounted for 22,054 MiB and the pre-existing llama-server for 23,234 MiB. After exit, GPU usage returned to 23,252 MiB and the server remained running. These are sampled values, not a proven worst-case capacity margin. The host swap was nearly full during loading, so larger batches or contexts need separate resource planning.

## Evaluation state

The existing m7 `todo_stage1` JacCoder run at `output/eval/agent/todo_stage1/jaccoder-JacLLM-Ornith-9B-prod-img-sft-m7_10-28_07-51/run.json` is a **historical reference**, not a controlled paired baseline for this adapter. It records 0/1 stages passed, 36 model calls and a final `FAILED_ERROR` from max-token exhaustion after 886.67 seconds. The scenario is disjoint from the import-typo training family, but the historical run does not record a checkpoint tensor hash. A fair base-versus-adapter evaluation must rerun both with pinned prompts, harness, sampling, model identity and independent task checks.

The one-step adapter is retained for plumbing inspection only. It is not approved as a production model or evidence of corrected path hallucinations, read offsets, full-app construction or general debugging. Before an informative FT comparison, collect varied independently verified target actions and create a family-disjoint evaluation set. Teacher prompts and Student deployment prompts differ; the current rows train a Teacher action in a Teacher-context request. Any Student-target export must prove the corrective action is grounded in the Student-visible context and compatible with its tool schema.
