# JacHacks Devpost 候選盤點（2026-10-27）

目標：從 [SF gallery](https://jachacks-sf.devpost.com/project-gallery) 與
[a2Tech gallery](https://jachacks-a2tech.devpost.com/project-gallery) 找 M3 可用的
公開 Jac repo。Gallery 顯示 SF 77 件、a2Tech 27 件；這是作品數，**不是**
已驗證可用的 repo 數。本次只抽查下列四個 SF 候選，未完成 104 件逐一盤點。
本機 `dataset/raw/repo/JacHackA2Tech/` 已有 20 個 repo 目錄，整個
`dataset/raw/repo/` 有 35 個 repo 目錄；本次沒有把 SF 候選加入 raw。

檢查方法：在 `/tmp` 下載公開 repo，以 JacBuilder 現行 harness 的
`/tmp/jac-0.34.27-linux-x86_64` 對**未修改**的原始碼執行 `jac check main.jac`；
Mindcraft 另跑 `jac test tests/core_tests.jac`；Alongside 跑
`jac test read.test.jac`。下載位置與檢查產生的檔案
不屬於 dataset。

| 候選 | 原始碼／版次 | 原樣 0.34.27 結果 | M3 判斷 |
| --- | --- | --- | --- |
| [Mindcraft](https://devpost.com/software/mindcraft-6xdj94) | [GitHub](https://github.com/Mr-Shockwave/Mindcraft) `38ccad5e7b5ca76481a2cd790283f5824b636d42`；`main.jac` 1,522 行，測試 204 行 | `jac check main.jac` exit 0（有 warnings）；14/14 Jac tests 通過；全端 HTTP 入口及 `get_world` walker 通過 [smoke](REVDEV_M3_SMOKE.md) | 目前最有證據的候選。單一大檔對 64k trajectory 很不友善；尚未以瀏覽器操作畫面或讓 JacCoder 重建完整 app。 |
| [Alongside](https://devpost.com/software/alongside) | [GitHub](https://github.com/nathansso/Alongside) `00c7b3ee09e778e9dc7d09293a665435f62cd449`；核心 `main.jac` 377 行，另有 `graph.jac`、`page.cl.jac`、`read.jac`、`write.jac`，核心 Jac 合計約 3,955 行 | `jac check main.jac` exit 0；`read.test.jac` 32/32 tests 通過 | 編譯和部分測試有證據；目前 repo 已不是 Devpost 所述單檔，完整重建規模偏大，其他模組與全端啟動尚未驗證。 |
| [BlastRadius](https://devpost.com/software/blastradius-0p2tw8) | [GitHub](https://github.com/KangJustin/blastradius) `2121d9af0bad7b8e7940d33745f5a5400115cbc7`；`jac.toml` 鎖 `==0.34.7`；含 client 與多個 UI 檔 | `jac check main.jac` exit 1：`graphdata.jac:22` 語法錯誤 | 不可直接當 0.34.27 ground truth；作品頁「四個 Jac 檔」不代表目前 GitHub repo 全貌。 |
| [AEGIS ForkGuard](https://devpost.com/software/aegis-forkguard) | [GitHub](https://github.com/Rafa-Innerchispa/aegis-forkguard) `ec43bc688d2744bfbd71a8cf7c69e5b276fd9eb9`；9 個 Jac 檔含測試；`AGENTS.md` 稱以 Jac 0.16.7 驗證 | `jac check main.jac` exit 1：25 errors、24 warnings，包含舊 lambda 語法 | 目前不適合 0.34.27 harness；原 repo 可能在其作者使用的版本可跑，本次未檢查。 |

Alongside 的 Devpost 頁面沒有 GitHub 連結；公開 repo 是經作者的
[portfolio 記錄](https://github.com/nathansso/portfolio/blob/main/progress.md)
找到並另行下載確認。作品頁的單檔描述對目前 HEAD 不再準確。

Mindcraft 已完成隔離的 `jac start` 與 harness tool-call smoke test；若要以它
做完整 M3，仍須做瀏覽器操作，並先量測原樣重建的 token 用量。
若超過 64k，選較小的已驗證 repo，或依原定 checkpoint/resume 規格切段。
不可只憑 `jac check`／測試通過就產出「成功重建」的 trajectory。
