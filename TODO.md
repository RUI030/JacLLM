[ ] compare original ornith capability (any stack) with finetuned model with jac
[ ] tool-use fim training 
[ ] read AST report
[ ] Full stack app eval

- [ ] Establish LLM-as-judge standard for semantic failure-mode categorization
    - [ ] Rubric file — fixed category list with definitions + 1-2 examples each
    - [ ] Per-case prompt template (in: prefix/python/reference/completion/failing-test names; out: JSON `{category, secondary, one_line_reason}`)
    - [ ] `llm_judge.py` driver — loops failed cases, calls judge model (Claude API or byllm), writes `judge.jsonl` + aggregate counts
    - [ ] Dual-judge agreement check on a small sample to measure rubric stability
    - [ ] Seed rubric from the ad-hoc subagent run on `sft_test_09-13_17-28`- [ ] GRPO rollout speed (10-06 run: grading 1.6% of wall time; generation ~30 s/completion in GRPO vs ~1 s in `run_eval.py`)
    - [ ] standalone script: time HF generate on the GRPO training model (4-bit + unmerged LoRA, batch 8, grad-ckpt/train mode) vs merged inference path (batch 32), same prompts
    - [ ] isolate the cause: unmerged LoRA, train mode / Unsloth GRPO wrapper, KV cache, batch size, missing fla fast path
    - [ ] check Unsloth `fast_inference=True` (vLLM) support for Ornith/Qwen3.5
- [ ] next GRPO run: constant LR (done in grpo.py), more prompts/step (grad_acc 8), epsilon_high 0.28, temperature 1.0, completion cap from reference lengths, 10-step timing run first
