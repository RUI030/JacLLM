# Factory4Eval — repurposing JacProjectFactory as a repo-level eval

## Motivation

Current JacLLM eval only has:
- `loss.py` — forward NLL per checkpoint (proxy signal; low is nice, doesn't prove anything)
- `gate.py` — `jac check` pass rate on SFT valid split (single-file, syntax-level)

Neither answers **"can this adapter actually build a working Jac project?"** That's the real product question, and it's exactly what JacProjectFactory (sibling repo, `../JacProjectFactory/`) already does end-to-end:

- Scaffold → Design → Model → Endpoints → Tests → Smoke (HTTP 200) → Harvest
- Bucket routing = natural pass/fail signal:
  - `marketplace/` = all gates passed
  - `repaircenter/` = failed at Tests/Smoke (partial credit)
  - `archived/` = failed at Model phase (couldn't even write valid code)

Factory is currently biased toward *dataset generation* (heavy prompt scaffolding + preloaded skills so a weak local model can still succeed). For eval we want the opposite: measure the model's *own* ability, controlled and comparable across adapters.

## Do NOT fork

Every prompt/skill change would need to sync — maintenance trap. Instead: **add an `EVAL_LEVEL` flag inside Factory** that swaps prompts/skills/retries.

## Three eval levels

| Level | Skills preloaded | Prompt style | Repair retries per phase |
|---|---|---|---|
| `full`  (current)   | on  | full (hints, patterns, examples) | 3 |
| `skills_only`       | on  | thin (task + acceptance criteria only) | 1 |
| `naked`             | off | skeleton (one-line task, gate rule) | 0 |

- `full` = matches production / dataset-gen conditions
- `skills_only` = "given the docs, can you figure it out"
- `naked` = pure model capability, no crutches

## What to change in Factory

Concrete edits (paths relative to `JacProjectFactory/`):

1. **`factory/config.py`** (or wherever run-config lives): add
   ```python
   EVAL_LEVEL: Literal["full", "skills_only", "naked"] = "full"
   ```
   plus `MAX_REPAIRS_BY_LEVEL = {"full": 3, "skills_only": 1, "naked": 0}`.

2. **Prompt templates**: for each phase (`model_task_first`, `endpoints_task_first`, `tests_task_first`, repair variants), define `..._full` / `..._thin` / `..._skeleton`. Selector reads `EVAL_LEVEL`.

3. **Skill preload site**: gate the `preload_skills(...)` call on `EVAL_LEVEL != "naked"`.

4. **Repair loop**: replace hardcoded max-retries with `MAX_REPAIRS_BY_LEVEL[EVAL_LEVEL]`.

5. **Trajectory metadata**: dump `eval_level` alongside phase timings into `.factory/meta.json` so every harvested repo carries the eval condition.

## What Factory doesn't have yet (add for eval use)

### Fixed spec suite
A frozen set of 3–5 specs covering the taxonomy, each run under a fixed random seed. Proposal — new folder `factory/eval_specs/`:

- `01_function/` — pure function library (no graph, no HTTP)
- `02_graph/` — node/edge model + walker traversal, no HTTP
- `03_osp/` — walker with `spawn root`, no HTTP
- `04_fullstack_min/` — 1 walker endpoint + 1 test
- `05_fullstack_full/` — 3 endpoints + tests + smoke

Each spec is one `customer/specs/<name>/` folder frozen in git. `EVAL_SPECS` in config lists them.

### Metrics dumper
After a batch, roll up per-adapter results into a single CSV: `output/eval/factory/<adapter_tag>.csv`

Columns per row (one row per spec):
- `spec`, `bucket`, `phase_completed`, `total_llm_seconds`
- `model_retries`, `endpoints_retries`, `tests_retries`, `smoke_retries`
- `n_files`, `n_walkers`, `n_endpoints` (harvest-time only, else null)

Second CSV `output/eval/factory/summary.csv` aggregates per adapter: pass rate, mean LLM time, retry totals.

### Batch runner
Runs `EVAL_LEVEL × spec × adapter` matrix. Serial for now (single 5080), one at a time. Just a driver script that swaps the adapter server endpoint between runs.

## Adapter serving

Per Factory README: `unsloth start claude` runs the local server, Factory hits it via `claude -p`.

For eval-mode batch, need a way to swap adapters between runs. Simplest: script kills the unsloth server, starts a new one pointing at the next adapter path, waits for health, then invokes Factory. Factory itself stays adapter-agnostic — sees only the OpenAI-compatible endpoint.

## Suggested rollout

1. Land `EVAL_LEVEL` flag with all three levels wired — no new specs yet, just verify existing pipeline still works with `full`.
2. Add 2 fixed specs first (`01_function`, `04_fullstack_min`). Run one adapter at all 3 levels — sanity check the difficulty gradient shows up.
3. Add metrics dumper. Run baseline (base Ornith, no adapter) at all levels.
4. Once one trained CPT adapter exists that beats baseline on `gate.py`, run it through Factory-eval as first real comparison.
5. Add remaining specs. Wire batch runner if there are ≥3 adapters to compare.

## Open questions

- **Time budget**: `full` level ran ~10 min/spec on Ornith. `naked` will retry-cap fast so probably faster. Still, 5 specs × 3 levels × N adapters gets slow. Do we accept overnight batches, or trim to 1 level for routine eval and 3 levels only for milestone comparisons?
- **Non-determinism**: even with fixed seed, claude-p and jac test may have variance. Do we run each cell N=3 and report median, or accept single-shot?
- **Where does the CSV live** — in JacLLM's `output/eval/factory/` (this repo's convention) or in `JacProjectFactory/output/`? Argument for JacLLM side: eval belongs to the trainee, not the harness.
- **Naked-mode fairness**: with 0 retries and no skills, base Ornith will likely score 0/5. That's fine as a floor, but the gradient between adapters may be invisible at this level until models get much better — might want to defer `naked` until adapters are stronger.

---

## Beyond eval: Factory as RL/GRPO reward source

Longer-term thought — Factory's deterministic gates (`jac check`, `jac test`, HTTP 200) are the exact shape RL wants: scalar, non-hackable, rich. The question comes up: can Factory drive GRPO?

### GRPO 30-second recap

1. One prompt → sample N completions from current policy (N=4~16)
2. Reward each completion (scalar)
3. Group-relative advantage: `adv_i = reward_i − mean(rewards)`
4. Policy gradient: raise logprob of above-mean completions, lower below-mean; KL-anchor to reference model
5. Loop

Assumption baked in: **rollouts cheap (seconds), reward cheap, one prompt → one completion (single-turn), logprobs of sampled tokens captured**.

### Where Factory fits and where it breaks

| Requirement | Factory today | Verdict |
|---|---|---|
| Scalar reward | bucket → {1.0, 0.5, 0.0}, phase weights optional | ✓ |
| Non-hackable | jaclang tools, deterministic | ✓ perfect |
| Rich signal | per-phase pass/fail + retry count | ✓ better than human labels |
| Rollout latency | **~10 min/spec** on Ornith | ✗✗✗ |
| Logprob capture | claude-p subprocess, tokens lost | ✗ |
| Single-turn | 6+ LLM calls per repo | ✗ multi-turn |

### The rollout-cost math

N=8, batch=4, 1000 steps = 32k rollouts × 10 min = **~222 days on one 5080**. Minimal N=4/batch=1/200 steps = 5.5 days. Not viable on current hardware.

### Architectural inversion required

Today — Factory is the boss, model is a tool. RL — training script is the boss, Factory is a stateless verifier:

```python
for step in range(N_STEPS):
    tasks = factory.sample_tasks(batch_size=4)
    for task in tasks:
        completions = model.generate(task.prompt, n=8)
        rewards = [factory.grade(task, c) for c in completions]
        adv = rewards - rewards.mean()
        loss = -(logprobs * adv).mean() + KL_COEF * kl_div(model, ref_model)
        loss.backward(); optimizer.step()
```

Factory would need to expose:
- **Verifier-only API** — `factory.grade(task_spec, completion)` that skips FSM/repair/harvest
- **Task distribution** — phase-level tasks, not whole-repo runs
- **Statelessness / parallelism** — tmp sandbox per rollout, no shared `.work/`
- **Batched scoring** — score N=8 in one call, not sequential subprocess

FSM / dataset-gen path stays; RL path is a new module alongside.

### Multi-turn is hard mode

Factory is inherently multi-turn (many claude-p calls). GRPO assumes one prompt → one completion. Options:

| Option | Difficulty | Rollout speed | Signal preserved |
|---|---|---|---|
| **A. One-shot** — collapse phase into single prompt/reply, gate | ★ standard | seconds | medium |
| **B. Multi-turn, terminal reward only** — dialogue kept, reward at end, tool outputs masked | ★★★ | tens of seconds | high |
| **C. Turn-level reward** — `jac check` after every turn | ★★★★ | medium | highest |
| **D. Full agent RL** — Factory-as-env, rollout = whole repo | ★★★★★ | 10 min | complete but untrainable |

B/C require: custom trainer fork (mask non-policy tokens from loss, KL only on policy-generated), replay collector, careful memory (100k–200k tokens per multi-turn rollout × N stored logprobs).

Field state: single-turn GRPO is mainstream. Multi-turn agent RL exists (DeepSeek R1-Zero style) but is not turnkey — no `UnslothGRPOTrainer(multi_turn=True)`.

### Three realistic paths, ordered by pain

1. **Offline rejection sampling** — no RL infra
   - Batch-sample N completions per task, score with Factory, keep top-K as new SFT positives
   - Retrain SFT on filtered pool. "Reward-labeled data augmentation"
   - Captures ~90% of Factory's value; no gradient RL
   - **Recommended first once SFT plateaus**

2. **Single-turn GRPO on one phase** — real RL, feasible
   - Extract one Factory phase (e.g. Endpoints) as `(spec) → (walker code)`
   - Reward = `jac check` + `jac test`
   - unsloth `UnslothGRPOTrainer` accepts `reward_funcs` callable
   - Rollouts are seconds
   - **Recommended once (1) shows Factory-graded rejection has real gain**

3. **Multi-turn agent RL on full trajectories** — research territory
   - Fork trainer, custom collator, custom KL masking
   - Only if (1) and (2) hit ceilings AND you rent 8×H100 for weeks
   - Not on roadmap

### Bottom line

Factory is a **fantastic verifier**, a **very expensive rollout environment**. For eval it's ideal (rest of this doc). For RL, extract the verifier, drop the FSM, train on single-turn phase tasks. Full Factory pipeline stays as eval harness + dataset generator — its native jobs.

## What NOT to do

- Don't copy Factory into JacLLM. Two repos, one pipeline, one truth.
- Don't add eval-only code paths that bypass real gates. If a gate is too strict for eval, weaken it globally (with justification) — never fork the gate.
- Don't tune Factory's prompts to make a specific adapter look better. Prompts stay frozen; only the model changes.
