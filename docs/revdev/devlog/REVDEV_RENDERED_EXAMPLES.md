# Revdev 訓練資料預覽

## 兩種檢視不可混用

原始 run 的 `step-*/decision.json`、`call.json`、`result.json` 和拒絕紀錄
是逐步**稽核資料**，不是訓練時的聊天格式。先前臨時產生的兩份
`full-trajectory.md` 預覽混淆了兩者，現已刪除；原始 run 仍保留。

本節下方連結的 `revdev-a2pulse-markdown-{plan,scaffold,app,resume}` 才是
已驗收 v1 run 由 `export.py` 產生，再用既有 renderer 顯示的 **SFT 視角**。
格式如下：

| 資料階段 | User message | Assistant 訓練目標 | Tool message |
| --- | --- | --- | --- |
| `revdev_plan` | 自然語言 app request | Markdown implementation plan，含 Mermaid | 無 |
| `revdev_scaffold` / `revdev_app` | 目前 exporter 的 JSON context：task、grounded plan、workspace、Jac 版本 | JacCoder schema 的 `tool_calls`（包括寫 `docs/plan.md`、scaffold、實作）及最後回覆 | 真實工具結果 |
| `revdev_resume` | 原 task、handoff、workspace 狀態 | 讀取必要檔案、接續工具呼叫與結果說明 | 真實工具結果 |

在原始 run 中，teacher 每步回一個 `{kind,name,args,summary}` JSON
**決策**；adapter 驗證 schema 和路徑後，把 `name,args` 包成含 workspace、
phase 的 JacCoder **呼叫**，再保存實際結果。Exporter 才把決策的
`name,args` 轉成 `assistant.tool_calls`，把結果 `content` 轉成 `tool`
message。`summary`、adapter 的私有欄位及 `call.json` 包裝不作為學生的
回答。遭 adapter 拒絕的決策仍留在稽核資料；其工具呼叫在可匯出的資料中
標為零權重，絕不偽造執行結果。

目前 implementation SFT 的 User message 直接放了機器 JSON context，
包括 `task_id` 和 `reference_id`。這是現行 exporter 的真實格式，並非
理想的產品對話；量產前應改為自然語言任務與可見的 `docs/plan.md`／handoff
上下文，保留 ID 和私有 grounded manifest 只作 metadata。v2 的 `.jac`
專屬 module plan 已生成實際 run，但前端 build 未通過，所以尚未匯出 SFT。

舊 renderer 輸出已移到 `/run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/revdev-render-pre-module-plan-20261030/`，
`manifest.json` 記錄每個檔案的大小與 SHA-256。以下舊範例連結仍可用；
目前主要目錄保留新版「前端／後端 `.jac` 模組」plan 預覽。

使用現有 `script/dataset/render.py` 與 `script/dataset/trajectory/view.py`
渲染已通過驗證的 Mindcraft pilot。這四個例子來自**同一個 repo**，是不同
SFT 任務或同一軌跡的不同段落，不能當成四個獨立 app。

| SFT 任務 | 實際輸入 → 目標 | 目前樣本 |
| --- | --- | ---: |
| `revdev_plan` | 自然語言 user request → 有檔案、public interface、依賴與驗證流程的 plan；不含 body | 1,415 tokens，1 個 assistant 回覆 |
| `revdev_scaffold` | 完整 plan → 真實 JacCoder 工具呼叫，建立 plan、config、service signatures/stubs、CSS、client 與 entry | 33,352 tokens，13 個 tool calls |
| `revdev_app` | 同一個 user request + plan → 從空 workspace 開始的實作前段，含 scaffold 及開始實作 | 44,877 tokens，18 個 tool calls |
| `revdev_resume` | 中途 workspace + plan → 讀檔接手、實作與檢查；目前 4 個段落 | 首段 52,697 tokens，22 個 tool calls |

Plan 的真實 user request 開頭是「Build a small reflective check-in app. A
person can describe how they feel and see that feeling appear as an object
on an island…」。plan 回覆指定 `jac.toml` → `services/island.jac` →
`styles.css` → `components/MindcraftApp.jac` → `main.jac`，並列出 service
exports 與跨檔依賴。scaffold 軌跡包含實際的 `write_code` 和工具結果；完整
app 前段接著修改 service 和 client。resume 段落從新上下文讀 plan、source，
後續包含真實測試、Jac diagnostics 及修正。

Markdown renderer 會標出 `ASSISTANT (weight 1)`：這些回覆與工具呼叫是
訓練目標。`SYSTEM`、`USER`、`TOOL` 是模型可見上下文，沒有 loss；
`weight 0` 的 assistant 內容也只當上下文。`meta` 用於篩選與溯源，
不是發給模型的訊息。HTML timeline 可以展開每個工具呼叫與結果。

從 repo root 重現預覽：

```bash
python script/dataset/render.py --in dataset/sft/revdev_plan/mindcraft-pilot/train.jsonl --out /run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/revdev-render-pre-module-plan-20261030/revdev-mindcraft-plan.md
python script/dataset/trajectory/view.py dataset/sft/revdev_scaffold/mindcraft-pilot/train.jsonl --out /run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/revdev-render-pre-module-plan-20261030/revdev-mindcraft-scaffold.html
python script/dataset/trajectory/view.py dataset/sft/revdev_app/mindcraft-pilot/train.jsonl --out /run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/revdev-render-pre-module-plan-20261030/revdev-mindcraft-app.html
python script/dataset/trajectory/view.py dataset/sft/revdev_resume/mindcraft-pilot/train.jsonl --out /run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/revdev-render-pre-module-plan-20261030/revdev-mindcraft-resume.html
```

先前展示的 A2-Pulse dates 是 `revdev_multifile`：接手既有 repo
的單一服務任務，會讀取 repo 已有測試，因此適合展示 test-driven
dependency inspection，卻不是全 app user request 的預覽。

## 第二個完整 app：A2-Pulse weekly brief

新產生的 A2-Pulse 是從**空 workspace 建立完整 app**。Teacher 使用實際
JacCoder 工具執行；獨立檢查包含原 repo 日期測試、55 個 executed tool calls
從空 workspace 重播、Chromium 首頁與兩種日期預覽。最後驗證狀態為
`accepted`。隔離匯出有 1 筆 `revdev_plan`（783 tokens）、1 筆
`revdev_app` 前段（21,393 tokens，8 calls）、2 筆 `revdev_resume`
（41,186 與 32,163 tokens；合計 50 calls）。品質審核 5 records
（含 16k plan 副本）、96,308 tokens、0 schema/path/token 問題。

可直接看 [A2-Pulse plan](/run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/revdev-render-pre-module-plan-20261030/revdev-a2pulse-app-plan.md)、
[app 前段](/run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/revdev-render-pre-module-plan-20261030/revdev-a2pulse-app.html)、
[兩段 resume](/run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/revdev-render-pre-module-plan-20261030/revdev-a2pulse-resume.html)。
這是同一條 app 軌跡拆出的三種訓練視角，並非四個獨立 app。

本輪 `revdev_scaffold` 尚未匯出：checkpoint 發生在建立前 3 個 planned
files 之後，剩餘 2 個檔案在下一段建立；目前 exporter 只接受同一段內
完成全部 planned files 的 scaffold prefix。舊的 Mindcraft scaffold
例子可用。A2-Pulse resume renderer 標出重複呼叫及一次失敗的
`cat .jac/client/package.json`；這些是真實軌跡痕跡，應作為下一輪
teacher prompt/投影品質改善的對象。

## Markdown plan + Mermaid：已驗收的新軌跡

依使用者修正，新的 A2-Pulse teacher run 把 `docs/plan.md` 當模型文件：
[planning SFT](/run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/revdev-render-pre-module-plan-20261030/revdev-a2pulse-markdown-plan.md)、
[scaffold SFT](/run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/revdev-render-pre-module-plan-20261030/revdev-a2pulse-markdown-scaffold.html)、
[app 前段](/run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/revdev-render-pre-module-plan-20261030/revdev-a2pulse-markdown-app.html)、
[resume](/run/media/imrui/Seagate/Jaseci/JacLLM/JacCoder/archive/revdev-render-pre-module-plan-20261030/revdev-a2pulse-markdown-resume.html)。
Plan 有 Mermaid `flowchart LR`：`services/brief_dates.jac` 提供
`components/WeekPlanner.jac` 與 `main.jac`，component 再被 `main.jac`
匯入；表格列出每個檔案的責任、公開介面和建立順序。

這條 run 的真實第一個工具呼叫是 `write_code docs/plan.md`，接著依序
建立五個 scaffold 檔案，再實作服務與頁面。`revdev_plan` 965 tokens；
`revdev_scaffold` 18,833 tokens、12 calls；`revdev_app` 22,343 tokens、
18 calls；`revdev_resume` 11,921 tokens、10 calls（其中 9 個執行）。
原 repo 測試、26 executed calls 重播、Chromium 行為測試通過。
詳見 [Markdown/JSON 職責](REVDEV_MARKDOWN_PLAN.md)。
