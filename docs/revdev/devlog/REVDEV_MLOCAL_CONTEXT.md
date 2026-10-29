# 第二個 repo 的雙檔行為任務（2026-10-29）

## 原始 ground truth

候選為 `CosmonautJones/m-local`，本地 commit
`b92b92c8387a12e2c55edbb7638c54dfbed78dc2`。目標是
`services/context_models.jac → services/context.jac`；後者實際 import 前者，
原測試也使用兩檔與既有 `services/importer.jac`。

以 pinned Jac 0.34.27 在未修改的 repo 隔離副本執行
`jac test services/context.jac`，13/13 通過；只保留 `jac.toml` 與
`services/*.jac` 的副本再跑一次，也是 13/13。產生器自己的 reference
preflight 也通過，結果、commit 與各檔 hash 保存於
`dataset/raw/revdev/multifile_v1/runs/mlocal_context/`。

## 產生器變更

- `script/dataset/revdev/recipes/mlocal_context.json` 是可審核的 task artifact：
  指定來源、兩個目標、讀取依賴、原測試、train split 與自然語言任務。
- `multifile_generate.py --recipe` 讀取外部任務，驗證路徑與原測試 preflight，
  保存 task、manifest、checkpoint，再交給原 JacCoder dispatch。
- 超過 16k 且不超過 64k 的接受紀錄可依 repo split 匯出 train 或 valid，
  不再只容許 A2-Pulse valid。
- Claude CLI 非零退出會留下 `interruption.json`；`--resume-existing` 從
  既有 workspace 與事件接續，保留前次失敗紀錄。之後新任務的 preflight
  在臨時副本執行，避免編譯 cache 被複製到 student checkpoint。
- `--repair-existing` 把獨立驗收失敗作為可見 feedback 接續同一條軌跡；
  `--finalize-unvalidated`／`--recheck-existing` 可在 teacher 已完成後重跑
  replay 和驗收，保留前次報告。Claude final JSON 多一個 `}` 時只解析有效
  JSON 前綴，另存原始 response hash 與移除的字元。
- 原 repo 的 `context_models.jac` 在 Jac 0.34.27 單獨 `jac check` 也有
  `E1032`；驗收改為逐檔比對 reference 與重建品的 return code／錯誤碼，
  並額外核對 READ 權限與混合新舊通知的獨立 oracle。

## 執行與接受結果

第一次 teacher decision 在 sandbox 內呼叫 Claude CLI 時回報
`EAI_AGAIN`，未產生任何 tool call；原始 response 在
`runs/mlocal_context/step-000/claude.stdout.json`，不是模型實作失敗。
可連線重試最初被自動核准審查拒絕，理由是這批 repo 原始碼／測試和
工具輸出會送往外部 API；使用者其後明確同意此 m-local 任務用 Claude。
接續使用 `claude -p` subprocess，沒有直接整合 API。teacher 讀取原測試與
依賴，寫入兩個目標檔；第一次原測試為 6 passed／7 failed，根據真實診斷
修正後為 13/13。第一次獨立驗收指出 teacher 把原版 `READ` 寫成 `WRITE`，
混合新舊通知的整體狀態也與 reference 不同，因此保留 rejected 報告，
把驗證結果交回同一條軌跡。修正時發生一次真實 stale-read 拒絕；重新讀檔
後編輯並再次跑到 13/13。

最終 `validation.json` 為 **accepted**：18 個已執行工具呼叫從初始
checkpoint 重播，兩個目標檔 bytes 一致；13 項未修改的原測試、reference
靜態診斷 parity、兩處 `AccessLevel.READ` 及獨立 mixed-state oracle 均通過。
原始 provider response、tool results、失敗／修正與前次拒收報告都保留在 raw run。
這是服務雙檔行為驗證，沒有驗證整個 web app 啟動。

匯出為 `dataset/sft/revdev_multifile/behavior-64k-v1/train.jsonl` 的
**1 筆、24,456 tokens**；A2-Pulse 的 34,733-token 樣本仍在 valid，
維持 repo 隔離。16k smoke 集合維持原本 2 筆，沒有截斷這條長資料。
