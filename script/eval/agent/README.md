# Agent eval: a served GGUF driving real coding agents

Serve a merged model with llama-server behind a logging proxy, then point jac_coder (jacBuilder's
verification_runner), opencode or pi at it on a scenario stage, and render what the model did.
Pitfalls and background: `docs/SERVING.md`.

```
script/eval/agent/
  serve.sh            llama-server (bf16/quant GGUF + mmproj, trained chat template) behind log_proxy.py
  serve_unsloth.sh    the same GGUF through Unsloth Studio (port 8888) for its web UI / `unsloth start opencode|pi`
  log_proxy.py        transparent proxy that appends every /v1 exchange to output/serve/<model>/calls.jsonl
  smoke.py            template parity vs training, plain chat, streamed tool call, vision → smoke.json
  run_jaccoder.sh     jac_coder on a scenario (verification_runner, IDE mode)
  continue_run.py     the same scenario again in fresh sessions on the project the last one left; git commit per session
  run_agent.sh        opencode or pi on a scenario stage in a fresh empty Jac full-stack project
  scenarios/<name>/   manifest.json + stage_N.md in verification_runner's format
  shims/              pkill/killall/pgrep that refuse (PATH-first for the agents)
```

## Run

```bash
# 0. once: model files and keys
python script/merge_lora_vlm.py --base <bf16 vlm base> --adapter <adapter> --out output/model/<model>
#    convert/quantize into output/gguf/<model>/{<model>-bf16.gguf, <model>-Q4_K_M.gguf, mmproj-<model>-f16.gguf}
#    (docs/CLOUD_GPU.md "GGUF export"); API key: ~/.config/jacllm/llama_api_key (mode 600, any random token)

# 1. serve (RAM-capped; one RAM-heavy job at a time on a shared box)
systemd-run --user --unit jacllm-serve -p MemoryMax=10G -p MemorySwapMax=0 \
    bash script/eval/agent/serve.sh <model>
python script/eval/agent/smoke.py --model <model>            # needs the training env (transformers, sft_img)

# 2. agents, one at a time (they share the server and the jac postgres)
systemd-run --user --unit agent-jaccoder -p MemoryMax=8G -p MemorySwapMax=0 --wait \
    bash script/eval/agent/run_jaccoder.sh <model>
systemd-run --user --unit agent-opencode -p MemoryMax=8G -p MemorySwapMax=0 --wait \
    bash script/eval/agent/run_agent.sh opencode <model>
systemd-run --user --unit agent-pi -p MemoryMax=8G -p MemorySwapMax=0 --wait \
    bash script/eval/agent/run_agent.sh pi <model>

# 3. look
python script/dataset/trajectory/view.py output/eval/agent/<scenario>/<run>/calls.jsonl --client pi --out view.html
python3 -m http.server 8090 --bind <tailscale-ip> --directory output/eval/agent     # browse runs remotely
```

Unit names must not contain "jac": the model has run `pkill -f jac`.

## Output

- `output/serve/<model>/`: `llama_server.log`, `calls.jsonl` (every API exchange through the proxy, all clients),
  `unsloth_run.log`, `smoke.json`, `REPORT.md`.
- `output/eval/agent/<scenario>/<agent>-<model>_<MM-DD_HH-MM>/`
  - jac_coder: verification_runner's `run.json` + `artifacts/` (events, screenshots, project snapshot), `run.log`.
  - opencode / pi: `prompt.txt`, `agent.jsonl` (the agent's own events), `agent.err`, `exit_code`,
    `diff.patch` (lock files excluded), `diff_stat.txt`; the project itself lives in a temp dir and is deleted.
  - both: `calls.jsonl` (proxy lines in the run's time window; `view.html` keeps only this agent's sessions)
    and `view.html` (standalone: inline CSS, images as data URLs, no external requests).

## Client configs (outside the repo)

opencode `~/.config/opencode/opencode.json`:
```json
"provider": {
  "jacllm-llama": {
    "npm": "@ai-sdk/openai-compatible",
    "options": {"baseURL": "http://127.0.0.1:8080/v1", "apiKey": "{file:/home/<user>/.config/jacllm/llama_api_key}"},
    "models": {"local": {"reasoning": true, "interleaved": {"field": "reasoning_content"}, "tool_call": true,
                         "attachment": true, "modalities": {"input": ["text", "image"], "output": ["text"]},
                         "limit": {"context": 65536, "output": 32000}}}
  }
}
```
pi `~/.pi/agent/models.json`: provider `jacllm-llama` with `"api": "openai-completions"`,
`"baseUrl": "http://127.0.0.1:8080/v1"`, `"apiKey": "!cat /home/<user>/.config/jacllm/llama_api_key"`, model `local` with
`reasoning: true`, `input: ["text", "image"]`, `contextWindow: 65536`, `maxTokens: 32000`.
The `unsloth-studio` providers are the same with port 8888, `unsloth_api_key` and the served model id
(the GGUF file name without `.gguf`). Docs: `docs/reference/serving/clients/`.

jac_coder: jacBuilder's `jac.toml` `[byllm.compaction] ctx_window` should match the served context (65536 was
used: the model was trained at <= 64k); `run_jaccoder.sh` sets the base URL through env vars.
