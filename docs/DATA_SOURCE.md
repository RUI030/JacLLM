# Data Source
Where every dataset comes from, one row each. Formats and fields live in `DATASET.md`; per-set counts in each `statistic.json`.
Update this table whenever a dataset is added under `dataset/` or a new upstream is pulled into `dataset/raw/`.

Column meaning:
- **Upstream**: the original public/external origin (HF dataset, GitHub, docs). `?` = not verified yet.
- **Intermediate**: the file the set was actually built from (`meta.origin_file` in each record).
- **Producer**: the script that wrote the checked-in split.
- **Verification**: `meta.verification` of the records.

`dataset/raw/repo/` (gitignored) holds whole repos as `<group>/<name>/`, keyed `group/name` (`script/dataset/parser/repo.py:iter_repos`): `golden/` founder projects, `Rui/` own apps, `jaseci/` jaseci-labs apps (flowline, jms, this_is_jac), and `JacHack{SF,Spring,2026,A2Tech}/` hackathon repos (`<owner>__<repo>`). `raw/repo/meta.json` (jac-data-gen `repo_meta.py`) records size, Jac usage and the training whitelist per repo. Datasets built before this layout (rows below up to `Rui-toolcall-fim`) used flat `raw/repo/<name>/` and repo-name ids.

## Checked-in datasets
### CPT (`dataset/cpt/`)
| Dataset | Rows | Upstream | Intermediate | Producer | Verification | Added |
| --- | --- | --- | --- | --- | --- | --- |
| `Ayush-JacDocs-26Sept` | 253 | jaseci repo docs (`jac/jaclang/cli/docs/**`, commit `6e11b32`), chunked | — | external (Ayush), archived v1.2 | — | `19bd0d5` |
| `Nitin-composer-fn` | 14,220 | ? (likely MultiPL-T py2jac chain, see below) | jac-data-gen `composer_dataset.jsonl` | jac-data-gen `build_valid_training_data.py` | check + hidden tests | `c9bf4e5` |
| `Nitin-farm` | 1,558 | GitHub Beanie/ODMantic models → Jac node + CRUD walkers (LLM) | `farm_dataset.jsonl` | jac-data-gen | check + behavioral | `c9bf4e5` |
| `Nitin-jachacks` | 1,776 | Human-written Jac, 153 GitHub repos linked from JacHacks Devpost pages (no LLM) | `jachacks_all_jac_files_filtered.jsonl` | jac-data-gen | human | `c9bf4e5` |
| `Nitin-js2jac` | 2,620 | GitHub React/TSX repos → Jac (LLM idiomize) | `js2jac_dataset_idiomatic.jsonl` | jac-data-gen (first built by `script/dataset/sft/js2jac.py`, `96bc86b`) | check | `96bc86b` |
| `Nitin-osp` | 2,454 | OSP tasks; seeds from GitHub issues (`graph_targets/issues.jsonl`, 13,399) + LLM | `osp_merged_corpus.jsonl` (tier `legacy_test_verified`) | jac-data-gen | check + tests | `c9bf4e5` |
| `Nitin-osp-compile-only` | 5,157 | same as `Nitin-osp` | `osp_merged_corpus.jsonl` (tier `legacy_compile_only`) | jac-data-gen | check | `c9bf4e5` |
| `Rui-jacapp-4` | 119 | Own Jac apps in `dataset/raw/repo/` (ClaudeLogViewer, JacProjectFactory, flowline, jms, pm, pomodoro, this_is_jac) incl. their docs/skills | `dataset/raw/repo/` | `script/dataset/cpt/repo.py` | — | `2f05022` |

### SFT (`dataset/sft/<task>/`)
| Task / Dataset | Rows | Upstream | Intermediate | Producer | Verification | Added |
| --- | --- | --- | --- | --- | --- | --- |
| `code_completion/Nitin-composer-fn` | 11,478 | same as `cpt/Nitin-composer-fn` | `composer_dataset.jsonl` | jac-data-gen | check + hidden tests | `c9bf4e5` |
| `code_fix/Nitin-osp-repair` | 795 | OSP corpus, broken + `jac check` error → fix | `osp_repair/code_fix.jsonl` | jac-data-gen | check gate + test pass | `c9bf4e5` |
| `test_gen/Nitin-osp-repair` | 1,436 | OSP corpus, program → `test` suite | `osp_repair/test_fix.jsonl` | jac-data-gen | test pass | `c9bf4e5` |
| `farm/Nitin-farm` | 1,557 | same as `cpt/Nitin-farm` | `farm_dataset.jsonl` | jac-data-gen | check + behavioral | `c9bf4e5` |
| `js2jac/Nitin-js2jac` | 2,627 | same as `cpt/Nitin-js2jac` | `js2jac_dataset_idiomatic.jsonl` | jac-data-gen | check | `96bc86b` |
| `osp/Nitin-osp-merged` | 1,933 | same as `cpt/Nitin-osp` | `osp_merged_corpus.jsonl` | jac-data-gen | check + tests | `c9bf4e5` |
| `py2osp/Nitin-osp-lift-gold` | 325 | OSP lift: GitHub issue seeds → Python → OSP Jac | `osp_merged_corpus.jsonl` (tier `v21_gold`) | jac-data-gen | check + tests + elimination | `c9bf4e5` |
| `scaffold2impl/Rui-jacapp-scaffold` | 433 | same as `cpt/Rui-jacapp-4` | `dataset/raw/repo/` | `script/dataset/sft/scaffold2impl.py` | — | `ff19bd9` |
| `tool_fim/repo-all-pi` | 2,625 (2,481 train / 144 valid, valid = held-out files) | all 35 `raw/repo/` apps (whitelisted or not, minus `exclude_files`): one Jac body stubbed to `# TODO: implement`, synthesized pi trajectory rg → read → (rg + read cross-file symbols) → edit → `jac check \| tail`, real tool outputs; skips `::py::` bodies and files whose original fails `jac check` | `dataset/raw/trajectory/repo-all-pi.jsonl` (rows), `raw/repo/stats.json` (`script/dataset/repo_stats.py`) | `script/dataset/sft/tool_fim.py` | check (original file passes; tool results replayed byte-identical through pi 1.0.4) | — |

v1.3 sets (`c9bf4e5`) are filtered, deduped and eval-decontaminated (`eval_denylist`, `osp_holdout`); see `dataset/v13_SUMMARY.md`.

### RL (`dataset/rl/<task>/`)
| Task / Set | Tasks | Upstream | Producer | Verification | Added |
| --- | --- | --- | --- | --- | --- |
| `functions/spike-sample-20` | 20 (109 hidden tests) | Hand-written | manual | `solution.jac` passes `tests.jac` | `05d8bf9` |
| `functions/kodcode-1k` | 1,094 (9,065 hidden tests; 875/109/110) | `KodCode/KodCode-V1` train, 100 per subset (Docs 55, Package 39), no LLM; see `dataset/raw/hf/KodCode-V1/CONVERSION.md` | `script/dataset/rl/kodcode.py` | py2jac solution scores 1.0 via `rl.graders`; starter < 1.0 | |

## Raw inputs (`dataset/raw/`, gitignored)
| Path | Rows | Upstream | Used by |
| --- | --- | --- | --- |
| `jac/Nitin-9k-py2jac-idiom/py2jac_idiom.jsonl` | 8,615 | `nuprl/MultiPL-T` (Cassano et al. 2024; Python functions with tests, coverage ≥ 90%). Read as `nuprl/stack-dedup-python-testgen-starcoder-filter-v2` → `jac tool py2jac` → LLM idiomize → tests re-run (fallback to baseline) → `jac fmt` + ROUGE-L dedup. Nitin's release: `py2jac_dataset_idiomatic.jsonl` (9,371) | `cpt/file.py`, `sft/code_complete.py` (no checked-in output yet) |
| `jac/Nitin-3k-js2jac-idiom/js2jac_idiom.jsonl` | 3,002 | GitHub React/TSX repos (Nitin `scripts/js2jac_dataset/`) | `sft/js2jac.py` |
| `jac/Nitin-2k-farm/farm.jsonl` | 1,731 | GitHub Beanie/ODMantic models | `sft/farm.py` |
| `jac/Nitin-1k-osp/osp_dataset_pass.jsonl` | 1,034 | OSP, GitHub issue seeds | `sft/osp.py` |
| `jac/Nitin-jachack-all/jachack_all.jsonl` | 895 | JacHacks Devpost → GitHub | `cpt/file.py` |
| `agent-synth/sft_train.jsonl` | 9,608 | LLM-synthesized (Opus), routed by category | `sft/qa.py` (`opus-synth-v2`) |
| `markdown/jac-docs/` | 646 | Jac official docs | `cpt/file.py` |
| `markdown/jac-skills/` | 40 skills | jac-mcp skill files | `cpt/file.py` |
| `repo/*` | 7 repos | Own Jac apps | `cpt/repo.py`, `sft/scaffold2impl.py` |

Nitin's upstream release also has `golden_client.jsonl` / `golden_client2.jsonl` (LLM-generated from Jac docs and jaseci/jaclang source); not imported here. Per-file counts and generators: jac-data-gen `data/MANIFEST.md` §A–E, §Inputs.

## Candidate upstreams (not imported)
Conversion survey for KodCode: `dataset/raw/hf/KodCode-V1/CONVERSION.md` (gitignored, local only).
Downloaded with `hf download <repo> --repo-type dataset --local-dir dataset/raw/hf/<name>`; review sample with `script/dataset/sample_hf.py`.

| Source | Size | Format | License | Fit |
| --- | --- | --- | --- | --- |
| [`KodCode/KodCode-V1`](https://huggingface.co/datasets/KodCode/KodCode-V1) (imported: `rl/functions/kodcode-1k`) | 484K train + 3.3K `use_with_caution` (local: `dataset/raw/hf/KodCode-V1/`) | `question`, Python `solution`, pytest `test`, `test_info` (fn name/signature/docstring), `gpt_difficulty`, `subset` (12), `benchmark_similarity` | CC BY-NC 4.0 (non-commercial) | RL `functions`: convert solution + asserts to Jac, keep only rows whose `solution.jac` passes `jac test`. `Package`/`Docs` subsets need their pip packages in the grader env |
| [`nuprl/MultiPL-T`](https://huggingface.co/datasets/nuprl/MultiPL-T) | 133K Python fns | Python fn + tests (coverage ≥ 90%) | per-file (The Stack) | Already the py2jac upstream; remaining rows could also seed RL tasks |
