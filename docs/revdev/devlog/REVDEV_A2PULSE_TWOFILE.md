# A2-Pulse 雙檔行為驗證 trajectory（2026-10-29）

## 選擇與原始 baseline

來源為 `A2Tech360/A2-Pulse` commit `9c57f06ad7e6b1fdd2bbf72efde5b6edb88e4771`。
`services/brief_editor.jac:13` 真實 import `services/brief_dates.jac` 的
`brief_monday`。隔離 slice 保留 repo 的兩個原測試和既有依賴；僅以
`jac_cli.SERVER_TOML` 固定 server codespace。原檔在 Jac 0.34.27 下各自
`jac check` 通過，`jac test services/brief_dates.jac` 為 4/4，
`jac test services/brief_editor.jac` 為 23/23。完整 return code、stdout/stderr、
SHA256 與 import edge 在
`dataset/raw/revdev/multifile_v1/a2pulse_editor_preflight.json`。

較大的 `speakable.jac → brief_narrative.jac` 候選也有原測試 21/21 與 28/28
通過；但 teacher 生成第一個長檔時，單次 Claude decision 在 240 秒超時，
沒有任何目標檔寫入。保留中斷的 raw events 和
`runs/a2pulse_speech/interruption.json`，不匯出 SFT。

## 實際雙檔軌跡

`script/dataset/revdev/multifile_generate.py --task a2pulse_editor` 以真實
JacCoder tool schema 和 dispatch 從 checkpoint 恢復的 workspace 執行。
Teacher 先讀 plan 與兩份原測試，寫 `brief_dates.jac`，再讀其當下內容與
`speakable.jac`、`brief_narrative.jac`、`pulse_llm.jac`。日期檔在第一次讀取後
又被改寫，因此 adapter 擋下第一次 editor 寫入；teacher 重新讀最新日期檔後，
才寫出 editor。第一次 editor 寫入有真實 type diagnostics；首次原測試為
16 failed、7 passed，teacher 編輯後第二次跑到 23 passed。拒絕與失敗結果都保留在
`runs/a2pulse_editor/conversation.json`，沒有補造成功回覆。

最終狀態 `accepted`：16 個已執行工具呼叫從初始 checkpoint 重播，目標兩檔
bytes 相同；獨立 `jac check` 兩檔皆 exit 0；在重建副本重跑原 editor 測試
23/23、dates 測試另行重跑 4/4；後者四項包含在前述 23 項中，並非 27 個
不同測試。兩份原測試的 SHA256 與 reference 相同。生成的
兩個目標檔 SHA256 均與 reference 不同，驗證結果不是直接複製 reference body。
證據在 `runs/a2pulse_editor/{validation,acceptance,source-manifest}.json`。

## 匯出與限制

精確使用現有 trainer 的 chat template 與 assistant loss mask，全文
**34,733 tokens**，其中 **4,685 loss tokens**（13.49%）。超過 smoke 16k cap，
低於 65,536 cap；匯出到
`dataset/sft/revdev_multifile/behavior-64k-v1/valid.jsonl`，train 為 0。
同 repo 先前的 dates smoke 也在 valid，維持 repo 隔離；不要同時把此筆當
train 並用先前 A2-Pulse valid 做評測。精確 audit 在
`output/eval/revdev/a2pulse-editor-token-audit.json`。

這是**服務模組**的雙檔行為驗證，不代表整個 A2-Pulse web app 啟動成功。
下一階段應找到其他 repo 的等級相當案例，再決定長 context 訓練與
完整 app／64k 接續軌跡。單條有效 valid 範例不能證明模型能力改善。
