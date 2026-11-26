# Data Preparation

> **In plain words.** Almost no Jac exists on the internet, so we have to **make** training data. The basic method:
>
> 1. Take code that exists in other languages (Python functions, React apps, database models).
> 2. Convert it to Jac.
> 3. Have an LLM polish the result.
> 4. Keep it only if the Jac compiler and the tests accept it.
>
> Every failed attempt is also kept, as "here is broken code and its error → here is the fix" data. This file covers which datasets exist, how they are made, and how much of training each one accounts for. Unfamiliar terms are in the [glossary](glossary.md).

**Example of one record's life.** This is a Python function from the MultiPL-T corpus:

1. `jac tool py2jac` converts it automatically. The result compiles, but reads like Python: this is the **floor**.
2. An LLM (`composer-2.5`) rewrites it in natural Jac style, using for example `match`/`case` and braces: this is **idiomize**.
3. `jac check` and the hidden tests run on the rewrite. If they pass, the rewrite is kept. If not, the floor version is kept.
4. The result becomes **two** training records:
   - a CPT record: just the code, as reading material;
   - an SFT record: "docstring + signature → body", shown in [training_methods.md](training_methods.md#2-sft-supervised-fine-tuning-instruction-fine-tuning).

## Data flow

```
jac-data-gen data/*.jsonl  ─┐
our own Jac app repos       ├─> dataset/raw/ (gitignored)
Jac docs, JacHacks repos   ─┘        │
                                     ▼  producer in script/dataset/{cpt,sft,rl}/
              dataset/cpt/<ds>/train.jsonl          {"text": ...}
              dataset/sft/<task>/<ds>/{train,valid}.jsonl   {"messages": [...]}
              dataset/rl/<task>/<set>/                tasks + hidden tests
                                     │
                                     ▼  recipe (script/train/recipe/*)
                                 training
```

Every producer follows the same shape: `# Setting` / `# Functions` / `# Run` sections, then the shared `script/dataset/pipeline.py`. Every record carries a `meta` block with `source, format, class, fp`, plus `task_type` for SFT.

## How jac-data-gen produces data

[chess10kp/jac-data-gen](https://github.com/chess10kp/jac-data-gen) (checked at commit `2c0640e`, 2026-11-05):

1. **Deterministic floor first.** `jac tool py2jac` for Python, a js2jac converter for React/TSX, `mongo_odm_to_jac` for Beanie/ODMantic models. The output compiles but reads like Python or JS.
2. **One LLM "idiomize" pass.** It rewrites the floor into idiomatic Jac. The default model is `composer-2.5` via cursor-agent. OSP synthesis uses several backends: minimax-m3, composer-2.5, gpt-5.6-luna and glm-5.3-flash. Every call is logged in `data/run_ledger.sqlite3`.
3. **Verification gates.** `jac check`, then `jac test` plus hidden tests, behavioural or ORM persistence gates, and hollowness checks. If a rewrite fails its guard, the record falls back to the floor. Everything runs on **Jac 0.36.1** in a sandbox with a 3 GB memory cap.
4. **Repair-trace harvest, at zero extra generation cost.** Every failed attempt plus its real compiler or test error, paired with the attempt that finally passed, becomes debugging data (`osp_repair/{code_fix, test_fix}`).

## Dataset inventory

### CPT (`dataset/cpt/`)

| Dataset | Rows | Content | How made | Verified by |
|---|---:|---|---|---|
| Ayush-JacDocs-26Sept | 253 | Jac docs (jaseci `jac/jaclang/cli/docs/**`), chunked | scraped, no LLM | none |
| Nitin-composer-fn | 14,220 | Python functions (MultiPL-T) → Jac | floor + composer idiomize (8,579 idiomatic / 5,641 floor) | check + hidden tests |
| Nitin-js2jac | 2,620 | GitHub React/TSX → Jac | js2jac converter + LLM cleanup + repair | check |
| Nitin-farm | 1,558 | Beanie/ODMantic models → Jac nodes + CRUD walkers | converter + composer | check + round-trip |
| Nitin-jachacks | 1,776 | human-written Jac from 153 JacHacks repos | scraped, no LLM | human-written |
| Nitin-osp | 2,454 | object-spatial programs from GitHub-issue seeds | multi-model synthesis | check + tests |
| Nitin-osp-compile-only | 5,157 | same corpus, compile-only tier | multi-model synthesis | check only. Used only in the v1.3-B ablation. |
| Rui-jacapp-5 | 999 | 28 of our own Jac apps, repo-level packing | `script/dataset/cpt/repo.py` | partial repos excluded |

### SFT (`dataset/sft/<task>/`)

| Task / dataset | Rows (train/valid) | X (input) → Y (target) | Verified by |
|---|---:|---|---|
| code_completion / Nitin-composer-fn | 11,478 / 0 | signature + docstring → body | check + hidden tests |
| js2jac / Nitin-js2jac | 2,627 / 0 | React/TSX → Jac | check |
| farm / Nitin-farm | 1,557 / 0 | ODM model → Jac node + walkers | check + behavioural |
| osp / Nitin-osp-merged | 1,933 / 0 | task → OSP Jac program | check + tests |
| py2osp / Nitin-osp-lift-gold | 325 / 0 | Python → OSP Jac (graph-native rewrite) | check + tests + elimination |
| code_fix / Nitin-osp-repair | 795 / 0 | broken code + real `jac check` error → fix | check + test pass |
| test_gen / Nitin-osp-repair | 1,436 / 0 | broken tests → passing tests | test pass |
| scaffold2impl / Rui-jacapp-scaffold | 801 / 200 | app scaffold (declarations) → implementation | none. Taken from working apps, no LLM. |
| tool_fim / repo-all-pi | 2,481 / 144 | synthesized pi trajectory (rg → read → edit → `jac check`) filling one stubbed body | real tool outputs |
| revdev / accepted-dedup | 97 | reverse-developed app-building trajectories, Claude CLI teacher | accepted by review |
| jacbuilder / debug-pilot-* | 2 | JacBuilder debug episodes, Opus teacher | pilot only |
| no_image / synthetic-v1 | 54 / 6 | templated synthetic | not used in any recorded run |

**`-nofence` variants.** The 27B run uses `-nofence` copies of the 8 main SFT sets. In every reply that was a single fenced block, the ```` ``` ```` fence is removed, leaving bare code, so the target matches the eval prompt, which asks for no fence (`script/eval/Nitin-test/run_eval.py`). Overall 3,096 replies were unfenced, and 23 replies that mix prose and code were left as they were.

### Teacher-loop data (full-stack app debugging)

Made by the teacher loop described in [training_methods.md](training_methods.md#4-teacher-loop-when-grpo-has-no-signal): our model builds an app, and Claude Opus takes over whenever it is stuck. The source is 45 app tasks (41 train, 4 held out), paraphrased from open-source GitHub repos across 8 categories: graph, algorithms, state-machine game, permissions, realtime, LLM, non-web and frontend. The output lives in `output/spike/1105-teacher-intervention/sft/` (not under `dataset/`).

| Set | What | Size | Used in |
|---|---|---|---|
| trajectories | whole episodes; teacher turns weight 1 | 122 episodes, 514 takeovers, 76 accepted | 1106b, 1107 |
| mined_fixes | file that failed `jac check` → its later fix | part of `seg2_mined_injected` (up to 495 rows) | 1106b, 1107 |
| injected_bugs | accepted files broken the way the student got stuck → fix | 644 rows for batch 4 | 1106b, 1107 |

Source: [report/weekly/1114.md](../../report/weekly/1114.md) §5, [docs/TEACHER_INTERVENTION.md](../TEACHER_INTERVENTION.md).

There is a known flaw: the early supervisor accepted 10 web episodes on static checks, but only 1 of them worked in a real browser. Treat accepted web episodes from before the browser check as suspect.

**New data for the next round.** A new set of teacher-loop data has just been produced in [jac-data-gen](https://github.com/chess10kp/jac-data-gen). It will be used for the next round of training (team-reported; not yet in a recipe).

### RL (`dataset/rl/functions/`)

| Set | Tasks (train/dev/test) | Hidden tests | Source |
|---|---|---:|---|
| spike-sample-20 | 20 (14/3/3) | 109 | hand-written |
| kodcode-1k | 1,094 (875/109/110) | 9,065 | KodCode-V1 train, converted and screened, no LLM |

## Token share in training

**Seen vs trained, in one example.** In the code-completion record shown in [training_methods.md](training_methods.md#2-sft-supervised-fine-tuning-instruction-fine-tuning):

- **Input (weight 0).** The system prompt plus the request and signature: 54 tokens, plus a few chat-template tokens. The model reads it but is not graded on it.
- **Answer (weight 1).** The function body: 112 tokens. This is what the model learns from.

These are counted with the Qwen3.8-27B tokenizer. So the model *sees* about 170 tokens but is *trained* on about 115. For a translation task, the input is a whole React file and the answer is a similar-sized Jac file, so less than half of what is seen is trained. The tables below add this up for each dataset.

How the counts were made:

- **Tokenizer.** Each recipe's own tokenizer: Qwen3.8-27B for `1123`, Ornith for `v135`.
- **CPT.** Seen = trained = every token, truncated at `max_seq_length`.
- **SFT.** **Seen** = the full rendered conversation (X + Y). **Trained** = assistant tokens with loss weight 1 (Y only), using the same masking code as `script/train/sft.py`.
- **Sampling.** Recipes use `sequential` mixing, 1 epoch, and no reweighting, so each dataset's share is just its token count.
- **Cross-check.** Row counts match `logs/cpt.log` and `logs/sft.log`.

Numbers are for the current recipe, `1123-qwen27b-r32`. Do not use `statistic.json` token totals: they are stale for the rewritten sets and missing for `-nofence`.

### CPT (max_seq 16,384)

| # | Dataset | Rows | Tokens (trained = seen) | Share |
|---|---|---:|---:|---:|
| 1 | Ayush-JacDocs-26Sept | 253 | 710,118 | 5.4% |
| 2 | Nitin-composer-fn | 14,220 | 1,940,347 | 14.7% |
| 3 | Nitin-js2jac | 2,620 | 830,102 | 6.3% |
| 4 | Nitin-farm | 1,558 | 1,056,259 | 8.0% |
| 5 | Nitin-jachacks | 1,776 | 3,011,233 | 22.8% |
| 6 | Nitin-osp | 2,454 | 2,787,855 | 21.1% |
| 7 | Rui-jacapp-5 | 999 | 2,881,379 | 21.8% |
| | **Total** | 23,880 | **13.2M** | |

20 documents were truncated at 16k (19 from jachacks). At v135's 4k CPT length, 294 were truncated.

### SFT (max_seq 16,384, no rows truncated)

| # | Task / dataset | Rows | Seen (all) | Seen % | Trained (weight 1) | Trained % | Trained / seen |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | code_completion / composer-fn | 11,478 | 2,942,457 | 17.7% | 1,437,271 | 17.0% | 0.49 |
| 2 | js2jac | 2,627 | 1,992,697 | 12.0% | 746,321 | 8.8% | 0.37 |
| 3 | farm | 1,557 | 1,164,980 | 7.0% | 296,857 | 3.5% | 0.25 |
| 4 | osp | 1,933 | 2,224,899 | 13.4% | 1,291,845 | 15.3% | 0.58 |
| 5 | py2osp | 325 | 578,811 | 3.5% | 323,288 | 3.8% | 0.56 |
| 6 | code_fix | 795 | 1,733,091 | 10.4% | 604,604 | 7.1% | 0.35 |
| 7 | test_gen | 1,436 | 2,794,556 | 16.8% | 1,595,384 | 18.8% | 0.57 |
| 8 | scaffold2impl (train + valid) | 1,001 | 3,159,009 | 19.0% | 2,168,791 | 25.6% | 0.69 |
| | **Total** | 21,152 | **16.6M** | | **8.5M** | | 0.51 |

How to read the gap between seen and trained:

- **Translation and repair tasks have long inputs** (the source code, or the broken code plus the error), so only 25–37% of their tokens carry loss. js2jac, for example, is 12.0% of what the model sees but only 8.8% of what it learns from.
- **scaffold2impl has short inputs and long outputs**, so it is the largest share of learning signal (25.6%).
- The v135 SFT (Ornith tokenizer, fenced originals) had nearly identical trained shares: 15.8M seen and 8.5M trained.

## Known data issues

1. **The nofence system prompts contradict their replies.** In the `-nofence` copies, 3,096 rows still have the "chat interface" system prompt that asks for a ```` ```jac ```` block, but the reply is now bare. These are the roughly 15% `chat_style` rows from `pipeline.py`'s `FENCE_RATIO`. They should be switched to the plain prompt pool, or the fence kept for those rows.
2. **The nofence producer is not in the repo.** The script that made the `-nofence` copies was a session-local script. It should be committed under `script/dataset/sft/`.
3. **The Qwen3.8 chat template adds a system preamble.** With `chat_template: null`, every SFT row gets a "Reasoning effort is set to xhigh" preamble (about 38 tokens) and an empty `<think>` block inside the trained span. The model learns to answer an "xhigh reasoning" prompt with no thinking. Check that eval renders prompts the same way.
4. **There is no held-out SFT data in the 27B run.** `split: [train, valid]` loads scaffold2impl's 200 valid rows into training, and the other sets have no valid split.
5. **Stale docs.** `docs/DATA_SOURCE.md` lists older row counts and omits Rui-jacapp-5. `report/sft_dataset_stats.md` describes the v1.2 sets, which are no longer used.
