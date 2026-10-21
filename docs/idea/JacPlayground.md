# JacPlayground — single-turn Jac coding sandbox

## Motivation

`JacProjectFactory` is a great product/dataset-gen tool and a great eval harness (see [Factory4Eval.md](Factory4Eval.md)), but it's the wrong shape for RL:
- Multi-turn (6+ LLM calls per rollout)
- 10 min/rollout on Ornith → GRPO math doesn't work
- Full repo build is inherently multi-file / multi-turn — can't be squeezed one-shot

RL algorithms (GRPO, PPO, DPO with reward model, rejection sampling) all want the same thing: **single prompt → single completion → cheap scalar reward → gradient update**. That's a different tool.

`JacPlayground` is that tool. LeetCode-for-Jac: a task bank of single-turn Jac coding problems, each with a deterministic gate, wrapped in a stateless verifier. Factory continues to own repo-level; Playground owns unit-level.

## Scope split (this doc vs Factory)

| Tool | Task shape | Rollout time | Native use |
|---|---|---|---|
| **JacPlayground** | Single file, one prompt, one reply | Seconds | RL training, unit eval, quick smoke |
| **JacProjectFactory** | Multi-file repo, many phases | ~10 min | Repo-level eval, dataset generation |

Common ground (extract as shared lib later): `jac check` / `jac run` / `jac test` wrappers already live at `JacLLM/script/utils/jac_cli.py`. Playground reuses those.

## Layout (proposed)

```
JacPlayground/
├── tasks/                        # frozen task bank
│   ├── 001_fizzbuzz/
│   │   ├── spec.md              # problem statement → becomes the prompt
│   │   ├── signature.jac        # optional: skeleton the model fills in
│   │   ├── tests.jac            # hidden test file (gate)
│   │   └── meta.yaml            # class: function/graph/osp/fullstack, difficulty, tags
│   ├── 002_walker_traverse/
│   ├── 003_graph_shortest_path/
│   └── ...
├── verifier.py                   # (task, completion) -> {reward, breakdown}
├── task_loader.py                # sample_task(filter=...) / list_tasks()
├── prompt_builder.py             # spec + signature -> chat messages
├── README.md
└── tests/                        # verifier unit tests
```

Add later, only if needed: `serve.py` (HTTP wrapper so training scripts on other machines can call), `datasets/` (task-to-JSONL exporter for offline batch scoring).

## Task record (canonical shape)

Each task folder is one atomic unit. `meta.yaml`:

```yaml
id: 001_fizzbuzz
class: function                  # function | graph | osp | fullstack
difficulty: 1                    # 1..5
tags: [control_flow, arithmetic]
timeout_seconds: 10              # per grade() call
```

`spec.md` is Markdown; the prompt builder wraps it in the chat template. `signature.jac` is optional — if present, prompt says "fill in the body". If absent, model writes the whole file.

`tests.jac` is a Jac test file that `jac test` runs against the merged source. Test failures = partial credit, test passes = full credit.

## Verifier API

```python
# verifier.py
from dataclasses import dataclass
from utils.jac_cli import check as jac_check, test as jac_test  # reuse JacLLM's

@dataclass
class GradeResult:
    reward: float          # 0.0..1.0
    phase: str             # "no_block" | "check_fail" | "test_fail" | "pass"
    check_ok: bool
    tests_pass: int
    tests_total: int
    stderr: str            # truncated

def grade(task, completion: str) -> GradeResult:
    src = build_source(task, completion)         # merge signature + completion
    if src is None:
        return GradeResult(0.0, "no_block", False, 0, 0, "no code block found")
    ok, err = jac_check(src)
    if not ok:
        return GradeResult(0.0, "check_fail", False, 0, 0, err[:500])
    passed, total, err = jac_test(src, task.tests_path)
    reward = passed / total if total else 0.0
    phase = "pass" if reward == 1.0 else "test_fail"
    return GradeResult(reward, phase, True, passed, total, err[:500])
```

Reward shaping starts simple: `passed / total`. Add bonuses later (execution time, code length, style checks) only when the plain ratio stops discriminating.

## Prompt builder

```python
# prompt_builder.py
def build_messages(task) -> list[dict]:
    user_content = task.spec_md
    if task.signature:
        user_content += "\n\nFill in the body of the following signature. Return only the completed Jac code in a ```jac ... ``` block.\n\n"
        user_content += f"```jac\n{task.signature}\n```"
    else:
        user_content += "\n\nReturn only the Jac source in a ```jac ... ``` block."
    return [{"role": "user", "content": user_content}]
```

No system prompt in v1. If model needs help with Jac syntax, prepend a small skill preamble (mirror Factory's "skills preload" idea, but stripped down).

## Task-bank seeding

30–100 tasks for v1, spanning the four classes so eval slices by class carry weight:

- **Source: Nitin-10k-jac-functions** — pick 20 with clear signatures, add tests
- **Source: Ayush-ground-truth example snippets** — pick 20 that are self-contained
- **Source: Factory harvest output** — slice `marketplace/` repos into single-file functions where possible
- **Hand-written**: 20 covering graph traversal, walker patterns, fullstack endpoints (the parts Nitin doesn't cover)

Class distribution target: 30% function, 30% graph, 25% osp, 15% fullstack.

Each task must have (a) a spec humans understand, (b) tests that fail on a stub and pass on the golden solution. Write the golden solution first, run tests against it, then delete the golden.

## Consumers

Three drivers hit the verifier through the same API:

1. **Offline rejection-sampling loop** — batch N completions per task, keep top-K by reward, dump as SFT JSONL
2. **GRPO trainer** — `reward_funcs=[lambda task, c: verifier.grade(task, c).reward]` fed to `UnslothGRPOTrainer`
3. **Eval driver** — sweep tasks × model checkpoints, dump CSV like `gate.py` does

Playground doesn't own any of these — they live in `JacLLM/script/train/` and `JacLLM/script/eval/`. Playground is a library + task bank.

## What Playground is NOT

- **Not a REPL / web sandbox** — no live editor, no user-facing UI. The name is aspirational; content is a task bank + grader
- **Not multi-file** — one completion, one file, one gate. Multi-file is Factory's job
- **Not multi-turn** — no dialogue, no clarification, no repair loop. One shot. Failure = 0
- **Not for HTTP/server tasks** — `jac start` needs env + boot time. Fullstack tasks in Playground stop at "walker + endpoint decl compiles and passes `jac check`". Actual HTTP smoke is Factory territory
- **Not a Factory replacement** — they cover different task shapes. Both exist

## Rollout plan

1. **Skeleton** — Playground repo, `verifier.py`, `task_loader.py`, `prompt_builder.py`, 3 hand-written tasks (one function, one graph, one walker). Verify grade() works on stub + golden solutions
2. **First 30 tasks** — mine Nitin + Ayush, class-balanced. Golden + tests for each
3. **Eval driver** — sweep script that runs current SFT checkpoint over all tasks, dumps CSV. Sanity check the pass-rate gradient across checkpoints matches loss.py
4. **Rejection-sampling loop** — batch generate N=8 per task, filter by reward, produce new SFT JSONL. First real "RL-lite" cycle
5. **GRPO integration** — `UnslothGRPOTrainer` with verifier as reward. Small run (100 tasks × 200 steps) on one strong task class to prove machinery works

## Open questions

- **Where does Playground live** — sibling repo (`JacLLM/JacPlayground/`) mirroring Factory, or subfolder inside JacLLM (`JacLLM/playground/`)? Sibling if we want other repos to depend on it; subfolder if it stays JacLLM-internal. Leaning sibling for cleanliness
- **Golden solutions**: keep them in-repo (under `tasks/<id>/golden.jac`, gitignored during eval), or archive elsewhere? In-repo is convenient but risks leakage into training data
- **Test isolation**: if two tasks import overlapping identifiers, tempfile handling matters. Prob just run each grade() in its own tempdir
- **Task rotation for GRPO**: sample uniformly, weight by difficulty, or curriculum (easy → hard)? Start uniform, revisit after first GRPO run
- **Should we add HTTP tasks** using Factory's `jac_start_http_check`? Yes eventually, but only after basic tasks work — HTTP adds boot time and flakiness

## Bottom line

JacPlayground = the shape RL wants. Factory = the shape products want. Two tools, one shared jac-cli utility library. Build Playground when you're ready to do rejection sampling or GRPO — not before, since bare SFT doesn't need it.
