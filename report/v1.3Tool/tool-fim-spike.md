# Tool-Use Fill-in-the-Middle on SFTv1.3: Spike Results

October 15, 2026

**Goal:** teach SFTv1.3 (`0926-v13-A`) to work as a coding agent inside the pi harness: find a stubbed Jac function in a real repo, read the code around it, fill the body with the `edit` tool and run `jac check`. One overnight run, as a demo, not a tuned recipe.

**Result:** on 144 held-out tasks run through the real pi agent, the task is solved 71.5% of the time, against 43.1% for SFTv1.3. The new model has a new failure: when an edit or `jac check` fails, it often retries the same call in a loop (22 of 144 runs used 50 or more tool calls, none of them solved). The training data has no failed steps, so the model never saw a recovery; the next step is real agent session logs that include failed attempts and their fixes.

---

## 1. Data

### Source

All 35 apps under `dataset/raw/repo/` (founder projects, own apps, jaseci-labs apps and hackathon repos). Codebase statistics from `script/dataset/repo_stats.py` (`dataset/raw/repo/stats.json`):

| | count |
|---|---:|
| Jac files | 1,117 |
| Jac lines | 213,189 |
| Function and ability bodies | 6,229 |
| Bodies that use a symbol defined in another file | 2,510 |

### How a row is built

Producer: `script/dataset/sft/tool_fim.py`. Output: `dataset/sft/tool_fim/repo-all-pi/`.

1. Pick a Jac body of 2 to 60 lines (bodies inside `::py::` blocks are skipped) and replace it with `# TODO: implement`. At most 16 bodies per file.
2. Write the trajectory a pi agent would take, running every tool for real on the stubbed copy, so every tool result is the actual output:
   - `rg` to locate the file, only when the prompt does not name it,
   - `read` the file,
   - `rg` and `read` for up to 2 symbols from other files that the body uses,
   - `edit` with the stub as old text and the original body as new text,
   - `jac check <file> 2>&1 | tail -n 3`,
   - a one-line reply.
3. The system prompt and tool schemas are pi 1.0.4's own, captured from a real pi request (`script/dataset/trajectory/harness/pi.json`).
4. A file whose original version fails `jac check` is dropped (355 files, listed in `rejected.jsonl`).

The format and three rendered rows are in `docs/DATASET.md`, section "Tool FIM".

### Variants (train split)

| Variant | Prompt | Rows | Rows with a lookup in another file |
|---|---|---:|---:|
| Path given | names the file and the function | 1,843 | 386 |
| No path | names only the function; the trajectory starts with `rg` | 607 | 117 |
| Several holes | 2 or 3 stubs in one file, one `edit` call | 31 | — |

### Split

| | rows | files | repos | tokens |
|---|---:|---:|---:|---:|
| train | 2,481 | 518 | 34 | 7,439,265 |
| valid | 144 | 26 | 12 | 430,962 |

Tokens are counted with the Ornith tokenizer on the full chat template, including the system prompt and tool schemas (`meta.tokens`). The median train row is 2,826 tokens; the longest is 6,537.

The split is by file: no valid file appears in train. All 12 valid repos also have other files in train, so this measures new files in familiar projects, not new projects.

---

## 2. Training

| | |
|---|---|
| Start | SFTv1.3 adapter (`output/adapter/0926-v13-A/sft/adapter`), continued |
| Data | `tool_fim/repo-all-pi` train only, no replay of the v1.3 data |
| LoRA | r64, alpha 16, rsLoRA, all linear layers (same as SFTv1.3) |
| Optimizer | lr 2e-4, linear decay, warmup 10, adamw_8bit |
| Batch | 1 × gradient accumulation 10 |
| Length | max 8,192 tokens |
| Epochs | 2 = 498 steps |
| Time | 9,042 s (2 h 31 min) on the RTX 5080, about 18 s per step |

Recipe and launcher: `script/train/recipe/1015-toolfim-v13A/`. The launcher also merges the adapter into bf16, converts it to GGUF Q8_0 and runs both evals.

### Loss on model output only

Every assistant turn is trained: the reply text, the tool call and the end-of-turn token. The system prompt, tool schemas, user prompt and tool results are masked. This was checked by building the real trainer on train rows and decoding which tokens of a batch carry loss. Unsloth ignores packing for Ornith (it logs "packing=True ignored (hybrid linear-attention model)"), so each row is trained on its own with the labels built in `script/train/sft.py:tokenize_with_assistant_mask`.

Every assistant turn in the data has an empty thinking block (`<think>\n\n</think>`), so the model is trained to act without reasoning first.

### Training loss

| step | epoch | loss |
|---:|---:|---:|
| 10 | 0.04 | 0.350 |
| 100 | 0.40 | 0.194 |
| 240 | 0.97 | 0.154 |
| 260 | 1.04 | 0.078 |
| 490 | 1.97 | 0.055 |

The loss halves right at the epoch boundary and stays near 0.06 for all of epoch 2 (mean 0.067). That drop at the moment rows repeat suggests the second epoch mostly memorized the training rows. Held-out loss was not measured and the epoch-1 checkpoint (`checkpoint-200`, the closest saved one) was not evaluated, so whether epoch 2 helped or hurt is open.

Log: `output/adapter/1015-toolfim-v13A/sft/checkpoint-498/trainer_state.json`.

---

## 3. Evaluation

### Setup

Each of the 144 valid tasks runs in a fresh copy of its repo with the stub in place. The real pi agent (1.0.4) runs with the same flags as the captured system prompt (no MCP, no context files, no skills, no extensions, no prompt templates). The model is served by llama-server as GGUF Q8_0, 4 tasks in parallel, 24,576 tokens of context per task, 600 s limit per task.

Metrics (`script/eval/tool_fim/run_eval.py`):

| Metric | Meaning |
|---|---|
| Solved | the stub is gone and `jac check` passes on the file |
| Stub left | `# TODO: implement` is still in the file |
| Edited the file | the agent called `edit` or `write` on the task file |
| Exact | the file is byte-identical to the original |
| Similarity | difflib ratio between the filled function and the original one |

"Solved" means the code compiles and type-checks. It does not run the code, so a solved task can still be wrong.

### Results (144 tasks)

| | SFTv1.3 | tool FIM model |
|---|---:|---:|
| Solved | 43.1% | **71.5%** |
| Stub left | 47.9% | 15.3% |
| Edited the file | 53.5% | 90.3% |
| Exact | 11.1% | 22.9% |
| Mean similarity | 0.476 | 0.629 |
| Median tool calls | 6 | 4 |
| Runs with 50 or more tool calls | 5 | 22 |
| Median time per task | 38.8 s | 11.4 s |
| Timed out | 1 | 0 |

The median of 4 tool calls matches the training trajectories (read, edit, check, and sometimes one search).

### Per task

| | tasks |
|---|---:|
| Solved by both | 46 |
| Solved only by the tool FIM model | 57 |
| Solved only by SFTv1.3 | 16 |
| Solved by neither | 25 |

### How SFTv1.3 fails (82 tasks)

| | tasks |
|---|---:|
| Never edited; wrote the code in its reply instead | 55 |
| Never edited; context overflow (requests of 24.6k to 53k tokens) | 6 |
| Never edited; other (stopped without code, or hit the output limit) | 6 |
| Edited, but `jac check` fails | 13 |
| Edited, stub still in the file | 2 |

SFTv1.3 mostly answers as a chat model: it reasons in its thinking block and prints the function in a code block without calling `edit`. 17 of its runs made no tool call at all.

### How the tool FIM model fails (41 tasks)

| | tasks |
|---|---:|
| Edited, but `jac check` fails | 19 |
| Edited the wrong file, stub untouched | 11 |
| Stub still in the file after edits to the right file | 8 |
| Never edited; other (context overflow, output limit, stopped) | 3 |

The 11 wrong-file runs, from the transcripts:

| Cause | runs | example |
|---|---:|---|
| The stub is in an `impl` file and the model edited the declaration in the main file | 3 | stub in `services/pulse.impl.jac`, model edited the `def _miles(...) -> float;` line in `services/pulse.jac` |
| Another file defines a function with the same name | 3 | stub in `raylib_shooter/web/main.jac`, model edited `raylib_shooter/shooter.jac` |
| Dropped the leading folder of the path | 4 | `littlex/components/ui/dialog.jac` edited as `components/ui/dialog.jac` |
| Edited an unrelated file | 1 | stub in `jac/walkers/health_check.jac`, model edited `jac/walkers/cover.jac` |

### Loops after a failure

All 22 runs with 50 or more tool calls failed (the longest made 267 calls). In those runs:

| | runs |
|---|---:|
| At least one `jac check` failed | 16 |
| 5 or more `edit` calls failed (old text not found, or the replacement changed nothing) | 16 |
| The same call, with the same arguments, was repeated 20 or more times | 16 |
| No `edit` call succeeded | 6 |

Over all 144 runs, 22 saw a failing `jac check`; only 3 of them ended solved and 16 turned into loops. Every train row ends with a passing `jac check` and contains no failed edit (checked over all 2,481 rows), so the model has seen how to finish a task but never how to recover from a failed step. The repeated calls are mostly the same `rg` search over and over.

### Why the edits fail

The first edit of a run is usually fine. The failures come from the retries after something went wrong.

| | SFTv1.3 | tool FIM model |
|---|---:|---:|
| `edit` calls | 137 | 504 |
| Failed `edit` calls | 34 (25%) | 345 (68%) |
| Runs whose first `edit` failed | 11 of 77 | 15 of 141 |

The 345 failed edits of the tool FIM model, by cause:

| Cause | calls | runs |
|---|---:|---:|
| The old text is code that is not in the file (written from memory, not copied from the file) | 186 | 16 |
| The old text and the new text are identical (a "fix" that rewrites the same body) | 99 | 17 |
| The old text is the `# TODO: implement` stub, which an earlier edit had already replaced | 56 | 5 |
| The old text is the stub, but does not match the file | 4 | 1 |

After a failed edit, 196 of the 345 times (57%) the next 2 calls did not `read` the file again.

Each failure matches a habit from the training rows, where every `edit` replaces the stub with the full correct body and the file is never read after an edit:

- the old text is always the stub, so the model keeps trying to replace a stub that is gone;
- the new text is always the correct full body, so a retry writes that body again, unchanged;
- no row reads the file after an edit, so retries write the old text from memory.

So the loops come mainly from data coverage: the training rows never reach a state after a failure, and in that state the model repeats the one edit it knows. The second epoch may make this more rigid, but this run cannot separate the two; evaluating `checkpoint-200` would.

---

## 4. Next steps

1. **Real session logs instead of only synthesized tasks.** The synthesized rows have clean prompts, one perfect edit and no failure, which is what the model failed to generalize from. Real agent sessions from JacHammer users (`dataset/raw/session/`) have vague or badly written prompts, multi-step diffs, failed edits, failing checks and the attempts that fixed them. The current export only has the file-changing calls (`edit_code`, `write_code`, `delete_code`) and a final summary per turn; the `read_file`, `list_files`, `jac_check` and `jac_docs` calls and their results are missing, so a full export has been requested before these can become trajectories.
2. **Deduplicate the session logs.** The current export (1,103 conversations) has repeats:

   | | count |
   |---|---:|
   | Conversations identical to another one | 42 |
   | Conversations whose first prompt repeats another conversation's | 237 (70 distinct prompts) |
   | User messages sent twice in a row with the same text | 73 of 674 back-to-back user messages |
   | Successful code changes that repeat another change exactly | 1,416 of 21,545 |

   Repeated starter prompts (for example "Build a full-stack expense tracker with user accounts, categories, and a dashboard", 19 times) come from templates and suggested prompts, so deduplication should look at the whole conversation, not only the first prompt.
3. **Keep failed steps in context, without training on them.** Instead of dropping failed attempts, keep them in the conversation and give their assistant turns weight 0, so the model is trained on the recovery that follows the failure but not on the mistake. `script/train/sft.py` already supports this (`weight: 0`). Published work supports learning from failures:
   - SWE-Lego keeps the full trajectory and masks the loss on agent responses that caused tool errors, found by regular expressions on the terminal output; this alone gave about 2 points on SWE-bench Verified.
   - Step Rejection Fine-Tuning (JetBrains) uses a critic model to grade each step, masks the loss on wrong steps but keeps them in context, and keeps unresolved trajectories: 3.7% gain on SWE-bench Verified against 2.4% for keeping only successful trajectories.
   - Agent-R builds training data by cutting a failed trajectory at its first error and joining it to a correct continuation, so the model learns to notice and correct its own mistakes.
   - Negative-Aware Training trains on failed trajectories too, marked with a prefix that tells the model it is a failure, and reports gains over training on successes only.

   A synthetic version is also possible for the tool FIM data: a wrong first body from a real model run, its real `jac check` output, a `read`, then the correct edit.
4. **Wrong-file cases in the producer.** For bodies in an `impl` file, look the symbol up so the search hits both the declaration and the `impl`, and make the trajectory read the `impl`. For names defined in several files, make the trajectory pick the file named in the prompt.
5. **Epochs.** Evaluate `checkpoint-200` against the final model, or train 1 epoch, to see whether epoch 2 helps.
6. **Harder split.** Hold out whole repos, not only files, to measure projects the model has never seen.
7. **Behavior, not only compile.** Add tests or run checks for a subset of tasks, since "solved" only means the file compiles.
8. **Thinking.** All training turns have an empty thinking block because there is no good reasoning data yet. Real agent trajectories with their reasoning (for example a full JacHammer export with tool calls and results) should go into training once available.

## Reproduce

```bash
python script/dataset/sft/tool_fim.py
setsid nohup bash script/train/recipe/1015-toolfim-v13A/run.sh > logs/1015-toolfim-v13A.log 2>&1 < /dev/null &
bash script/eval/tool_fim/serve_eval.sh <model.gguf> <tag>          # eval alone
```

To run the trained model by hand in pi, use `--no-mcp -nc` so the system prompt matches the training data:

```bash
~/.unsloth/llama.cpp/build/bin/llama-server -m output/model/JacLLM-SFT-Ornith-9B-toolfim-spike_GGUF/JacLLM-SFT-Ornith-9B-toolfim-spike-Q8_0.gguf --jinja -ngl 99 -c 24576 --alias local --port 8080
PI_CODING_AGENT_DIR=output/eval/tool_fim/repo-all-pi/toolfim-spike_10-15_04-18/pi_agent pi --no-mcp -nc --model local/local
```

## Data

| | path |
|---|---|
| Dataset | `dataset/sft/tool_fim/repo-all-pi/` |
| Codebase statistics | `dataset/raw/repo/stats.json` |
| Adapter and checkpoints | `output/adapter/1015-toolfim-v13A/sft/` |
| Merged model, bf16 | `output/model/JacLLM-SFT-Ornith-9B-toolfim-spike-bf16/` |
| GGUF Q8_0 | `output/model/JacLLM-SFT-Ornith-9B-toolfim-spike_GGUF/` |
| Eval, tool FIM model | `output/eval/tool_fim/repo-all-pi/toolfim-spike_10-15_04-18/` |
| Eval, SFTv1.3 | `output/eval/tool_fim/repo-all-pi/v13A_10-15_04-55/` |
| Run log | `logs/1015-toolfim-v13A.log` |

Each eval folder has `report.json`, `results.jsonl` (one row per task) and `transcripts/` (the full pi event stream per task).

Sources: [SWE-Lego](https://arxiv.org/abs/2601.01426), [Step Rejection Fine-Tuning](https://arxiv.org/abs/2605.10674), [Agent-R](https://arxiv.org/abs/2501.11425), [Negative-Aware Training](https://arxiv.org/abs/2402.11651) (NAACL 2025).
