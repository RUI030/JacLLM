# Claude CLI teacher adapter

2026-10-29。沿用已登入的 Claude Code CLI。`--system-prompt-file` 使用捕獲的 JacCoder system prompt，加 teacher 與 transport 指令；`--tools ''` 關閉 Claude 自帶工具。每次回傳一個 JSON decision，由 Python 驗證後交給 `dispatch.jac` 呼叫真正的 JacBuilder 工具。此 transport 必須記錄為 JSON decision → tool-call 轉換，不能標示為原生 provider tool call。

## 執行與紀錄

- `script/dataset/revdev/claude_adapter.py`：讀 task/plan、保存原始 Claude response、schema validation、dispatch、token 預算與 checkpoint。
- `dispatch.jac`：沿用 `read_file`、`write_code`、`edit_code`、`run_command`、`load_jac_skill`；只暴露這五個實際工具的原始 schema。
- `plan_build` 尚未接入，完整 grounded plan 作為可見 context，由 teacher 透過 write_code 寫入。這是明確的介面差異。
- 每步保存 request、decision、實際 execution stdout/stderr、result。Adapter 的拒絕會標記 origin/executed，不能冒充 JacBuilder 成功執行。
- Compiler AST 在 scaffold 階段檢查每個 function/ability body：只允許明確 stub，UI 入口允許最小 JSX。所有規劃檔案存在後才進 implementation。
- Token 邊界保存 workspace＋plan hashes，再恢復到新路徑，清除舊對話並要求先讀 plan／相關檔案。正式 export 仍須用訓練 tokenizer/template 檢查 65,536 上限。

第一輪 `claude_teacher_v1` 在所有 scaffold 完成前實作 service，已停止並標記 `rejected_scaffold_order`，不供訓練。第二輪 `claude_teacher_v2` 已通過接受門檻：獨立 `jac check`、3 個 acceptance tests、5 個瀏覽器互動，以及 64 個實際工具呼叫重播。來源檔案 hashes 和診斷狀態一致；帶時間戳的工具輸出檔和生成的 dist archive 不做逐 byte 比對。完整原始輸出保留於 run。

## 訓練與資源

使用者授權通過驗證後接續 trajectory 模型做 rank 16 SFT。基底為 `output/model/JacLLM-SFT-Ornith-9B-trajectory-bf16`，新增 LoRA r16，避免將既有 r64 adapter 誤當成 r16。Recipe：`script/train/recipe/1029-revdev-r16/sft.yaml`。

完整資料上限仍為 64k；這台 RTX 5080 16GB 的第一輪訓練只使用完整長度不超過 16,384 的樣本，不截斷超長軌跡。單 repo pilot 為 train-only，不能聲稱有獨立 validation 成績。

`script/utils/resource_watch.py` 每五秒記錄 RAM、swap、GPU VRAM/utilization/temperature、SSD/HDD 空間及 diskstats。可用 RAM <4 GiB、任一磁碟剩餘 <20 GiB 或 GPU >=88°C 時停止受監控工作。日誌保留在 raw run 或 output/log。

四個舊 v1.2 模型已透過 `script/archive_models.py` 比對 HDD 副本 SHA256，再切換原 SSD 路徑為 symlink。明細及逐檔 hashes：`output/log/archive-models-20261029.jsonl`。Trajectory 合併基底留在 SSD。

## Pilot 接受結果

五類共 8 筆，全部不超過 65,536 tokens；只有 plan 與 function repair 共 2 筆符合本機 16k 限制。[實際預覽](REVDEV_DATASET_PREVIEW.md) 列出每類內容與限制。`revdev_app` 是第一段開發軌跡，最終成品經四段 resume 才完成，不能把第一段單獨描述成完整 app。

Runtime 固定 Jac 0.34.27。真實執行暴露了 host 0.36.1 checker 混用與 microservices 自動啟動問題；dispatcher 已固定 PATH，teacher 依據實際錯誤恢復 client codespace，並設定 `[scale.microservices] enabled=false`。所有修復都保留於軌跡。0.36.1 harness 遷移仍未完成。

訓練啟動時發現 recipe 的 log_freq 放錯區塊，以及 planning/tool-use Arrow nested message schema 無法合併，皆在載入模型之前失敗。已移正設定，並在既有 mixer 中對齊欄位，原始 tool arguments、weight 與 results 不變；失敗 logs 保留於 output/log。

## Rank 16 SFT 結果

已完成，process exit 0。使用 trajectory 合併基底、新建 r16/alpha16 LoRA，兩筆完整樣本、1 epoch、2 optimizer steps。Training loss 1.277（僅訓練紀錄，非能力評估）；adapter 位於 `output/adapter/1029-revdev-r16/sft/adapter`，checkpoint-2 可恢復 optimizer。256 個 tensor 均 finite，128 個 LoRA B tensor 非零；adapter_config 確認 r=16 與 trajectory base path。

每五秒抽樣的訓練資源：VRAM 最高 14,207 MiB、GPU 最高 60°C、RAM 可用最低 39.88 GiB、SSD 可用最低 820.36 GiB、HDD 可用最低 4,395.50 GiB；沒有觸發停止門檻。這是抽樣峰值，非硬體瞬時上限。最終驗證 server 已關閉。訓練與監控 logs：`output/log/revdev-r16-training.log`、`output/log/revdev-r16-resources.jsonl`。

Mixer 驗證：實際兩筆資料可混合；concat/sequential/interleave 保留 tool calls 與 weight=0。Interleave 的 all_exhausted 會重採樣，不能要求筆數與 concat 相同。

仍待完成：額外 repo 的泛化驗證、signature-to-implementation 變體、長軌跡在 64k 訓練機的實測、dependency/read 重複率報告與生成後模型能力評測。這次完成的是一個可重播的資料生成→匯出→訓練 pilot。

後續已完成初步成對能力測試，結果與限制見 [REVDEV_MODEL_EVAL.md](REVDEV_MODEL_EVAL.md)：planning 一題的簽名較完整，核心工具決策／實作完成率尚未改善。
