# Serving reference docs

Official docs for hosting a fine-tuned model behind an OpenAI-compatible endpoint, fetched 2026-10-27 as Markdown. These are snapshots: re-fetch before relying on a flag that may have changed.

- `unsloth/`: from `https://unsloth.ai/docs/<page>.md` (index: `https://docs.unsloth.ai/llms.txt`).
- `llama.cpp/`: from `ggml-org/llama.cpp` master @ `63b4b30`. The local build in `~/llama.cpp` is at `1ddffe9` (2026-10-24), and Unsloth Studio bundles its own build in `~/.unsloth/llama.cpp`.

## Unsloth

| File | Page |
|---|---|
| `api-endpoint.md` | Unsloth as an API endpoint: OpenAI `/v1/chat/completions` + `/v1/responses` and Anthropic `/v1/messages` on one port, API keys, model loading |
| `api-curl-http.md` | Every endpoint as curl recipes |
| `api-python-sdk.md` | OpenAI/Anthropic SDK against Unsloth: streaming, vision, function calling |
| `studio-intro.md`, `studio-start.md`, `studio-install.md` | Unsloth Studio overview, getting started, install |
| `studio-run-models.md` | Running models and GGUFs in Studio chat |
| `studio-export.md` | Exporting safetensors/LoRA to GGUF and other formats from Studio |
| `studio-security.md` | Studio security notes |
| `connections.md`, `connect-llama-server.md`, `connect-vllm.md` | Connecting external model servers (llama-server, vLLM) to Studio |
| `lan-access.md` | Serving to other machines on the network |
| `inference-and-deployment.md` | Overview of save/deploy targets |
| `saving-to-gguf.md` | `save_pretrained_gguf` / merged 16-bit → GGUF |
| `llama-server-openai-endpoint.md` | Deploying with llama-server as an OpenAI endpoint |
| `vllm-guide.md`, `vllm-engine-arguments.md`, `vllm-lora-hot-swapping.md` | vLLM serving, flags, LoRA hot swap |
| `sglang-guide.md` | SGLang serving |
| `speculative-decoding.md` | Speculative decoding with llama-server / vLLM |
| `troubleshooting-inference.md` | Common save/run failures |
| `tool-calling-local-llms.md` | Tool calling with local models |
| `chat-templates.md` | Chat template basics and customization |
| `qwen3.5-run-locally.md`, `qwen3.5-fine-tune.md` | Qwen3.5 (the Ornith base family): run settings and fine-tuning |

## llama.cpp

| File | Source |
|---|---|
| `server.md` | `tools/server/README.md`: every `llama-server` flag and endpoint (`--jinja`, `--chat-template-file`, `--mmproj`, `--reasoning-format`, `/apply-template`, …) |
| `function-calling.md` | `docs/function-calling.md`: tool-call parsing per template |
| `autoparser.md` | `docs/autoparser.md`: template-driven tool/reasoning parser |
| `multimodal.md`, `mtmd.md` | `docs/multimodal.md`, `tools/mtmd/README.md`: mmproj and vision serving |
| `preset.md` | `docs/preset.md`: server presets |
| `speculative.md` | `docs/speculative.md` |
| `multi-gpu.md` | `docs/multi-gpu.md` |
| `build.md`, `install.md` | Building and installing llama.cpp |

## Coding-agent clients (`clients/`)

| File | Source |
|---|---|
| `unsloth-opencode.md` | `https://unsloth.ai/docs/integrations/opencode.md`: OpenCode against Unsloth (`unsloth start opencode`, custom provider, `--disable-tools`) |
| `opencode-providers.mdx`, `opencode-config.mdx` | `sst/opencode` dev, `packages/web/src/content/docs/`: custom `@ai-sdk/openai-compatible` providers, `{file:}` / `{env:}` substitution, model `limit` |
| `pi-models.md`, `pi-models-configuration.md`, `pi-README.md` | `badlogic/pi-mono` main, `packages/coding-agent/`: `~/.pi/agent/models.json` providers, every model field, `compat` |

Local configs written from these (2026-10-27): `~/.config/opencode/opencode.json` and `~/.pi/agent/models.json`, each with providers `jacllm-llama` (`http://127.0.0.1:8080/v1`, model `local`) and `unsloth-studio` (`http://127.0.0.1:8888/v1`, model `JacLLM-Ornith-9B-prod-img-sft-Q4_K_M`). Keys are read from `output/serve/10-27-prod-img-sft/{api_key,unsloth_api_key}`, never inlined.
