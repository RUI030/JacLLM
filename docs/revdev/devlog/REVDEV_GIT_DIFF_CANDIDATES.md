# JacHacks Git diff 作為 debugging 資料候選

日期：2026-10-28。四個公開 repo 的完整 Git 歷史已下載到 `/tmp`，
以下數字只涵蓋目前預設分支可達的 commit；`fix` 類數字是訊息關鍵字
粗篩，不是可直接輸出的 SFT 樣本數。

| Repo | 全部 commits | 非 merge | 修改 `.jac` 的非 merge | 訊息含 fix/bug/error/crash/repair 的非 merge |
| --- | ---: | ---: | ---: | ---: |
| [Mindcraft](https://github.com/Mr-Shockwave/Mindcraft) | 23 | 16 | 11 | 3 |
| [Alongside](https://github.com/nathansso/Alongside) | 83 | 50 | 33 | 21 |
| [BlastRadius](https://github.com/KangJustin/blastradius) | 66 | 66 | 22 | 7 |
| [AEGIS ForkGuard](https://github.com/Rafa-Innerchispa/aegis-forkguard) | 23 | 21 | 7 | 7 |

## 已重現的 red → green 例子

[Alongside commit `c6831e0`](https://github.com/nathansso/Alongside/commit/c6831e0c39ad46fb8c5d744f95142a0fb6e71785)
修正 `read.test.jac` 的測試間 fixture 依賴；其 parent 是
`ab975397e7a65a49f04d66408bd1aad338040213`。在兩個乾淨、分離的
worktree 以同一 Jac 0.34.27 執行 `jac test read.test.jac`：

| 原始狀態 | 結果 |
| --- | --- |
| parent | exit 1：8 failed、24 passed；失敗測試找不到先前測試建立的 graph nodes。 |
| 修正 commit | exit 0：32 passed。 |

原始執行輸出留在 `/tmp/revdev_alongside_before_test.log` 與
`/tmp/revdev_alongside_after_test.log`。這個 commit 只修改
`read.test.jac`（新增每個測試自己的 seed helper），是可重現的
**test-debugging** 範例；不應標成 production bug 修復。commit metadata
標有 Claude Opus co-author，須保留來源標記，不能當作「純人寫」樣本。

[BlastRadius commit `821b551`](https://github.com/KangJustin/blastradius/commit/821b55190b62005922450c3e40b8362d9318926c)
也有明確的錯誤處理與新增測試：不存在的 repo path 改為拋
`FileNotFoundError`，未知函數回傳 `found=False`。但其 HEAD 在目前
0.34.27 harness 下 `jac check` 失敗；本次尚未對該 commit 做 red/green
重現，因此只列候選。

## 資料集設計判斷

Git diff 可以提供 `before` workspace、修改目標與 `after` 參考答案；
commit/issue 描述可作為自然語言需求的證據，但必須改寫並檢查是否洩漏
具體 patch。每個樣本至少保存 repo/parent/commit、Jac/runtime 版本、
變更檔案、前後測試命令與**實際**輸出、diff hash、可見上下文與排除原因。
學生只看 parent 狀態、需求與前置失敗；after diff 只供評分與監督。

先分成 `revdev_debug`（真實 red → green）及 `revdev_change`（功能新增，
需求和驗證均有證據）。單純 merge、autosave、格式調整、沒有可重現
前置失敗的 `fix` commit，不要自動升格為 debugging。原始 Git 歷史不含
當時 agent 的工具呼叫，若要 tool-use SFT，必須在 parent checkout 以
真實 JacCoder harness 重新執行並記錄，不能把 diff 偽裝成過去的 trajectory。
