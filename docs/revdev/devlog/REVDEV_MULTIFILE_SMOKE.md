# 多檔 smoke 與行為測試擴充（2026-10-29）

## 結果

以 `script/dataset/revdev/multifile_generate.py` 從真實 repo 建隔離 slice、保存
`.jaccoder/build_plan.json` 與初始 checkpoint，再用 Claude JSON decision adapter 呼叫
JacCoder 真正的 `read_file`、`write_code`、`edit_code`、`run_command`。每一步的原始
decision、tool result、Jac 執行結果與資源紀錄都在 `dataset/raw/revdev/multifile_v1/runs/`
和 `output/log/revdev-multifile-*.log`。重播從初始 checkpoint 恢復，再逐步呼叫相同
harness tool，比對回報狀態與目標檔 bytes；獨立 acceptance 使用 pinned Jac 0.34.27。

| 來源 | Teacher 寫入 | Replay | Acceptance | 標籤 |
| --- | --- | --- | --- | --- |
| GhostBoard | `models.jac`、`server.jac` | 7 個實際 tool calls，目標 bytes 相同 | `models.jac`、`server.jac`、既有 `client.jac`、`main.jac` 各自 `jac check` 通過 | `compile_only` |
| A2-Pulse | `services/brief_dates.jac` | 6 個實際 tool calls，目標 bytes 相同 | 原 repo 的 `services/brief_dates.test.jac` 保持 SHA256 不變；`jac test services/brief_dates.jac` 4/4 通過，目標檔 `jac check` 通過 | `behavior_tested` |

GhostBoard teacher 先讀 plan、client、main，接著寫 model 和 server。第一次 server
寫入的 harness 回傳語法錯誤，teacher 用 `edit_code` 修正後才執行 `jac check`。這是
真實失敗與修正步驟，匯出時保留。A2-Pulse teacher 先讀 plan 與既有測試，再完成
date helper；產物與 reference source 的 hash 不同，所以其 4/4 結果不是複製
reference source 得到的。

匯出在 `dataset/sft/revdev_multifile/smoke-v1/`：GhostBoard 為 train 1 筆，
A2-Pulse 為 repo 隔離的 valid 1 筆。以目前 Ornith tokenizer 計，分別是 7,738 與
3,839 tokens；合計 11,577。這只是小型 smoke，不代表足夠訓練。GPU driver 在本輪
無法被 `nvidia-smi` 讀取，資源監控仍記錄 RAM 與磁碟；未執行訓練。

## 拒絕案例與產生器修正

Orbitron 的原始嘗試在 `runs/orbitron/`，狀態為 `rejected`。JacCoder 的 anti-pattern
檢查擋下 `pages/WelcomePage.jac` 寫入；雖然 adapter 回報 `executed: true`，檔案並未
建立，重播檔案也不相同。原本的 `jac check main.jac` 還可能在缺少該 import 檔時
顯示 `1 passed`。產生器現在要求目標檔真實存在、每個目標獨立檢查並與 replay bytes
相同；GhostBoard 也檢查既有 client 與入口。Orbitron 的失敗紀錄不進 SFT。

### Orbitron 瀏覽器驗證（2026-10-29）

為判斷 anti-pattern gate 是否過嚴，在 `/tmp/revdev-orbitron-browser-raw/` 建立**未修改
原始碼**的隔離副本，以 `jac_cli.execute` 啟動 Jac 0.34.27，並使用本機 Playwright
Chromium 造訪 `/`、`/onboarding`、`/dashboard`。原始 Jac stdout/stderr、每條路徑的
HTTP 狀態、body、console errors 及截圖已保存在
`dataset/raw/revdev/multifile_v1/browser_orbitron/`。重現腳本為
`script/dataset/revdev/orbitron_browser_probe.py`，資源紀錄在
`output/log/revdev-orbitron-browser-resources.jsonl`；主要診斷另存於
`output/log/revdev-orbitron-browser-evidence.json`。已核對封存檔 hash，移除
118 MB 的一次性 `/tmp` 副本；原始 raw repo 沒有修改。

三條路徑在 Playwright 中都是 **HTTP 503**，body 為 `503 Service Unavailable`；
因此沒有成功渲染的頁面可供互動測試。Jac 啟動時另有兩組獨立診斷：

- Jac route scanner 回報 `pages/` 有 13 個模組、沒有任何可辨識的 route，預測 app
  不會掛上 file-based router；`WelcomePage.jac` 等函式回傳 `JsxElement` 而非
  `JsxPage`。這支持 harness 對目前 `pages/` 形狀的阻擋，不能再把它單純稱作
  false positive。
- Vite 無法從 client runtime resolve `@tanstack/react-form`；Jac 顯示
  `JAC_CLIENT_001: Missing Dependency`。這個 build 失敗本身也足以讓頁面回 503，
  所以 503 **不能單獨證明**手動 Router 的執行行為。

結論：目前固定 Jac 版本下，原始 Orbitron 無法作為「可運作的 app」ground truth。
先前認定 harness 過度攔截的說法過強；目前不放寬 `pages/` gate。若未來要支援
手動 routing，應在不被 Jac 視為 file-based routes 的目錄建立最小可運作案例，
再測瀏覽器導覽後調整規則。原始 repo 不因此修改。

## 邊界

GhostBoard 的資料證明跨檔 tool use 和靜態相容性，沒有證明服務啟動或 UI/LLM
功能。A2-Pulse 的資料證明 date helper 通過原 repo 的 4 個行為測試，沒有證明整個
應用程式可啟動。下一步若要訓練更大模型，應增加更多有獨立行為驗證的 repo，並
按 repo 分割 train/valid；不能只複製這兩筆或把靜態檢查當成完整 app 成功。
