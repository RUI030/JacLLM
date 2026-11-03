# Rui/pomodoro backend trajectory (2026-11-01)

## Source and scope

- Source: `dataset/raw/repo/Rui/pomodoro/endpoints.jac`, SHA-256 `1c62aab192e2ae49bb51637a02048869b237bca6bdc94a9c0b375a9d28c0991a`.
- Slice: event creation, Pomodoro session transitions, persistent idle settings, with `endpoints.jac` imported by `main.jac`. This is a headless adaptation, not the source repository's full web UI.
- Target Jac: 0.36.1. The reference pins 0.36.0; an isolated copy with only the pin removed passed `jac check` and three independent reference behavior tests under 0.36.1.
- Recipe and independent acceptance: `script/dataset/revdev/recipes/pomodoro_backend/`.

## Raw execution and verification

- Accepted run: `dataset/raw/revdev/Pomodoro/runs/claude_teacher_backend_036_v3/`.
- 22 teacher decisions, 19 executed JacCoder calls, two retained adapter schema rejections. The teacher's four behavior tests passed. The independent acceptance file ran three tests and passed; `jac check main.jac` passed.
- Clean replay passed for all 19 executed calls, and `validate.py --accept-backend` marked the run accepted. The final workspace contains `docs/plan.md`, `jac.toml`, `endpoints.jac`, `main.jac`, and teacher-authored tests.
- Earlier v1/v2 attempts were interrupted during planning when source field names/types were under-specified. Their raw files remain as failure evidence and were not exported.

## SFT output

- Source repository split: **train** (`rui__pomodoro`). This repository already appears in older `scaffold2impl` and `tool_fim` training files, so a valid assignment would leak across the broader model dataset.
- Formal output: `dataset/sft/revdev_{plan,scaffold,app,resume}/pomodoro-backend-036-v3/` with one record each. Token counts: 1,131; 8,051; 21,555; 8,353. The `revdev_function` export yielded zero records. The 16k siblings contain plan, scaffold, and resume only.
- The initial valid export is retained under `dataset/raw/revdev/Pomodoro/exports/claude_teacher_backend_036_v3/` as attempt evidence; it is not part of the formal training set.
- Full revdev audit after formal train export: 48 records, 507,340 tokens, zero issues. No `rui__pomodoro` valid record is present in formal revdev output.

The 21,555-token app record fits the 65,536-token dataset cap but exceeds the current 16,384-token trainer context. Its shorter plan/scaffold/resume records are immediately eligible for that context.
