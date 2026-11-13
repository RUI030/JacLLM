# 1105 Teacher Intervention

Spike: can a teacher that steps in only when the student is stuck produce useful SFT rows, and do they change the
student? The student is a JacLLM GGUF served by `script/eval/agent/serve.sh` (64k context, thinking on); the
teacher is `claude -p --model opus`. Findings, changes and their dates are in `docs/TEACHER_INTERVENTION.md`.

## What it does

- **Harness** (`workspace.py`): a light JacCoder stand-in on Jac 0.36.1. The student gets the revdev student prompt
  and tool schemas (`prompts/`, see `prompts/SOURCE.md`) without `load_jac_skill`, plus the prod lookups
  `list_files`, `grep_search`, `find_symbol` and `analyze_project` (`prompts/lookup_tools.json`; the last two run
  `lookup.jac`, a port of JacCoder's `jac_analyzer.impl.jac`) and prod's `delete_code`. Tools run on a real
  directory shown as `/workspace` and answer in JacCoder's wording. Every jac call keeps `[build] default_codespace
  = "server"` in `jac.toml`. `run_command` takes an allowlist (`jac check|test|run|build|...`, `ls`, `cat`, ...): no
  network, servers or background jobs.
- **Episode** (`episode.py`): a plan phase (the plan must have a Mermaid module graph, .jac modules, typed `def`
  signatures and a verification section), then a build phase. A final answer is accepted (`Episode.accept`) only
  when no scratch file is left (`tmp_*`, `debug*`, `scratch/`), every `.jac` file passes `jac check`, `jac test`
  passes on every module with `test` blocks, every module the plan lists exists, the app uses what its category
  needs (`by llm`, or `node` and `edge`), and a web app has a frontend the runtime can mount (`frontend_check.py`).
- **Detector**: a turn fails on a tool failure, an identical repeated call on an unchanged workspace, a tool call
  after the checks pass, a final answer before they pass, or a reply cut off at the token limit.
- **Teacher** (`teacher.py`): after 3 failures at the same place, `claude -p` gets the visible trajectory, a scratch
  copy of the workspace, `jac check` / `jac test` and the Jac skills. It tries its fix in the copy and proposes the
  student's next turn, which the harness executes like a student turn.
- **Compaction**: past 48k prompt tokens a new segment starts from a handoff in the revdev resume format.
- **Repetition guard** (`generate.py`): a looping reply is cut and continued after `Wait, I'm repeating myself. ...`.
- **Rows** (`export.py`, `sft_img.py` format): one row per trajectory. Teacher turns that worked are weight 1;
  student turns that worked are weight 1 only when the episode passed acceptance.
- **Debugging rows**: `mine_fixes.py` turns each file that failed `jac check` and was later fixed into a short row;
  `inject_bugs.py` breaks files of accepted episodes in the ways the student got stuck and keeps only bugs the tools
  confirm. An import fix is preceded by a lookup that shows where the name is defined, chosen by situation
  (`find_symbol` for a known name, `grep_search` when the name has no definition). Both read `sets/<name>` (training
  episodes), never the held-out comparison runs.
- **Checks**: `frontend_check.py` (does a web app mount and compile), `idiom_check.py` (non-idiomatic Jac: `jac check
  --lint` plus the skills' rules), `analyze.py` (failure statistics per group).

## Run

```bash
# student server (once): Q8_0 at 64k uses ~13 GB of VRAM
systemd-run --user --unit jacllm-serve -p MemoryMax=10G -p MemorySwapMax=0 --setenv=NP=1 --setenv=CTX=65536 \
    --setenv=LISTEN=127.0.0.1:8080 bash script/eval/agent/serve.sh <gguf model name> Q8_0
cd "script/spike/1105 Teacher Intervention"
PATH=$HOME/.local/bin:$PATH python episode.py --task records_crud      # -> output/spike/1105-teacher-intervention/episodes/
python export.py --episodes <set dir> --out <train.jsonl>             # trajectory rows
python mine_fixes.py --episodes <set dir> --out <train.jsonl>         # fixes mined from episodes
python inject_bugs.py --episodes <set dir> --out <train.jsonl>        # injected bugs
python frontend_check.py <workspace> ...                              # web app frontend check
python idiom_check.py --workspaces <workspace> ... | --rows <train.jsonl> ...
```

`jac test` leaves a postgres database per test block (`~/.cache/jac/pg`); `inject_bugs.py` purges them after every round of workers (about 4 GB per
episode). Tasks (`tasks/*.json`) are English requirements paraphrased from open-source GitHub repos (source and
license in each file); no code is copied. Tasks with a `category` come from permissively licensed projects;
`non_web` tasks bring their own `support_files` (a library with a CLI entry, not a web app).
