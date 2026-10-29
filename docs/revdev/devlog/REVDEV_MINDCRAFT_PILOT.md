# Mindcraft pilot：M1/M2 與 M3 checkpoint 實測

日期：2026-10-28。M3 尚未完成，正式 SFT 產出為 0。

## 已完成

- 固定 reference `Mr-Shockwave/Mindcraft@38ccad5e7b5ca76481a2cd790283f5824b636d42`，Jac 0.34.27。
- M1 抽取 22 files、63 symbols、286 dependencies、65 unresolved、0 cycles；baseline passed。Unresolved 仍需依任務範圍審查，不能視為全部已解析。
- M2 建立 `mindcraft_core_a`：無 AI key 的核心流程，五個規劃檔案依序為 `jac.toml`、`services/island.jac`、`styles.css`、`components/MindcraftApp.jac`、`main.jac`。
- 實際 JacBuilder planner 寫入 plan，MainAgent 寫入 config 與 service scaffold；保存 cp0，驗證檔案 hash 後恢復到新 workspace。
- 恢復後，實際 MainAgent dispatch 依序執行三次 `write_code`（其餘 scaffolds）、兩次 `read_file`（plan、service）、一次 `edit_code`（get_world）。Component、main 與 service 的內建 Jac check 全部回報 ok，probe passed。
- 保存 cp1，六個檔案包含五個規劃檔與 build plan。`plan_consistency=scaffold_only`、`implementation_state=unverified`，避免 harness 的 done 狀態被誤認為功能完成。

## 證據與限制

Capture 位於 `dataset/raw/revdev/Mindcraft/m3/private/prefix_capture_v2.json` 與 `resume_capture_v2.json`；checkpoint 位於 `m3/runs/scripted_prefix_v2/checkpoints/`。舊版 probe 在所有 scaffolds 完成前實作 body，已由 v2 取代，不供匯出。

使用 scripted MockLLM 決定呼叫內容，工具 dispatch、寫檔與檢查結果則來自真實 harness。這證明 checkpoint 與工具串接可運作；尚不能作為模型自主開發的 SFT trajectory。環境尚未配置可用的模型 API key 或本機推論服務。

Ornith-1.5-9B chat template 的預算量測：planner 10,166 tokens、MainAgent prefix 16,158、resume probe 18,339。這些是將觀測 calls/results 配對後的 packing 量測，尚非正式 provider transcript 或完整 app 的 token 數。

初次從 JacLLM cwd 啟動 probe 時找不到 jac_coder；改從 JacBuilder cwd 執行即通過。執行入口必須記錄 harness cwd，僅設 PYTHONPATH 不足以重現此 runtime。

## 下一步

完成可配置模型的 capture runner，再執行完整 scoped app build；保留失敗與修正，驗證功能、依賴 inspection 與 checkpoint replay，之後才進入 M4 segmentation 和五類 SFT 匯出。目前 get_world 僅通過靜態檢查，其餘 service bodies 和 client interactions 尚未實作。
