# Mindcraft M3 前置 smoke：全端啟動與 JacCoder 工具

日期：2026-10-27；參考 repo：[Mr-Shockwave/Mindcraft](https://github.com/Mr-Shockwave/Mindcraft)
`38ccad5e7b5ca76481a2cd790283f5824b636d42`。執行環境使用 JacBuilder
現行的 Jac 0.34.27；參考 repo 與 harness 都沒有修改。這是 M3 前置驗證，
**不是** app 重建 trajectory。

## 原始全端專案

在 `/tmp/revdev-mindcraft` 執行
`jac start main.jac --port 38139 --no-dev`：client dependencies 安裝完成，
client bundle build 完成，server 報 `Server ready`。sandbox 禁止本機
socket，首次啟動報 `Operation not permitted`；經許可在 sandbox 外重跑後成功。

| 實際請求 | 結果 |
| --- | --- |
| `GET /` | HTTP 200；HTML 內有 `/static/client.js` 與 `walker:get_world` 等 endpoint metadata；原始回應在 `/tmp/revdev_mindcraft_home.http`。 |
| `POST /walker/get_world`，body `{}` | HTTP 200；Jac walker 的 `reports` 包含 `entities: []` 與四個工具定義；原始回應在 `/tmp/revdev_mindcraft_world.http`。 |

這證明原 repo 的 client build、HTTP 入口與一條 server walker 路徑能啟動。
尚未以瀏覽器操作畫面，也未走需要 byLLM 模型的寫入路徑。

## 實際 JacCoder 工具呼叫

[mindcraft_harness_smoke.jac](../../../script/dataset/revdev/mindcraft_harness_smoke.jac)
沿用 M0 的 JacBuilder 初始化和 `MainAgent.respond`，用 MockLLM 指定
`write_code` 呼叫，在乾淨 `/tmp` workspace 寫入一個 Mindcraft 型態的
`MindIsland`／`get_world` scaffold。真實 MainAgent dispatch 的 tool result 是
`OK: main.jac (4 lines)`；JacCoder 自動 `Check main.jac -> ok`。其後真實
`read_file` 回傳四行編號內容，`run_command("pwd")` 回傳該 workspace。
probe 的 Jac test 1/1 通過。

完整 request messages、27 個 live tool schemas、dispatch args/result 與
direct results 存於 gitignored
`dataset/raw/revdev/Mindcraft/m3/private/harness_smoke.json`。首次 request
的 sorted-JSON schema SHA-256 為
`9155fa1d7371901f3a9c30af7343e353c38aba935bc4e7f8ee488236d88cabb5`，
與 M0 capture 相同。MockLLM 的 `tool_call_id` 仍為空字串；它沒有測到
真實 provider 產生的 ID。此 probe 的工具選擇是預設的，不是模型自主
規劃，也沒有實作完整 Mindcraft。

下一步 M3 仍需：用受限 student workspace 從零產生完整檔案、逐段保留
真實工具結果、控制 64k token 上限，並對重建出的 app 重做啟動和驗證。
