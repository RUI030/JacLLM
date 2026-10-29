# 真實多檔 trajectory 擴充方案（2026-10-29）

## 已查證的起點

`dataset/raw/repo/JacHackSpring/orbitronsystems__ori-Jac-Demo` 有 17 個來源 `.jac` 檔。實際 import 路徑包括
`main.jac → index.jac → pages/DashboardPage.jac → pages/dashboard/TelemetryModule.jac`。
隔離複本加上 `jac_cli.SERVER_TOML`，使用固定 Jac 0.34.27 執行 `jac check`：
入口與 17 個檔案逐一 exit 0。原始結果在
`output/log/revdev-multifile-preflight-orbitron*.json`。這只證明靜態檢查，
沒有證明服務啟動、互動、資料持久化或功能正確。

`GhostBoard` 也有四個真實分檔，入口檢查通過；但含 `by llm()`、
無現成行為測試，而且 `with entry` 啟動同步迴圈，暫不當第一個端到端 acceptance 候選。
`dataset/raw/repo` 還有其他多檔 repo；須逐個固定 commit / version、排除產物與 vendored 檔、
確認測試與依賴，不能依檔案數直接收錄。

## 合成方式

1. 對每個真實 repo 建 immutable manifest：repo/commit、每檔 SHA256、Jac 版本、
   compiler AST 宣告與簽名、實際 import edges、baseline command 及原始結果。
2. 依真實 import graph 選一個小的 connected slice，包含至少兩個需要由 teacher 寫入的檔案。
   未選的 dependency 保留原始檔供 read-on-demand。禁止把單一原始檔切成多檔後稱為跨檔案例。
3. 產生完整 planning artifact，再讓 teacher 從真實空缺 workspace 用捕獲的 JacCoder tools
   建立所有檔案 scaffold、依照依賴實作、檢查。工具呼叫和結果均保留原樣。
4. 注入可重現的接手／錯誤情境：例如依賴檔在上次讀取後變更、一次真實 `jac check`
   失敗，或完成一個 dependency group 後保存 checkpoint。這些情境必須真的在 workspace 發生。
5. 從 checkpoint 恢復，讓 teacher 先查 plan 與當下檔案再繼續；使用原始 repo 的其餘檔案
   及獨立 acceptance 重新測試產物。對 tool schema、實際 read-before-use、hash、重播、
   命令 exit code、行為測試都留下證據。沒有行為測試者標記 `compile_only`，不聲稱 app 成功。
6. 用實際 tokenizer 在完成的 tool response 邊界切 16k / 64k segments；完整 raw 不截斷，
   resume 必須對應可恢復的 checkpoint。依來源 repo 分 train / valid。

直接沿用 `extract.jac` / `extract.py`、`checkpoint.py`、`claude_adapter.execute_tool`、
`replay.py`、`validate.py`、`export.py`、`dataset.pipeline`，補上 multi-file slice selection
和使用真實 repo 檔案的 acceptance。現有 `scale_tasks.py` 的單檔拆分模式不適合拿來聲稱真跨檔。

## 一筆預期範例（尚未生成）

來源切片：上述 Orbitron 的 `TelemetryModule.jac` + `DashboardPage.jac`。
學生可見需求：完成 dashboard 與 telemetry 區塊，整合到既有路由；其他頁面與入口已存在。
預期證據序列：讀 `index.jac` 與相關頁面的 public interfaces → 寫兩檔 scaffold →
`jac check main.jac` → 實作 TelemetryModule → 確認其 export → 實作 DashboardPage 的 import
及顯示 → `jac check main.jac` → 儲存 checkpoint / resume。實際 teacher 可選其他合法 read order。
若沒有可執行的互動 acceptance，此例只屬編譯層級，不能列為 working-app SFT 成功案例。

## 收錄門檻與次序

先做一個真實多檔、雙檔寫入、可重播的 smoke；再挑有自帶 tests 或能建立獨立
行為測試的 repo，才擴大。優先檢查 fresh workspace 路徑、offset=0、失敗後修正、
依賴更新後重讀、跨檔修改與最終測試。這些正是現有 r16 固定評測未改善的行為。
