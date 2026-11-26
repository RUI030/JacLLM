[ ] compare original ornith capability (any stack) with finetuned model with jac
[x] tool-use fim training
[x] read AST report
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

- [ ] Prod trajectory SFT (`script/dataset/trajectory/clean.py`, rules in `dataset/raw/prod/sft/prod-64k/RULES.md`)
    - [ ] Prune tool-call records instead of dropping whole oldest messages when a row is over the cap: drop or stub tool calls/results that carry nothing the later turn needs (e.g. a read superseded by a later read or write of the same file, stale `preview_status`, long command output), so more turns fit per row
        - [ ] The grounding check (G) must run on the pruned row: a pruned read may be what a later edit relied on
        - [ ] Mark a pruned result with a harness-style stub (e.g. `[output omitted]`) so the model does not learn that a call returned nothing
        - [ ] Re-run the packing simulation (scratch `pack_sim.py`, policy B: group consecutive turns, fill the rest with history) on top of pruning; compare total tokens, trainable tokens and G masks with the current set
    - [ ] Response labeling: give every assistant response a label instead of only weight 0/1
        - [ ] Label set (English in code and data): `harmful` (rejected edit, Jac errors, flailing, invalid args, unverified claim, answer on a broken app), `redundant` (repeated read-only call, re-read after a clean write, sleep, restart of a healthy preview), `useful` (everything else), plus the rule ids that fired
        - [ ] SFT weight from label (harmful/redundant 0, useful 1); keep labels in `meta` so RL reward functions can reuse them (see `dataset/raw/prod/badhabit.md` reward table)
        - [ ] Decide whether `redundant` calls are deleted (as D1/D2 now) or kept as context with weight 0
