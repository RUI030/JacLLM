# Serving a trained model to real agents

How a trained VLM adapter becomes a GGUF that jac_coder, opencode and pi can drive, and what broke on the way
(first done 2026-10-27 for `JacLLM-Ornith-9B-prod-img-sft` on a shared 48GB / 32GB-RAM box). Commands:
`script/eval/agent/README.md`. Upstream docs (unsloth, llama.cpp, opencode, pi): `docs/reference/serving/`.
GGUF conversion and the CUDA runtime for Studio's llama.cpp: `docs/CLOUD_GPU.md` "GGUF export".


## Pipeline

1. **Merge, keeping vision.** `script/merge_lora.py` loads through Unsloth with `text_only=True`, which drops
   `model.visual.*`. For a VLM adapter (`train/sft_img.py`), use `script/merge_lora_vlm.py`: a tensor-level
   `W += scale * B @ A` on the bf16 base shards (rslora scale `alpha/sqrt(r)`), every other tensor copied.
   Check it with `script/eval/probe/merge_loss.py`: merged must match base + adapter (unmerged), and both must
   differ from base (prod-img-sft: base 0.7600, unmerged 0.7046, merged 0.7058).
2. **Keep the trained chat template.** The merge copies the adapter's `chat_template.jinja` and removes the
   base's `chat_template` from `tokenizer_config.json` (it would override the file). `serve.sh` passes it with
   `--chat-template-file`; the GGUF's embedded template can be a different one (v1.35 shipped thinking-off).
   `smoke.py` compares the HF render with llama-server's `/apply-template` on training rows.
3. **Convert** text model and mmproj separately (`convert_hf_to_gguf.py`, then `--mmproj`), keep them in
   `output/gguf/<model>/` together with any quant.
4. **Serve** with `script/eval/agent/serve.sh` behind `log_proxy.py`, so every exchange is in
   `output/serve/<model>/calls.jsonl` whatever the client logs itself.
5. **Run agents** one at a time; render with `script/dataset/trajectory/view.py`.


## Pitfalls

### Server
- **llama-server's host prompt cache is 8 GiB by default** (`--cache-ram`). Under an 8G `MemoryMax` the server
  was OOM-killed mid-run. `serve.sh` uses `--cache-ram 1024`, and the unit cap is 10G.
- **A thinking model can think until `max_tokens`.** One jac_coder call thought 32,000 tokens (two lines
  repeated 687× each) and returned nothing (`finish_reason: length`). Count that as a failure class in evals.
- **Unsloth Studio needs `--disable-tools`** for agents: otherwise Studio runs its own tool loop and the
  agent's tool calls never come back to it. Its API key is printed in its log on first start.
- Reasoning comes back as `reasoning_content`; opencode needs `"interleaved": {"field": "reasoning_content"}`
  on the model to send it back on later turns.

### jac_coder (jacBuilder verification_runner)
- **jac 0.34.28 ignores `[byllm.model] base_url`** in `jac.toml`; requests went to OpenAI (401). litellm reads
  `OPENAI_BASE_URL` / `OPENAI_API_BASE`, which `run_jaccoder.sh` sets.
- `[byllm.compaction] ctx_window` × `threshold_ratio` decides when history is compacted into a
  `[Earlier conversation: N messages compacted…]` stub. Training data never contains that stub, and the
  model's first invented "fact" came right after the first compaction.
- Run the pinned `jac` from outside the jac source tree, or it imports the checkout instead of itself.

### Agents on a shared machine
- **The model runs `pkill -f jac`.** That killed the agent, its runner and the shared jac postgres
  (`~/.cache/jac/pg`, restarts on demand). `shims/` puts refusing `pkill`/`killall`/`pgrep` first on PATH, and
  agent units are named `agent-<name>` (no "jac").
- **`opencode run` attaches to a background `opencode serve --service`**, and starts one if none runs. A
  `timeout` on `opencode run` kills only the client: the session kept running for an hour in the service,
  outside the shims and the memory cap. Use `opencode run --standalone` (private server that exits with it).
- **Cut logs by client, not by time.** Two agents (or a smoke test) in the same window share `calls.jsonl`.
  `log_proxy.py` logs the User-Agent, and `view.py --client` also recognises jac_coder / opencode / pi by
  their system prompts.
- **agent-browser's Chrome fails with "No usable sandbox"** on Ubuntu (AppArmor blocks unprivileged user
  namespaces): `AGENT_BROWSER_ARGS=--no-sandbox`.
- Agents leave scratch files in `/tmp` (`test_*.jac`, screenshots, server logs) and background `jac start`
  processes; check `ps` after a run.

### Secrets
- API keys live in `~/.config/jacllm/` (mode 600), never in the repo or inline in client configs: opencode
  reads `{file:<path>}`, pi `"!cat <path>"`, llama-server `--api-key-file`.


## Viewing runs

`view.py` turns a proxy log, a jac_coder trace, SFT rows or trajectory rows into one standalone HTML page
(inline CSS, images as data URLs; jac_coder traces need `--embed` to inline their image files), with
repeated calls, near-repeats, error results, repeated thinking lines and `length` stops flagged at the top
of each session. Pages built from prod traces contain real user data: don't share them.
