# Revdev r16 模型能力比較

2026-10-29，成對評測與補測已完成。比較 trajectory 合併基底與本次 r16 adapter。相同 frozen suite、greedy decoding、16k context、每回合 1,024 output tokens，沒有截斷輸入。兩個模型分開進程載入，資源每五秒抽樣。

評測規格與事先固定 rubric：[script/eval/revdev/README.md](../../../script/eval/revdev/README.md)。實際 suite 與輸出：`output/eval/revdev/1029-r16-v2/`。這是 6 個下一步決策、2 個規劃、2 個最多六回合的真實工具實作；非大型 held-out benchmark。

## 評測器預檢修正

- 第一版 oracle 使用 invoice.test.jac 與同名 module，Jac 0.34.27 import collection 失敗。改成 test_invoice.jac / test_greeting.jac 與相對 imports，兩個 oracle 均通過後才測模型。原失敗目錄保留。
- 第一次 before 輸出的工具布林是原生 template 的 `False`。解析器原只接受 JSON `false`，已修正並用原輸出驗證。此輪保留為 before-parser-invalid，不採計；兩個模型使用同一修正版重新評測。
- 同一 assistant response 中同時發出 read 與 write，不算已觀察 read result；dependency inspection 分數只看前面已完成回合。

## 範圍

訓練只有 2 筆、2 steps：planning projection + function repair projection。scaffold、app、resume 的資料雖已產出，但本輪沒有訓練。新題沒有被用來更新模型。自訂小測試只能提供初步行為證據，不能宣稱整體能力或完整 app 成功率改善。

## 第一輪成對結果

| 指標 | trajectory 基底 | revdev r16 |
|---|---:|---:|
| 工具參數符合 JSON schema | 6/6 | 6/6 |
| 同時符合 workspace／command policy | 2/6 | 2/6 |
| 選對下一步行為 | 2/6 | 2/6 |
| 新 plan 有 callable 參數與回傳簽名 | 0/2 | 1/2 |
| 完整 scaffold-first dependency order | 0/2 | 0/2 |

兩邊皆通過 cached-read 後直接 edit 與補齊 missing scaffold。兩邊皆未通過 unseen dependency、stale dependency、resume、可執行 verification。注意：JSON schema 6/6 不等於選對工具／路徑；`schema_valid` 原始欄位還含 adapter policy，summary.json 已拆開。

Planning 手動 rubric（每題五項，細項在 summary.json）：library 3→3、pantry 3→4。唯一明確提升是 pantry 出現 `load_items() -> list[PantryItem]`、`add_item(name: str, quantity: int = 0) -> PantryItem` 等 callable contracts。這是兩題中的局部跡象，不是穩定能力提升。Library 新 plan 雖拆了更多 modules，但 引入 copies/available_copies，需要檢查是否符合「已借出的書不能再借」規則。兩個版本的 plan 都未執行成 app。

第一輪兩個 live tasks 均在第二回合被 adapter command policy 擋下，0 writes，不能把 0/2 completion 直接解讀成程式邏輯能力 0/2。已追加**兩邊**相同的六回合補測：顯式告知命令 allowlist，將實際 validation error 回傳給模型，使它有機會修正。第一輪不刪除或覆蓋。

兩邊 tokenizer.json 與 chat_template.jinja 的 SHA256 相同，suite hash 相同；新 adapter 依共用 loader 做 in-memory merge。原生 tokenizer regex warning 兩邊都有，本次保持訓練時的 tokenizer，不在比較中途修改。所有 plan 都未碰到 1,024 output-token 上限。

## 已定位的工具語意問題

基準模型在補測中用 `read_file(offset=1)` 讀一行的 rates.jac；實際工具 offset 是零起算，因此回傳只有 `(1 total lines)`，沒有函式定義。模型接著嘗試被禁止的 sed/wc/find，而沒有改為 offset=0。這不能視為已驗證 dependency signature。實作在 `jacBuilder/jac_coder/tool/read/filesystem.impl.jac` 的 `lines[offset:offset + limit]`，預設 offset=0；captured schema 對 offset 只寫 int，沒有語意說明。

因此「有呼叫 read_file」還不夠。之後資料驗證需要確認讀到所需符號，並包含空頁後修正讀取範圍的成功軌跡；也應讓工具 schema 明確描述 offset 語意。本輪保留現有真實 schema，不在兩模型比較中途偷偷補上答案。

## 補測與最終結論

明確 command policy + 真實拒絕回饋的六回合補測：

| 指標 | trajectory 基底 | revdev r16 |
|---|---:|---:|
| 完成修改且 evaluator 測試通過 | 0/2 | 0/2 |
| 進入成功寫檔 | 0/2 | 0/2 |
| Agent 自行執行測試 | 0/2 | 0/2 |

兩邊都在讀取/命令選擇階段卡住；這不是已完成程式的演算法正確率。Rates/labels 都只有一行，offset=1 會漏掉整個定義；模型未在六回合內改正讀取範圍，並持續嘗試契約不允許的 shell 指令。結果顯示目前部署工具契約下，無法可靠完成這兩題。它不代表給更多回合或別的 harness 也一定失敗。

**目前沒有證據顯示核心 dependency-aware 開發流程改善。** 有一題 planning 的 callable contracts 更具體，但下一步決策、dependency 更新、resume 與實際完成率沒有提升。只有 2 個 SFT samples / 2 optimizer steps，且 scaffold/app/resume 根本沒有參與這次訓練，因此不能把此結果解讀成 revdev 方法或 r16 本身無效。

下一輪應先增加可完整放入訓練 context 的跨 repo 工具軌跡，包含 offset 空頁修復、依賴變更後 refresh、沿用未變更 reads、resume 與測試失敗後修復；同時為工具 schema 補齊參數語意。保留這組作回歸測試，另加未用於資料設計的 repo 評測，避免只對這幾題調整。這些是建議，尚未進行新一輪訓練。

## 資源與原始證據

127 次資源抽樣（含預檢及保留的失敗嘗試）：VRAM 最高 9,923 MiB、GPU 最高 61°C、RAM 可用最低 40.73 GiB、SSD 可用最低 820.34 GiB、HDD 可用最低 4,395.50 GiB；沒有觸發停止門檻。完成後推論進程已退出，GPU 回落至約 1.35 GB／35°C。峰值為五秒抽樣，不是硬體瞬時最大值。

- 統計：`output/eval/revdev/1029-r16-v2/summary.json`。
- 固定題目、真實 seed reads、oracle 預檢：同目錄 suite.json、seed_results/、oracle/。
- 原始模型輸出：before/、after/ 的 predictions.json；六回合補測為 before-feedback/、after-feedback/。
- 每步原始輸出、實際工具結果及 evaluator test stdout/stderr：各 tag 的 *-events.json、tool_results/、*-check.json。
- 載入方式：共用 load_model，4-bit inference，新 adapter 依既有 Ornith 路徑 in-memory merge；未改動 SSD 上模型權重。
- 日誌：`output/log/revdev-eval-*.log` 與 `*-resources.jsonl`。


## 擴量後補測

已用同一 fixed suite 評估 scale-up r16：動作仍 2/6，兩種 live rollout 都 0/2。
詳見 [scale-up 紀錄](REVDEV_SCALEUP.md)；原始 pilot 分數與輸出未覆寫。
