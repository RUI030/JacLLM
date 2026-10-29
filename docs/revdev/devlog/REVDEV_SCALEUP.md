# Reverse development scale-up（2026-10-29）

## 狀態

模組任務 reference preflight、真實 teacher generation、checkpoint replay 與獨立驗證均完成 21/21。
訓練組 14/14 已通過執行、checkpoint replay 與獨立驗證；加原 planning 1 筆，
15 筆接續 r16 SFT 與模型能力比較已完成；Aegis 7 筆固定為 heldout valid，未用於訓練。
本批是既有專案中的 function implementation / repair / resume，並非 21 個完整 app。

## 為什麼擴量

上一輪 capability comparison 沒有證明整體改善。以實際 tokenizer 與
`train.sft.tokenize_with_assistant_mask` 重算（不截斷，排除 weight=0）：

| 範圍 | 筆數 | 平均完整 tokens | 平均 loss tokens | 總 loss tokens |
| --- | ---: | ---: | ---: | ---: |
| Pilot 全部 | 8 | 28,902 | 4,156.375 | 33,251 |
| Pilot 實際 16k 訓練範圍 | 2 | 8,620.5 | 765 | 1,530 |

全部 8 筆 loss 比例為 14.38%；實際兩筆為 8.87%。其中 function repair
只有 238 個 loss tokens。完整 context 長不等於模型得到大量工具行為監督。
原始統計：`output/eval/revdev/pilot-token-audit.json`。

## 本批方法

- 3 repos、21 AST 定位的模組任務；Mindcraft 5 + Alongside 9 為 train；
  Aegis ForkGuard 7 固定為 repo-heldout valid。split 在 generation 前決定。
- `slice.jac` 使用 Jac compiler AST 定位宣告與行範圍，保留原始 source；
  `scale_tasks.py` 建立 scope、簽名、依賴、需求、既有 plan、checkpoint 與驗證案例。
- reference 原碼、commit、source hash、AST span 保留在 private artifact。
  Teacher 不會看到目標函式原始 body；既有 dependency 與測試可讀。
- `scale_generate.py` 呼叫 Claude CLI，使用完整 captured JacCoder system
  加 scoped teacher instruction；只有四種真實 harness tools 可用。
- 實際 tool schema 沒有自行改寫。工具經共用 `execute_tool` / `jac_cli` 執行。
  原始 calls/results、失敗、rejections、CLI response 全部保留。
- read on demand：先讀 plan / target / dependency，已讀且未修改的內容可重用。
  offset 明定從 0 開始；repair fixtures 包含真實錯誤及空頁讀取。
- Fixture seed actions 和 adapter 拒絕的 actions 設 weight=0；真實結果仍是 context。
- 每條軌跡從 checkpoint 重播，核對最終 source 與結果狀態訊號；再以原始
  dependency / verify fixture 驗證 teacher 產出的 app.jac。
- Export 明確替換為較短的 scoped student prompt；這是有紀錄的 context projection，
  不是聲稱 student 收到與 teacher 完全相同的 prompt。原始 teacher prompt 保留。
- Workspace 路徑映射成 `/workspace` 並保留 mapping；完整工具結果不捏造。
- 本批接受上限 16,384 tokens，超長拒收且保留 raw，沒有靜默截斷。
  未替代完整 app 的 64k / resume 切段設計。
- 模組測試只涵蓋具體案例，不代表完整 repo 或全端應用已驗證。
  依賴觀察 gate 目前用實際 read output 的名稱出現判定，尚非完整 semantic resolver。

## Preflight 問題與修正

1. `jac run` 下相對 `.app` import 沒有 parent package；改成 workspace 內絕對 module import。
2. 0.34.27 native lowering 在部分 reference 函式產出錯值；沿用
   `jac_cli.SERVER_TOML` 將 default_codespace 固定 server。保留兩次失敗 artifacts。
3. Jac 字串中的換行需要跳脫；以 reference 真實執行取得 expected values。
4. 前三筆原始 generation 跨越設定修正；另外使用最終 server config 獨立重驗，
   3/3 通過，保留 `runs/*/server-config-recheck.json`，沒有覆寫原始執行結果。
5. 最終 preflight：21/21 ready，見 `private/tasks-report.json` 與
   `output/log/revdev-scale-preflight-v3.log`。

## 儲存整理與協作

本輪 SHA256 驗證後已移至 HDD、刪除 SSD 實體資料：

- `JacLLM-SFT-Ornith-9B-toolfim-spike-bf16`
- `JacLLM-SFT-Ornith-9B-toolfim-spike_GGUF`

合計約 33 GiB；hash manifest 在 `output/log/archive-scaleup-verified.jsonl`。
刪除前再次確認 source 未變更；helper 留的 symlink 本身不佔模型容量。
其他目錄後續消失，使用者已確認另一個視窗正在整理，不能算成本輪搬移成果。
因此本輪暫停額外 model / adapter 搬移，避免競爭操作。
保留 trajectory bf16、1029 r16 continuation adapter、1022 trajectory baseline；
若要載入原始 1022 adapter，也需保留其 CPT v1.3A bf16 base。

## 資源與 artifacts

- Generator raw：`dataset/raw/revdev/scaleup_v1/`
- Export：`dataset/sft/{revdev_function,revdev_resume}/scaleup-v1/`
- 生成監控：`output/log/revdev-scale-generate-resources.jsonl`
- RAM floor 4 GiB、disk floor 20 GiB、GPU temperature limit 88°C，觸發時停止 child。
- Adapter boundary self-test 在本次共用 dispatch 重構後通過。

## 下一步

本輪 generation、token audit、r16 continuation、固定 capability comparison 均已完成。
後續應增加真實 workspace 路徑變化、offset=0 與錯誤後修正的任務覆蓋，
並另設未看過的評測；尚未執行下一輪擴量或訓練。

## 執行入口

```bash
python script/dataset/revdev/scale_tasks.py
python script/dataset/revdev/scale_generate.py
python script/dataset/revdev/scale_generate.py --export-only
python script/eval/probe/dataset_tokens.py --files dataset/sft/revdev_function/scaleup-v1/train.jsonl dataset/sft/revdev_resume/scaleup-v1/train.jsonl --out output/eval/revdev/scaleup-train-token-audit.json
python script/train/train.py --recipe script/train/recipe/1029-revdev-scaleup-r16/sft.yaml
```

需用 tornith environment；generation / training 外層另包 resource_watch。
第一次準備依賴已抽出的 `private/slices.json`；source repos 必須仍在原始路徑。
Generator 不會覆寫既有 runs；interrupted/rejected raw 也保留，不會自動重試 mutation。
訓練 recipe：1 epoch、lr 1e-4、r16/alpha16、4-bit base、16k packing、batch1。
從 `1029-revdev-r16/sft/adapter` 接續權重，optimizer 重新初始化；
新增訓練資料外，保留一筆既有 planning example。新輸出獨立放在
`output/adapter/1029-revdev-scaleup-r16/sft`。

## 訓練完成與精確統計

| Dataset | N | 平均完整 tokens | 平均 loss tokens | 總 loss tokens |
| --- | ---: | ---: | ---: | ---: |
| 新 function / repair | 9 | 3,291.44 | 549 | 4,941 |
| 新 resume | 5 | 2,875 | 597.4 | 2,987 |
| 保留 planning | 1 | 1,415 | 1,292 | 1,292 |
| 本次 training 合計 | 15 | 3,027.53 | 614.67 | 9,220 |

新產出的 14 筆（不含舊 planning）：平均 3,142.71 完整 tokens、566.29 loss tokens。
本次訓練總 context 45,413 tokens，loss 比例 20.30%；最長 4,628，沒有截斷。
總 loss tokens 是 pilot 實際訓練的 6.03 倍；function/resume 目標 7,928 tokens，
相較 pilot 的 function repair 238 tokens 約 33.31 倍。此為監督量比較，不是能力提升倍數。

實際完成 15 optimizer steps / 1 epoch，train runtime 32.5 秒（不含模型載入）；
train_loss 0.3229。產物 `output/adapter/1029-revdev-scaleup-r16/sft/adapter`。
256 個 tensor 全部有限值、全部相較原 r16 有變更；rank16 / alpha16 已確認。
證據：`output/eval/revdev/scaleup-train-token-audit.json`、
`scaleup-weight-audit.json`、`output/log/revdev-scale-train.log`。

精確 token 數使用與訓練相同的 tokenizer/chat template/loss mask。
`statistic.json` 的 chars/4 僅為通用估算，不可混用成上述數字。

## 最終資料與評測結果

新資料共 21 筆、3 repositories，全部接受，0 超長拒收。
Train：function/repair 9、resume 5；valid：function/repair 5、resume 2。
7 筆 valid 是經過驗證的 teacher examples，並不是 student 通過 7 題。
模型本輪評測沿用上一輪的固定小型 suite，沒有使用 Aegis valid 訓練或選參數。

21 筆合計 63,394 完整 tokens，11,643 loss tokens；平均 3,018.76 / 554.43，loss 比例 18.37%。
實際重播工具呼叫共 119 次（含 fixture seeds）；不計其他 oracle / acceptance 執行。

| 指標 | trajectory base | pilot r16 | scale-up r16 |
| --- | ---: | ---: | ---: |
| 六個下一步動作 | 2/6 | 2/6 | 2/6 |
| JSON schema 正確 | 6/6 | 6/6 | 6/6 |
| 首錯停止實作測試 | 0/2 | 0/2 | 0/2 |
| 明示工具限制＋錯誤回饋實作測試 | 0/2 | 0/2 | 0/2 |
| Plan 有 callable 參數及回傳介面 | 0/2 | 1/2 | 0/2 |

因此本輪沒有證明 dependency-aware 能力改善。兩個 live tasks 仍沒有成功寫入，
模型會提出錯誤 workspace 路徑、受限 shell 指令，且讀取仍出現 offset=1。
新規劃輸出也沒有保住 pilot pantry 的 signature 改善；有把 `by llm()` 誤述為 persistence
的內容。Plan 僅人工審閱，沒有執行，不能宣稱能編譯。
這是小型固定 regression probe；資料量變大、training loss 低都不能取代實際能力證據。

新報告：`output/eval/revdev/1029-r16-v2/scaleup-summary.json`；原 baseline summary 保留。
原始模型輸出在同目錄 `scaleup/` 與 `scaleup-feedback/`。

訓練＋評測監控：GPU 最高 12,473 MiB / 67°C，RAM 最少可用 43.43 GiB，
SSD 最少剩約 899.33 GiB，HDD 約 4,363 GiB，沒有 resource stop。
SSD 其他額外釋放由另一視窗整理造成，不算成本輪已驗證搬移量。
