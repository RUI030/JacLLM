# Mindcraft：實際輸出的 dataset preview

2026-10-29。以下取自已接受的 `claude_teacher_v2`，共 8 筆、5 類。這些是同一次開發的不同切片，有重疊，並不是 8 個獨立專案。單 repo 全部 train-only。

| Dataset | 筆數 | Tokens | 本機 16k 訓練 |
|---|---:|---|---|
| revdev_plan | 1 | 1415 | 1 筆 |
| revdev_scaffold | 1 | 33667 | 0 筆 |
| revdev_function | 1 | 15826 | 1 筆 |
| revdev_app | 1 | 45332 | 0 筆 |
| revdev_resume | 4 | 55271, 31548, 28448, 19709 | 0 筆 |

## revdev_plan

User request → 完整 implementation plan。此筆是從實際 teacher 寫出的 plan 做 context projection；不是另一條獨立 request-only teacher run。

原始資料：`dataset/sft/revdev_plan/mindcraft-pilot/train.jsonl`。

實際 user request：

> Build a small reflective check-in app. A person can describe how they feel and see that feeling appear as an object on an island. They can place it, try a gentle interaction, choose one concrete next action, and reset the island. Keep the check-in history in a graph so the stages are connected. Show a direct crisis-support message for urgent language, and make the main flow work without an AI key.

實際 plan 節錄（省略後續內容）：

```json
{"schema_version": "1", "jac_version": "0.34.27", "ui": {"app_type": "wellness", "nav_pattern": "single_page", "pages": [{"name": "MindcraftApp", "route": "/", "title": "Mindcraft", "purpose": "check_in"}], "primitive_components": ["button", "input", "card"], "style": "custom", "base_color": "neutral", "theme": "nature", "font": "system", "radius": "soft", "menu_accent": "none", "design_rationale": "The island metaphor and clear stage controls make the check-in flow visible.", "auth_required": false, "backend_required": true, "ai_required": false}, "files": [{"path": "jac.toml", "layer": "config", "purpose": "Declare the Jac web app entry, runtime dependencies and local serve route.", "exports": [], "imports_from_plan": [], "write_order": 1, "status": "pending"}, {"path": "services/island.jac", "layer": "service", "purpose": "Define the island graph, deterministic check-in and crisis guard, plus public walkers for placing, interacting, committing an intention, viewing the path and rese
```

## revdev_scaffold

Request + grounded plan → 寫 plan、讀 skills、建立所有規劃檔案的 import/signature/stub。保留實際被 adapter 拒絕的呼叫作 context，但其 assistant weight=0。

原始資料：`dataset/sft/revdev_scaffold/mindcraft-pilot/train.jsonl`。

最前面的實際 tool calls（參數節錄；完整 JSONL 保留所有內容）：

- `run_command`：`{"command": "ls -la", "workdir": "/home/imrui/Documents/Jaseci/JacLLM/JacLLM/dataset/raw/revdev/Mindcraft/m3/runs/claude_teacher_v2/workspace", "timeout": 30, "background": false}`
- `write_code`：`{"file_path": "/home/imrui/Documents/Jaseci/JacLLM/JacLLM/dataset/raw/revdev/Mindcraft/m3/runs/claude_teacher_v2/workspace/.jaccoder/build_plan.json", "content": "{\n  \"schema_ver`
- `load_jac_skill`：`{"name": "jac-fullstack-patterns"}`
- `load_jac_skill`：`{"name": "jac-scaffold"}`

## revdev_function

目前是 function_repair：讀完整 services/island.jac → 修正 keyword iteration 型別。它不是 signature → 從零實作的樣本；該變體仍待擴充。

原始資料：`dataset/sft/revdev_function/mindcraft-pilot/train.jsonl`。

最前面的實際 tool calls（參數節錄；完整 JSONL 保留所有內容）：

- `read_file`：`{"file_path": "/home/imrui/Documents/Jaseci/JacLLM/JacLLM/dataset/raw/revdev/Mindcraft/m3/runs/claude_teacher_v2/workspace-segment-1/services/island.jac", "offset": 0, "limit": 400`
- `edit_code`：`{"file_path": "/home/imrui/Documents/Jaseci/JacLLM/JacLLM/dataset/raw/revdev/Mindcraft/m3/runs/claude_teacher_v2/workspace-segment-1/services/island.jac", "old_string": "        fo`

## revdev_app

乾淨 workspace → 初始開發段。這一筆在 checkpoint 結束，需接後續四筆 resume 才達到已驗證的最終成品。

原始資料：`dataset/sft/revdev_app/mindcraft-pilot/train.jsonl`。

最前面的實際 tool calls（參數節錄；完整 JSONL 保留所有內容）：

- `run_command`：`{"command": "ls -la", "workdir": "/home/imrui/Documents/Jaseci/JacLLM/JacLLM/dataset/raw/revdev/Mindcraft/m3/runs/claude_teacher_v2/workspace", "timeout": 30, "background": false}`
- `write_code`：`{"file_path": "/home/imrui/Documents/Jaseci/JacLLM/JacLLM/dataset/raw/revdev/Mindcraft/m3/runs/claude_teacher_v2/workspace/.jaccoder/build_plan.json", "content": "{\n  \"schema_ver`
- `load_jac_skill`：`{"name": "jac-fullstack-patterns"}`
- `load_jac_skill`：`{"name": "jac-scaffold"}`

## revdev_resume

已實際 restore 的 workspace + plan + handoff → 重新讀取必要內容 → 接手實作／修復／驗證。四筆都來自真實分段執行。

原始資料：`dataset/sft/revdev_resume/mindcraft-pilot/train.jsonl`。

最前面的實際 tool calls（參數節錄；完整 JSONL 保留所有內容）：

- `read_file`：`{"file_path": "/home/imrui/Documents/Jaseci/JacLLM/JacLLM/dataset/raw/revdev/Mindcraft/m3/runs/claude_teacher_v2/workspace-segment-1/.jaccoder/build_plan.json", "offset": 0, "limit`
- `read_file`：`{"file_path": "/home/imrui/Documents/Jaseci/JacLLM/JacLLM/dataset/raw/revdev/Mindcraft/m3/runs/claude_teacher_v2/workspace-segment-1/services/island.jac", "offset": 0, "limit": 400`
- `read_file`：`{"file_path": "/home/imrui/Documents/Jaseci/JacLLM/JacLLM/dataset/raw/revdev/Mindcraft/m3/runs/claude_teacher_v2/workspace-segment-1/components/MindcraftApp.jac", "offset": 0, "lim`
- `read_file`：`{"file_path": "/home/imrui/Documents/Jaseci/JacLLM/JacLLM/dataset/raw/revdev/Mindcraft/m3/runs/claude_teacher_v2/workspace-segment-1/main.jac", "offset": 0, "limit": 200}`

## 證據與限制

- 最終 app：獨立 Jac check、3 個 acceptance tests、5 個瀏覽器操作通過。
- 64 個工具呼叫重播：來源檔案 hashes 和診斷狀態一致。生成的 dist 與時間戳 tool logs 不逐 byte 比較。
- CLI 回傳 JSON decision，再由 adapter 呼叫真實 JacCoder tools；明確標記 transport 轉換，沒有冒稱 provider 原生 tool calls。
- 全部使用同一 reference split group；若將重疊 app/scaffold/resume 同時訓練，需在擴量時控制重複權重。
- 本機只訓練兩筆完整 <=16k 樣本，其餘六筆沒有截斷、也還沒訓練。
