# Teacher intervention spike: findings and changes

Log for `script/spike/1105 Teacher Intervention/` (how to run it is in its README). Outputs are under
`output/spike/1105-teacher-intervention/`. Newest first.

## 2026-11-07: scratch files, archive, batch 5

**Path leaks.** No harness path (`/tmp/mine-*`, `/tmp/inject-*`, the host home) is left in the current rows. The
only absolute non-workspace path is jac's own build path (`/home/runner/work/jac/...`) inside 6 tracebacks of
`jac test` in one batch3 row. What did show up are probe files the student wrote into the workspace to try a call
(`tmp_check.jac`, `tmp_debug.jac`, `tmp_test_roster.jac`, `debug.py`) and never removed: 7 accepted workspaces
kept one, so injected rows built on them list it (21 rows of batch4's), and 14 trained turns write or run one.
Two student attempts wrote to `/tmp` (refused: outside the workspace).

**Rule now.** The student has prod's `delete_code` (schema verbatim, JacCoder's wording). Acceptance fails while a
scratch file is left (`tmp*`, `temp*`, `scratch*`, `debug*` names, or anything under `scratch/`); the message says to
delete it, or to keep the check as a test block in the module or its `.test.jac` annex. The teacher prompt says the
same. `mine_fixes.py` skips fixes of scratch files; `inject_bugs.py` drops leftover ones from its copy.

**Archive.** Everything produced before this rule (all episodes including the held-out runs, `sets/`, every `sft/`
version, `REPORT.md`, `analysis_heldout.json`) moved to `output/spike/1105-teacher-intervention/archive/2026-11-07/`;
the set symlinks are relative and still resolve there. 1106b was trained on `archive/2026-11-07/sft/seg2_mined_injected`.

**Batch 5.** All 41 training tasks (not the 4 held-out ones) once with the 1106b student under every check above
(`episodes/batch5.sh`), so the new rows can be compared with the archived ones before training.

Its first run (records_crud) ran out of interventions and showed two more harness assumptions, fixed at 13:30 for
the runs after cron_next: the plan's frontend/backend module lists accepted only `-`/`*` bullets, not numbered
items; and the teacher's Bash allowed only commands starting with `jac check` / `jac test` / `ls`, so its compound
ones (`cd scratch && jac run ...`, heredocs, `sed -i`) were denied and 7 of its 8 fixes went unverified. It now may
also run `jac run` and `jac clean`, and the prompt says single commands only, files changed with Edit/Write.
records_crud is rerun at the end as `batch5-records_crud-r2`.

**Our checks are teacher-only (21:21).** `frontend_check.py` and `idiom_check.py` are this spike's tools, not
JacCoder's, so the student no longer sees their output: when only the frontend check fails, the student is told
"the web app's frontend does not load yet" and the teacher is called at once with the findings as a note. The
teacher can run both as `fe-check` / `idiom-check` in its copy, and must ground its turn in what the student can
see (reading the file, `jac check --placements`, `jac build --as source`). Before this, 23 of the batch-5 runs
up to room_scheduler (10 of them accepted) showed the student `Frontend (...)` lines; envelope_budget also ran with
the old code. sales_dashboard and records_crud-r2 run with the new code.

## 2026-11-07 (night): spike_v6, training from 1105, held-out eval without the teacher

The 23 batch-5 runs whose student saw `Frontend (...)` lines are kept as they are (123 of the 650 assistant turns
of the accepted ones came after such a line); they are rerun only if the eval shows frontend skill did not improve.
`pipeline_1107.sh` (under the spike output dir, log `pipeline_1107.status`) runs, each step skipped when its output
exists:

1. `sets/batch5` (batch 5, `records_crud-r2` in place of the run before the plan-list fix) → `sft/trajectories`,
   `sft/mined_fixes`, `sft/injected_bugs`, and `sft/spike_v6` = trajectories twice + both debugging sets (as for
   1106b), valid = the 11 prod-64k valid rows (forgetting check).
2. `sft_img.py` from the 1105 adapter (1105's apps are not spike apps; 1106b's are the same as spike_v6's), lr 5e-5,
   1 epoch → `output/adapter/1107-teacher-iv-v6-on-1105`; merge with vision, Q8_0 GGUF.
3. Eval: the 4 held-out tasks (task_board, event_booking, hotel_rooms, recipe_box; in no training row), 4 runs each,
   **no teacher** (`episode.py --no-teacher`: being stuck does not end the run, only acceptance or 80 turns), for
   the new model and 1105. `score.py` re-checks each final workspace part by part (plan, check, tests, planned
   modules, category, scratch, frontend; frontend_check per check; idiom counts) and gives pass@1/2/4 per task.

**What it answers.** The missing skill is a web app whose frontend mounts. If `frontend` rises from 1105 to the
new model while the other parts hold, the data worked. If not, `score.py`'s frontend_check breakdown says which part
fails (no `def:pub app`, components not bundled, JS that does not compile), to compare with how many accepted web
runs spike_v6 has: few accepted web runs means too little data (more runs, or upgrading the 23 runs), many means the
rows do not teach it. The prod-64k valid loss shows whether 1105's prod skill was lost.

**For RL.** A task where pass@4 > 0 but pass@1 < 1 gives a group of rollouts with different rewards: GRPO can learn
from it. pass@4 = 0 everywhere means the reward is all zero and SFT has to come first; the part scores of
`score.py` are the candidate for a partial reward then. RL on whole multi-turn episodes is not what `grpo.py` does
today (single completion per prompt), so a first RL step would be on the failing part alone (e.g. writing the
entry module and its `app` given the rest of the workspace).

## 2026-11-07: harness rules checked against the Jac skills

The harness rules had been written from memory. Checked against `~/.claude/skills/jac-*` and Jac 0.36.1:

| Rule | Was | Now | Effect |
|---|---|---|---|
| Which tests count | only `*.test.jac` / `test_*.jac` files | any module with `test` blocks; a `<mod>.test.jac` annex runs through `<mod>.jac` (jac-testing) | kanban_board and ctf_scoreboard (batch4) had passing in-file tests and could never be accepted; both pass on rerun (2 and 1 interventions) |
| Missing-test message | suggested `test_*.jac` | points to in-module tests or an annex | jac-testing advises against the `test_` prefix (it still runs on 0.36.1) |
| Planned modules | not checked | every module the plan lists (list item or Mermaid node) must exist | 10 of batch4's 30 and 8 of the 16 earlier accepted runs had skipped planned modules, mostly the frontend |
| Category needs | not checked | llm tasks use `by llm`; graph tasks have `node` and `edge` | commit_message passed without any `by llm` |
| Web frontend | not checked | `frontend_check.py`: entry-point module exports a client `def:pub app`, `jac build --as source` emits JS that `node --check` accepts, lowercase JSX tags are HTML/SVG, components are imported, every JSX module is bundled | see below |
| `docstring_in_def` fix | deleted the docstring | moves it above the def (W0060, jac-core-cheatsheet) | |
| Lookup results in mined rows | showed the replay dir `/tmp/mine-*` | scrubbed to `/workspace` | 35 rows of the 1106b training set had the leak |

Confirmed as they were: `class` instead of `obj` fails at construction (no constructor for `has` fields);
`with entry:__main__` is the CLI entry; `[project] kind` / `entry-point` are real jac.toml keys; MockLLM is
`import from jaclang.byllm.lib { MockLLM }`; `jac check` exits 0 on warnings only.

### Frontends

Of 51 web runs (all accepted runs before this date included), 2 had a frontend the runtime can mount. 32 had no
`def:pub app` in any module: the student writes React-style roots (`def:pub App()`, `index()`) and no entry
module, although the task's `support_files` names `main.jac` as the entry. Other failures found:
`markdown_editor` renders `<Editor />` in `main.jac` without importing it (`jac check` passes); `sales_dashboard`
names a parameter `new`, which compiles to invalid JS (`function on_range_change(new)`).

### Effect on the training rows

`export.py` now applies all the checks above to old runs. Trajectory rows:

| Set | Rows | Trained student turns | Trained teacher turns |
|---|---|---|---|
| batch2/3, as trained into 1106b | 45 | 270 | 65 |
| batch2/3, planned-module and category checks | 40 | 155 | 65 |
| batch2/3, plus the frontend check | 32 | 0 | 65 |
| batch4, before the checks | 55 | 373 | 74 |
| batch4, all checks | 38 | 52 (non-web apps) | 74 |

Student turns of web apps are no longer trained until runs produce mountable frontends.

### Lookup tools

1106b's habit of calling `find_symbol` on an import error came from the harness-built rows (all 189 weight-1
`find_symbol` calls were in mined or injected rows, none in episode trajectories), and those rows used 3 template
sentences (93 of 138 turns used the same one). The chat probe where it also looked up names that were not missing
had a hand-written error that did not name the symbol.

The lookup is now chosen by situation, as the tools' own descriptions (from JacCoder) say: `find_symbol` for a known
name; `grep_search` for text or a name only partly known; `list_files` for which modules exist; `analyze_project` for
an overview of archetypes. In injected rows: when an import lists a wrong name but the code uses the right one
(`wrong_name`), both names are known and find_symbol looks up both. A new kind, `misnamed`, renames the name at every
use and in the import: find_symbol finds no definition, so the next turn greps the imported module for definitions
starting like it, and the fix renames it throughout (`replace_all`). `analyze_project` is not used as evidence: it
lists only archetypes, and for a documented archetype its line is the docstring's. The teacher prompt has the same
guidance and asks it to load the matching skill and write idiomatic Jac (components with `has` state that is rebound,
`{for ...}` slots, `def` handlers, `def:pub app` in the entry, `obj`, `enum`, `with entry:__main__`).

Two intermediate versions were replaced: `*_v2` / `*_v3` picked `find_symbol` or `grep_search` at random per row;
`*_v4` grepped for `wrong_name` although the right name was in the code.

### Idioms

`idiom_check.py` over the trained code of the rows and the 55 workspaces: few React or Python leftovers
(`useState`, `.map(lambda`, Python enums: none). Found: `onClick={lambda ...}` handlers (84 in workspaces;
jac-cl-components wants `def` handlers), 5 in-place mutations of `has` state (the UI does not re-render), 5
`class` for own types, one hand-written `class MockLLM` next to the real import (doc_qa). `jac check --lint` reports
mostly `remove-empty-parens` and `unnecessary-none-return`. 16 of 55 apps keep their data in module `glob` dicts
behind `def:pub` endpoints (evaluated once at server boot, shared by all users) rather than in the graph; not gated.

### Other

- The databases are jac's, not the trajectories' or the apps' data: `jac test` (0.36.1) runs each test block in an
  isolated worker with its own new postgres database in the shared cluster `~/.cache/jac/pg/main`, and does not drop
  it. Measured mid-run: 1,162 databases, all 2.3-8.0 MB (the size of an empty database), so no test filled one with
  nodes; the volume comes from how often the generators run `jac test` (every runtime mutation, on every episode).
- `inject_bugs.py` left ~25 GB of `jac test` databases in `~/.cache/jac/pg` over 40 episodes and filled the disk;
  it now purges after every round of workers (about 4 GB per episode).
- Running the generators next to other jac-heavy jobs made runtime kinds time out (fewer `drop_def` /
  `import_path` rows); run them alone.

## 2026-11-06

- The student got the prod lookups (`list_files`, `grep_search`, `find_symbol`, `analyze_project`); earlier episodes
  had only the four revdev tools.
- Before 06:50, `jac check` output after a write and `jac test` tracebacks showed host paths; `export.py` scrubs them.
- Before 12:00: no `default_codespace = "server"` in `jac.toml` (plain functions could lower to native: E5092,
  `== []` failing under native tests); the detector keyed a failing command by its first three tokens instead of
  the subcommand; the teacher's workspace copy was read-only, so its fixes were unverified.
- Empty `old_string` and `old_string == new_string` edits are refused as in JacCoder (before, no-op edits returned OK).
- 32 tasks with a `category` were added (graph, algorithms, state_machine_game, permissions, realtime, llm, non_web,
  frontend; 4 each), from MIT / Apache-2.0 / BSD projects.
- The plan check required frontend/backend module lists for non-web tasks too; batch4's first cron_next run hit it
  (rerun as batch4r-cron_next).
- Mined rows opened with a harness-inserted `find` listing before the evidence turn (list_files + find_symbol).

## 2026-11-05

Spike set up with student `JacLLM-1105-prod-on-1102` (v1.35 + revdev 1102 + prod-64k). Differences from JacCoder's
edit tools that remain: no loop guard (`check_tool_loop`), no anti-pattern block or `[HINTS: ...]`, no
`_sanitize_jac` auto-fixes, no preview runtime log. If the harness proves too far from the real one: switch to
jacBuilder's JacCoder, try upgrading it to 0.36.1, and fall back to 0.34.x last.
