# mix_1113_mini

Training data for adapter `1113-mini-on-v135`: the rows of `mix_1112_subset` plus the mini apps. Built by
`python script/dataset/sft/mix_subset.py output/sft/mix_1113_mini --mini` (run by `output/eval/agent/pipeline_1113.sh`).

The question this mix answers: do one-screen apps that are almost nothing but wiring reduce the errors that stop
every app 1112 built (server module not loaded, imports of things that do not exist, `await` in the wrong place)?

1112 and 1113 differ only in this data, so the scenarios compare directly.

Known fault kept from 1112: in the 42 UI main rows the first message names one working directory
(`.../projects/<uuid>/prj_<a>`) while every tool call uses another (`.../projects/prj_<b>`), because
`ui_apps.app_rows` read the project root with a trailing backslash. The code was fixed on 2026-11-12 and the mini rows
are built with the fix (one path per row, as in prod). The UI rows were not rewritten for this mix: it would be a
second difference from 1112, and the longer paths (about 75 per row, +37 characters each) may push coursely, hireboard
and northdocs over max_seq_length, where sft_img.py crashes. Count their tokens before running
`ui_apps.py --rows-only` for a later mix.

| Group | Source | Copies | Note |
|---|---|---|---|
| prod, ui, synthetic | as in `mix_1112_subset/README.md` | 2, 3, 1 | unchanged |
| mini | `output/sft/jac_ui_build/mini_apps_harness_v1/train.jsonl` | 3 | a main row and a planner row per app |

Mini apps (`output/sft/jac_ui_build/mini_apps_v1`, `mini_apps_v2`; producer `script/dataset/sft/mini_apps.py`):
- written by Opus and Sonnet from apps already verified on jac 0.34.28, without running anything;
- used only after their browser flow passes (`mini_apps.py --verify`, result in `<batch>/verify.status`) and their
  replay through the real harness has no check error, no blocked write and every file written;
- server-backed ones in both styles (`def:pub` functions, walkers with `root spawn`), client-only ones as the
  contrast where `main.jac` imports no server module.

Held out for `valid.jsonl` (with pantry and sprintboard): `scoreboard_walker`, `contacts_form`.
Same loss rules as 1112: 11-tool subset, reasoning capped at 400 characters. Training settings unchanged (rank 64,
lr 1e-4, grad-acc 4, one epoch, max_seq_length 65,536). Row and app counts of the build: `output/sft/mix_1113_mini.build.log`.
