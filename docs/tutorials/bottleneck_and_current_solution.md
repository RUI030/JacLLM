# Bottlenecks and Current Solutions

> **In plain words.** Three things slow us down:
>
> 1. **Context length.** Agent sessions are far longer than what we can fit in one training example.
> 2. **Data generation.** Verified Jac data is slow and expensive to make.
> 3. **Iteration speed.** One train-and-test cycle takes about a day.
>
> The first one blocks progress on agent behaviour. Our main fix is a harness that breaks app-building into small, separate steps, so that each session is short. Unfamiliar terms are in the [glossary](glossary.md).

**Scenario: "build a todo app".**

- **With a general harness (pi).** One long session: the model reads files, writes, runs the compiler, fixes errors, and so on, for 80+ turns. The conversation grows past 200k tokens, the harness compacts old turns, and the model starts forgetting which files it already wrote. That whole session is one training example, and only a 16k–64k slice of it fits on our GPU.
- **With a layered harness (Jach).** The app is split into phases: plan, scaffold, write tests, implement each function, test the page. Each task gets a **fresh, short session**: "implement `add_todo` so these 3 tests pass", with only the files and hints that task needs. Each session fits in a few thousand tokens, and each one is a complete training example. The price is more sessions and more wall time per app.

---

## 1. Context length

### The problem

Agent trajectories are far longer than anything we can train on:

| What | Length | Source |
|---|---|---|
| JacHammer production sessions, largest request per session | median 125,531 tokens, max 474,763. Only 7 of 84 fit in 64k. | [report/weekly/1026.md](../../report/weekly/1026.md) |
| pi baseline, 9B on Jac apps, whole trajectory | median about 221k tokens, max about 444k. Compaction ran in 14 of 16 runs. | `Jach/runs/baseline/` session logs |
| pi baseline, 27B on Jac apps, whole trajectory | median about 92k tokens | same |
| Max trainable length, 9B on 48 GB | 65,536 | [report/weekly/1026.md](../../report/weekly/1026.md) |
| Max trainable length, 27B on 48 GB | about 22.5k–25k | `script/eval/probe/seq_mem.py` (results not checked in) |

So trajectories must be cut, and every way of cutting them hurts:

- **Truncation** drops the history that later turns depend on.
- **Chunking** makes the model edit files it never saw being created, which teaches it to hallucinate file paths and dependencies.
- **Most tokens in a long trajectory carry no loss anyway.** Only 7% of tokens in the production trajectory data were trained ([docs/DATA_AFTER_V135.md](../DATA_AFTER_V135.md)). In the JacBuilder debug pilot, 2 examples of about 41k tokens each held only 217 loss tokens in total; the rest was repeated system and skill text ([docs/JACBUILDER_DEBUG_PILOT_CLOSEOUT.md](../JACBUILDER_DEBUG_PILOT_CLOSEOUT.md)).
- **Long context also degrades the model at inference.** Models use information in the middle of a long context worst (Liu et al., TACL 2024).

The root cause is the harness. JacHammer/JacBuilder, the existing Jac app builder, is built for a large general model (Claude Sonnet by default). It sends about 16k tokens of fixed prompt (a system prompt of about 10k plus 27 tool schemas) and runs a ReAct loop of up to 100 iterations with no phase gating (`Jach/docs/research/existing-harnesses-and-model.md`). A small model cannot plan for itself in that setting, and the trajectories it produces are too long to train on.

### Short-term mitigation: sliding window

`script/dataset/sft/tool_use.py --window` cuts one trajectory into consecutive windows. Each window repeats the user prompt and keeps the recent context its turns need. This reduces path hallucination compared to independent chunks, but the overlap multiplies the tokens processed, so training is slow.

### Long-term solution: a custom, layered harness (Jach)

[Jach](https://github.com/RUI030/Jach) is a harness built for a small fine-tuned model. The harness owns the workflow instead of the model:

- **Layered SDLC with gates** (`Jach/docs/decisions/0004-sdlc-phases-and-gates.md`). The phases are Understand → Plan → Setup → Tests → Implement → Page test → E2E → Deliver. Planning, scaffolding and implementation are separate phases. The plan is written as real Jac declaration files checked with `jac check`, and tests are written before bodies and then frozen. The harness runs each gate itself; the model saying "done" never passes a gate.
- **Context resets at every task.** Failed turns are folded to one line (decisions 0005 and 0007).
- **Only the necessary prompt and hints.** The tool list changes per phase (4 to 15 tools). Jac knowledge is loaded on demand from the installed Jac version's guides, and a compiler error points to the guide to read (decisions 0006 and 0008). System prompt plus task card plus 4 tools comes to 939 tokens.

**Does it work?**

- **Pipeline test with Claude Haiku.** We ran Claude Haiku on Jach to check that the pipeline works end to end, and it does. Haiku used about **16k tokens per session** to solve a task, compared with pi, which was run with a 64k context and hit compaction in most runs. The trade-off is that each task is a smaller piece, so finishing a whole app takes **more sessions and more wall time**. (Team-reported; the Haiku run logs are not checked in.)
- **With the fine-tuned 9B,** the longest context across 33 Jach runs on 11 tasks was under 5,000 tokens (`Jach/docs/slides/new-harness.html`, `Jach/docs/research/level2-runs-2026-11-13.md`).

**Why a custom harness is necessary.** General harnesses assume a large model that plans by itself. For a small model, the harness has to give structure (phases, gates, small tool sets) and only the hints needed for the current step. Even if we later want the model to be harness-agnostic, it should at least follow a fixed SDLC (plan → scaffold → implement → verify), so that its trajectories stay short and each phase can be trained on separately.

**Data consequence.** Jach's run log is designed to be the trajectory training format (`Jach/docs/decisions/0012-run-log-format.md`). Short per-task trajectories fit the training window, and a small fixed prompt means a far larger fraction of each record carries loss. A shorter-trajectory dataset built this way is **in progress**. The harness core and the Implement phase are built; the Plan-as-declarations flow and the sample exporter are designed but not yet built.

---

## 2. Data generation

- **Verified data is expensive.** Each record goes through an LLM call plus `jac check` and tests, and many attempts fail the gates. Repair traces recycle those failures as debugging data (see [data_preparation.md](data_preparation.md)), but agentic data still needs a teacher run per trajectory.
- **Long-horizon data hardly exists.** App-building trajectories come from teacher agents: revdev has 97 accepted trajectories, and the JacBuilder pilot has 2 episodes. Most of each one is context with no loss.
- **The Jac version moves.** Data is gated on Jac 0.36.1 (the JacBuilder pilot used 0.34.28). A language update can invalidate data or skills.
- **RL tasks need test benches.** KodCode prescreening took 75 min for 7,000 samples ([report/v1.3RL/kod-result.md](../../report/v1.3RL/kod-result.md)).

- **The model is too weak for RL on apps.** On held-out app tasks the 9B scored pass@4 = 0, so GRPO gets no signal.

**What we are doing:**
- Use the **teacher loop** (Claude Opus takes over when the student is stuck), which gives correct debugging actions to learn from; a new set of this data has just been produced in jac-data-gen for the next training round (see [training_methods.md](training_methods.md#4-teacher-loop-when-grpo-has-no-signal)).
- Reuse harvested repair traces; produce short per-task trajectories from Jach instead of full-app sessions; screen RL tasks to the mixed-pass band so no rollouts are wasted.

---

## 3. Iteration speed

| Step | Time | Source |
|---|---|---|
| 27B CPT (82 steps, 16k) | about 4 h | `logs/qwen27b-timeline.log` |
| 27B SFT (103 steps, 16k) | about 5.4 h (stopped at step 90) | same |
| 27B Nitin eval (972 problems) | 77–103 min | same |
| 9B v1.3 CPT | 2 h 10 m – 3 h 49 m | [report/v1.3/v13_report.md](../../report/v1.3/v13_report.md) |
| GRPO spike, 50 steps on the 5080 | 4 h 32 m, about 98% generation | [report/v1.3RL/v13rl_report.md](../../report/v1.3RL/v13rl_report.md) |
| GRPO KodCode, 1 epoch | about 15 h (planned 8 h) | [report/v1.3RL/grpo-kodcode.md](../../report/v1.3RL/grpo-kodcode.md) |
| HF eval, unmerged adapter | about 30 s per sample | [docs/CLOUD_GPU.md](../CLOUD_GPU.md) |

One CPT → SFT → eval cycle on the 27B takes about a full day on one GPU, and only one job can run at a time on the shared server.

**What we are doing:**

- **Packing**, which cut one SFT from about 6.5 h to about 80 min on the PRO 6000.
- **Spike recipes**, i.e. short smoke runs (`dev-cpt-spike.yaml`, `dev-sft-spike.yaml`) before full runs.
- **GGUF serving for eval** through llama.cpp, at about 5 samples/s with 16 parallel requests, instead of HF generation.
- **Shorter trajectories from Jach**, which make each step faster as well as more useful.

## References

- Liu, N. F. et al. "Lost in the Middle: How Language Models Use Long Contexts." TACL 12, 157–173 (2024). https://aclanthology.org/2024.tacl-1.9/
