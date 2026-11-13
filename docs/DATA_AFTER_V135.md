# Data after v1.35

Every dataset trained into (or built for) a model after `JacLLM-SFT-Ornith-9B-v1.35`, as of 2026-11-07. The
datasets v1.35 itself was trained on (`dataset/sft/*/Nitin-*`, `Rui-jacapp-scaffold`, `repo-all-pi`) are in
`DATA_SOURCE.md`.

Tokens are counted with the Ornith-1.5-9B tokenizer and chat template, tool schemas rendered into the system prompt.
**Weight-1 tokens** are the assistant turns that carry loss (message weight != 0), i.e. what the model learns from;
everything else is context. Images count as one placeholder here; prod-64k's own README has the processor counts
(9,447,101 tokens with images, 612,163 trained in train).

## Model lineage

```
v1.35 ─┬─ 1102 (revdev) ── 1105 (prod-64k, M7) ── 1106b (spike seg2_mined_injected)
       ├─ 10-26 prod-img-sft (prod-64k before M7; that version is no longer on disk)
       └─ 10-28 prod-img-sft-m7 (prod-64k, M7) ── jacbuilder-debug-v2 smoke (1 step)
```

## Datasets

| Dataset | Path | Content | Rows | Tokens | Weight-1 tokens | Apps | Trained into |
|---|---|---|---|---|---|---|---|
| revdev accepted-dedup | `JacLLM-revdev-wave2/dataset/sft/revdev/accepted-dedup` | Claude-teacher builds of Jac hackathon repos, plan + app turns with 4 tools (read/write/edit/run) | 97 | 1,048,137 | 254,537 | 22 | 1102 |
| prod-64k | `dataset/raw/prod/sft/prod-64k` (train) | Real JacHammer user sessions: main agent turns (127) and planner chains (80), full 27-tool schema, screenshots, thinking | 207 | 7,697,986 | 619,051 | 80 sessions | prod-img-sft, m7, 1105 |
| prod-64k valid | same, `valid.jsonl` | as above, eval only | 11 | 521,873 | 45,697 | 4 sessions | (eval) |
| no_image synthetic-v1 | `dataset/sft/no_image/synthetic-v1` | Short chats: asked about a screenshot that is not attached, the answer says so | 54 | 8,605 | 2,504 | 0 | none |
| jacbuilder debug-pilot-v2-projected | `dataset/sft/jacbuilder/debug-pilot-v2-projected` | 2 JacCoder debug episodes (import typos) by a Claude teacher, Jac 0.34.28 | 2 | 50,437 | 225 | 2 | smoke only |
| spike seg2_mined_injected | `output/spike/1105-teacher-intervention/archive/2026-11-07/sft/seg2_mined_injected` | Teacher-intervention trajectories (45 rows ×2) + mined fixes (70) + injected bugs (335), 8 tools | 495 | 3,320,943 | 341,085 | 9 | 1106b |
| spike batch2_3_seg_v4 | `archive/2026-11-07/sft/batch2_3_seg_v4` | The same 9 apps' trajectories under the frontend / planned-module / category checks | 32 | 925,145 | 37,086 | 9 | none |
| spike batch4_seg_v4 | `archive/2026-11-07/sft/batch4_seg_v4` | Batch 4 trajectories (categorized tasks) under the same checks | 38 | 963,318 | 88,157 | 32 | none |
| spike debug_mined_v4_all | `archive/2026-11-07/sft/debug_mined_v4_all` | Fixes mined from the 9 apps' episodes, situation-based lookups | 70 | 240,956 | 26,082 | 9 | none |
| spike debug_mined_v4_batch4 | `archive/2026-11-07/sft/debug_mined_v4_batch4` | Fixes mined from batch 4 | 76 | 283,298 | 49,501 | 27 | none |
| spike debug_injected_v5_all | `archive/2026-11-07/sft/debug_injected_v5_all` | Bugs injected into the 9 apps (12 kinds incl. `misnamed`) | 350 | 1,102,121 | 77,646 | 9 | none |
| spike debug_injected_v5_batch4 | `archive/2026-11-07/sft/debug_injected_v5_batch4` | Bugs injected into batch 4 | 644 | 2,146,249 | 152,314 | 32 | none |
| spike batch5 | `output/spike/1105-teacher-intervention/episodes/batch5-*` | Episodes of all 41 training tasks with the scratch rule and `delete_code`, 9 tools | running | | | 41 | none |

## Apps and overlaps

- **Spike**: 45 tasks paraphrased from public GitHub repos (`script/spike/1105 Teacher Intervention/tasks/`):
  9 older ones (class_attendance, dev_forum, expense_tracker, library_loans, memories_feed, records_crud, shop_cart,
  travel_blog, user_roster), 32 categorized ones (batch 4), 4 held out (event_booking, hotel_rooms, recipe_box,
  task_board; never in training rows). Within the spike, the same apps recur across sets: the 9 older apps are in
  seg2_mined_injected, batch2_3_seg_v4, debug_mined_v4_all and debug_injected_v5_all; the 32 batch-4 apps are in
  batch4_seg_v4, debug_mined_v4_batch4 (27 of them) and debug_injected_v5_batch4. Batch 5 reruns all 41.
  The 9 and the 32 do not overlap.
- **revdev**: 22 Jac hackathon repos (`split_group`); none is a spike task.
- **prod-64k**: 84 JacHammer sessions (80 train, 4 valid) of real users' own projects; a session is one project,
  but one project could span sessions. Not the same codebases as revdev or the spike; similar kinds of app were not
  checked.
- **jacbuilder pilot**: 2 synthetic debug episodes.

So 1106b's data and every new spike set share the 9 older apps, and the new sets are rebuilt versions of the same
episodes. A model trained on the new sets should start from 1105, not from 1106b.

## Notes on how each was made

- **revdev**: Claude CLI teacher, JSON output converted to function calls, run workspaces projected to `/workspace`,
  near-duplicates removed (dedup). 64k cap.
- **prod-64k**: `script/dataset/trajectory/clean.py`, rules in its `RULES.md`. One row per real run, not chunked:
  over 64k the oldest history is cut, a turn longer than 64k by itself is dropped (86 of 226 main turns). Bad habits
  are masked (weight 0), not deleted, so the context stays true; M7 (added 10-27) masks calls the harness prompt
  forbids. Thinking kept (GLM reasoning), original Ornith template. Real user data: never commit or share.
- **no_image**: synthetic counter-examples against hallucinated screenshot answers; built but in no training run.
- **jacbuilder pilot**: Jac 0.34.28, not the 0.36.1 the rest uses.
- **spike** (details in `TEACHER_INTERVENTION.md`): student 1105 (batches 2-3) or 1106b (batches 4-5) in a
  JacCoder stand-in harness; a Claude Opus teacher writes the next turn after 3 failures at one place. Teacher turns
  that worked are weight 1; student turns only when the episode passed acceptance. Mined rows replay a file that
  failed `jac check` and its later fix; injected rows break files of accepted episodes in the ways the student got
  stuck, kept only when the tools confirm the bug. seg2_mined_injected repeats the 45 trajectory rows twice. The
  student sees 8-9 of JacCoder's 27 tools.
