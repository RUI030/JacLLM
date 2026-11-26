# Training Methods: CPT, SFT, GRPO

> **In plain words.** There are three ways to teach the model, and they differ in what data they need:
>
> - **CPT:** "read a lot of Jac". It needs only raw text.
> - **SFT:** "here is a question and the right answer". It needs input/answer pairs.
> - **GRPO:** "try several times; we tell you which attempt was better". It needs only a way to score attempts.
>
> We run them in that order. Unfamiliar terms are in the [glossary](glossary.md).

| | CPT | SFT | GRPO (RL) |
|---|---|---|---|
| Data needed | Raw text (docs, code) | (input, correct output) pairs | Tasks plus a grader. No answers needed. |
| What gets learned from | Every token | Only the answer tokens | The model's own attempts, weighted by score |
| Teaches | What the language looks like | How to respond to a request | Which of its own solutions are good |
| Cost | Cheapest per token | Cheap | Expensive: many attempts plus grading per step |
| Code | `script/train/cpt.py` | `script/train/sft.py` | `script/train/grpo.py` |

Each stage continues from the previous stage's adapter. For example, `script/train/recipe/1123-qwen27b-r32/sft.yaml` loads `output/adapter/1123-qwen27b-r32/cpt/adapter`.

---

## 1. CPT: continued pretraining

### What it is

CPT is the most basic kind of training. The model reads text and, at every position, tries to predict the next token. **Every single token** is used to adjust the weights. There is no "question" and no "answer", just text.

### When to use it

Use CPT when you have an **unlabeled corpus**: lots of text in the domain, but nobody has written down what the right response to anything is. CPT lets the model learn the overall distribution of the language itself: its syntax, keywords, common patterns, library names, and how a project is laid out.

**Scenario.** Jac is new, so the base model has barely seen it. It writes Python-looking code with `def` and indentation where Jac needs braces and `;`, and it has never seen a `walker`. Before we can ask it to do tasks in Jac, it must first *read* a lot of Jac. That reading is CPT.

Continued pretraining on unlabeled in-domain text is an established way to adapt a model to a new domain (Gururangan et al., ACL 2020). That study used encoder models on classification, so for a code LLM it is an analogy rather than a proof.

### What we use for code: docs and repositories

**Example 1: a file-level record** (`script/dataset/cpt/file.py`). One Jac file per record, with a header saying where it came from. The whole thing is training text.

**Example 2: a repo-level record** (`script/dataset/cpt/repo.py`, real excerpt from `dataset/cpt/Rui-jacapp-5`). Several files from the **same repository** are packed together, so the model sees how they relate:

```jac
# repo: this_is_jac

# file: components/GraphView.jac
"""A small framed panel that embeds the runtime's Jac Graph Visualizer..."""
import from "lucide-react" { Waypoints, ArrowUpRight }
def:pub GraphView(refreshKey: int = 0) -> JsxElement { ... }

# file: components/HeroSection.jac
"""Landing hero: the pitch, an install line, ..."""
import from "lucide-react" { ArrowDown, Terminal }
import from .ui.button { Button }
import from .CodeBlock { CodeBlock }
def:pub HeroSection -> JsxElement { ... }
```

### Why cross-file context matters

In a real project, files import each other. `HeroSection.jac` above imports `Button` from `.ui.button`. If the model only ever sees files one at a time, it never learns what is *in* `ui/button.jac`. When it later writes code, it has to **guess** module paths and names, and it hallucinates imports that do not exist.

Peer-reviewed results back the idea that giving a code model the related files helps:

- Without repository context, code models hallucinate identifiers. Supplying that context raises compile rate and correct identifier use (Agrawal et al., NeurIPS 2023; this is a decoding-time method, not training).
- Training a code model on in-file plus cross-file context together improves exact match and identifier match (Ding et al., CoCoMIC, LREC-COLING 2024).
- More generally, pretraining on groups of related documents improves how a model uses context (Shi et al., ICLR 2024).

### What `repo.py` does today

- **File order.** Files of a repo are packed in **sorted path order**, in chunks of about 4k tokens. Oversized `.jac` files are split at top-level declarations.
- **No dangling imports.** A repo whose imports point at files we do not have is **excluded** (`EXCLUDED_REPOS` in `script/dataset/parser/repo.py`), so the model is never shown an import to a file it never sees.
- **Next step: dependency order.** Ordering files so that each imported file comes *before* the files that import it is a possible next step. It already exists for the revdev SFT tasks (`write_order` in `script/dataset/revdev/tasks.py`). No peer-reviewed study measures this for CPT, so it is an engineering choice.

---

## 2. SFT: supervised fine-tuning (instruction fine-tuning)

### What it is

Each training example is **instruction → response**: given messages **X**, the model is trained to respond with **Y**.

- **X** (system prompt, user request, tool results) is what the model *sees*. It has **loss weight 0**: the model reads it but is not graded on it.
- **Y** (the assistant reply) has **loss weight 1**: this is what the model learns to produce.

Because the data is shaped as "instruction → response", SFT is also called **instruction fine-tuning** (Wei et al., ICLR 2022; Ouyang et al., NeurIPS 2022). The masking is `tokenize_with_assistant_mask` in `script/train/sft.py`.

**Example: code completion** (real record from `dataset/sft/code_completion/Nitin-composer-fn-nofence`):

```text
[system]    You are a helpful assistant.                                   ← weight 0
[user]      Write the Jac function described by the comment(s) below.      ← weight 0
            Reply with just the code.
            """Validate a boolean parameter and return its fixed string form."""
            def verify_bool_parameter(bool_param: bool | None) -> str | None {
[assistant] """Validate a boolean parameter and return its fixed string form."""   ← weight 1
            def verify_bool_parameter(bool_param: bool | None) -> str | None {
                match bool_param {
                    case None:  return None;
                    case True:  return "true";
                    case False: return "false";
                    case _: raise ValueError(...);
                }
            }
```

The model is never trained to *write* the user's request. It is trained only to write the answer, given the request.

### Scenario A: how should the model respond?

Given a user prompt or a harness message, what should the model do? Reply with code, reply with text, or make a tool call? SFT teaches this directly. Our tasks:

| Task | X (input) | Y (target) |
|---|---|---|
| code_completion | signature + docstring | function body |
| js2jac / py2osp | React or Python code | equivalent Jac |
| osp | a description of a graph problem | a Jac program with nodes and walkers |
| scaffold2impl | an app skeleton with empty bodies | the filled-in implementation |
| tool_fim | an agent session so far (tool calls and results) | the next tool call, e.g. `edit` then `jac check` |

### Scenario B: debugging

The same format teaches the model what to do *after* something goes wrong. Make the **bad attempt plus the compiler or test feedback the input**, and the **correct fix the target**. The model learns the right debugging action, not just how to write code from scratch.

**Example** (real record from `dataset/sft/code_fix/Nitin-osp-repair-nofence`, shortened):

````text
[user]  Here is my Jac code and the error it produces. Please fix the program.  ← weight 0
        Task: a hiker walker that travels a trail of waypoints and counts stops...
        ```jac
        walker Hiker {
            can walk with Waypoint entry {
                ...
                if self.stops >= self.target { ...; disengage; }
                visit [-->];
            }
        }
        ```
        Compiler error:
        walker ability does not `visit` after a typed entry
[assistant]  <the full corrected program>                                         ← weight 1
````

These pairs are harvested from real failures during data generation: the failed attempt, the real `jac check` or `jac test` error, and the attempt that finally passed. Execution feedback does help models repair code (Chen et al., ICLR 2024). That paper studied prompting, not training; here it supports why the error message is a useful input.

### A cost to know about

Weight-0 tokens are not learned from, but the GPU still has to process them. In the current 27B SFT run, 16.6M tokens are *seen* but only 8.5M (51%) are *trained*. For long agent sessions it is much worse: only 7% of tokens in the production trajectory data carried loss ([docs/DATA_AFTER_V135.md](../DATA_AFTER_V135.md), doc only). This is a big part of why context length is our main bottleneck ([bottleneck_and_current_solution.md](bottleneck_and_current_solution.md)).

---

## 3. GRPO: reinforcement learning with a grader

### What it is

For each task, the model writes **8 attempts** (a "group"). A grader scores each one. Each attempt is then compared with **its own group's average**:

- An attempt that scored above the average is reinforced, so it becomes more likely.
- An attempt that scored below the average is discouraged.

There is no "correct answer" anywhere. There is only a score.

**Worked example.** Task: implement `balanced_brackets(s)` (real task, `dataset/rl/functions/spike-sample-20`). The grader gives reward = fraction of hidden tests passed (0 if it does not compile).

| Attempt | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Reward | 1.0 | 1.0 | 0.5 | 0 | 1.0 | 0 | 0.5 | 1.0 |
| Advantage | +0.90 | +0.90 | −0.30 | −1.51 | +0.90 | −1.51 | −0.30 | +0.90 |

Group mean = 0.625 and standard deviation ≈ 0.41. Advantage = (reward − mean) / std. The fully passing attempts are pushed up, and the ones that failed to compile are pushed down. This is the formula in the GRPO section of Guo et al., *Nature* 2025:

A_i = (r_i − mean(r_1..r_G)) / std(r_1..r_G)

**Why all-pass or all-fail teaches nothing.** If all 8 attempts score 1.0, the mean is 1.0 and every advantage is (1.0 − 1.0) / 0 → 0. The same happens if all 8 score 0. There is nothing to prefer, so there is **no learning signal**.

### When to use it

Use RL when all three hold:

1. **There are no labels, but there is a good grader.** Example: we have test benches for 1,000 functions, but nobody has written reference solutions.
2. **The model can already do it, just not reliably.** RL sharpens an existing ability; it does not teach a new one. So the model must first learn Jac through CPT and SFT.
3. **The tasks are "sometimes pass, sometimes fail".** We pre-screen tasks with `script/eval/rl/run_eval.py --emit-split`, which keeps only tasks where 0 < passes < 8.
   - In our preflight, 504 of 972 Nitin problems were in this mixed band ([report/v1.3RL/v13rl_report.md](../../report/v1.3RL/v13rl_report.md)).
   - During training, easy tasks became all-pass after about 38 steps and stopped giving signal (same report).

### The cost: it is slow

Every step needs 8 attempts per task plus grading:

- **The 50-step spike** on an RTX 5080 took 4 h 32 m, and about 98% of that was the model generating attempts ([v13rl_report.md](../../report/v1.3RL/v13rl_report.md)).
- **The KodCode run** took about 550 s per step against a 284 s estimate, and about 15 h instead of 8 h ([report/v1.3RL/grpo-kodcode.md](../../report/v1.3RL/grpo-kodcode.md)).

### What we have seen so far

- **Spike** (`0930-grpo-functions-spike`, 14 train tasks). Train pass@1 went from 37.5% to 50.9%, and dev (3 tasks) from 25.0% to 45.8%. The 972-problem Nitin suite did not change (56.3% → 56.9%, McNemar p = 0.29, not significant). So GRPO did not overfit, but it did not transfer either.
- **KodCode** (`1005-grpo-kodcode-r64`, 180 tasks, 1 epoch). Dev went from 38.3% to 39.7%, which is within noise. The RL update was only about 0.46% of the size of the SFT update, so it was under-trained.

---

## Which method fits which data

| You have… | Use | Example in this project |
|---|---|---|
| Docs, source repos, any raw Jac | CPT | `dataset/cpt/*` (docs, JacHacks repos, our app repos) |
| Input → known-good output | SFT | code completion, py2jac, js2jac, OSP, scaffold2impl |
| Failed attempt + compiler or test error → fix | SFT (debugging format) | `code_fix`, `test_gen` |
| Agent session (tool calls + results) | SFT on the assistant turns | `tool_fim`, `revdev`, `jacbuilder` |
| Tasks + tests, no answers, model passes sometimes | GRPO | `dataset/rl/functions/{spike-sample-20, kodcode-1k}` |

## References

- Gururangan, S. et al. "Don't Stop Pretraining: Adapt Language Models to Domains and Tasks." ACL 2020. https://aclanthology.org/2020.acl-main.740/
- Agrawal, L. A. et al. "Monitor-Guided Decoding of Code LMs with Static Analysis of Repository Context." NeurIPS 2023. https://papers.nips.cc/paper_files/paper/2023/hash/662b1774ba8845fc1fa3d1fc0177ceeb-Abstract-Conference.html
- Ding, Y. et al. "CoCoMIC: Code Completion by Jointly Modeling In-file and Cross-file Context." LREC-COLING 2024. https://aclanthology.org/2024.lrec-main.305/
- Shi, W. et al. "In-Context Pretraining: Language Modeling Beyond Document Boundaries." ICLR 2024. https://iclr.cc/virtual/2024/poster/18861
- Wei, J. et al. "Finetuned Language Models Are Zero-Shot Learners." ICLR 2022. https://openreview.net/forum?id=gEZrGCozdqR
- Ouyang, L. et al. "Training Language Models to Follow Instructions with Human Feedback." NeurIPS 2022. https://papers.neurips.cc/paper_files/paper/2022/file/b1efde53be364a73914f58805a001731-Paper-Conference.pdf
- Chen, X. et al. "Teaching Large Language Models to Self-Debug." ICLR 2024. https://proceedings.iclr.cc/paper_files/paper/2024/file/2460396f2d0d421885997dd1612ac56b-Paper-Conference.pdf
- Guo, D. et al. "DeepSeek-R1 incentivizes reasoning in LLMs through reinforcement learning." *Nature* 645, 633–638 (2025). https://doi.org/10.1038/s41586-025-09422-z
