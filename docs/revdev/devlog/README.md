# Reverse Development 開發紀錄

這個資料夾放每個階段的實測結果、遇到的問題與尚未完成的驗證。
流程設計與資料格式仍在 [總覽](../../REVDEV.md)、
[實作計畫](../../REVDEV_IMPLEMENTATION_PLAN.md) 和
[artifact 規格](../../REVDEV_ARTIFACTS.md)。

| 紀錄 | 內容 |
| --- | --- |
| [M0](REVDEV_M0.md) | JacCoder harness 工具 schema 與基本工具呼叫 |
| [M1](REVDEV_M1.md) | Jac AST／依賴抽取與第一個 repo baseline |
| [M2](REVDEV_M2.md) | Grounded task、plan 與參考 app 驗證 |
| [JacBuilder 0.36.1](REVDEV_JACBUILDER_0361.md) | 隔離升版測試、通過項目與阻礙 |
| [Devpost 候選](REVDEV_DEVPOST_CANDIDATES.md) | SF／a2Tech 作品盤點與 0.34.27 原樣檢查 |
| [Mindcraft M3 smoke](REVDEV_M3_SMOKE.md) | 原始全端啟動及 JacCoder 工具 dispatch |
| [Mindcraft pilot](REVDEV_MINDCRAFT_PILOT.md) | M1/M2、完整 scaffold 順序、checkpoint 恢復與 token 預算 |
| [Claude adapter](REVDEV_CLAUDE_ADAPTER.md) | 真實 teacher、階段檢查、r16 訓練與資源監控 |
| [Git diff 候選](REVDEV_GIT_DIFF_CANDIDATES.md) | 四個 repo 的 commit 密度與一個 red → green 範例 |

原始命令輸出、完整 harness capture 和 reference artifact 保留在
gitignored 的 `dataset/raw/revdev/` 與
`script/dataset/trajectory/harness/`；這裡只記錄可檢閱的結論與路徑。
新的階段紀錄也放在此資料夾，並更新本索引。

- [Actual dataset preview](REVDEV_DATASET_PREVIEW.md)：五類 8 筆、實際片段、tokens 與本機訓練範圍。

- [Model capability comparison](REVDEV_MODEL_EVAL.md)：trajectory 與 revdev r16 成對新題、真實工具補測與限制。

- [Scale-up](REVDEV_SCALEUP.md)：21 個模組任務、精確 loss tokens、真實 replay 與儲存整理。

- [真實多檔擴充方案](REVDEV_MULTIFILE_PLAN.md)：本機候選、基線檢查、雙檔寫入與 acceptance 門檻。

- [多檔 smoke 實測](REVDEV_MULTIFILE_SMOKE.md)：雙檔重播、原始行為測試與拒絕案例。

- [A2-Pulse 雙檔行為軌跡](REVDEV_A2PULSE_TWOFILE.md)：原測試 23/23、日期測試獨立重跑、64k valid 匯出。

- [m-local 雙檔行為軌跡](REVDEV_MLOCAL_CONTEXT.md)：原測試 13/13、reference oracle、失敗後修正與 64k train 匯出。
