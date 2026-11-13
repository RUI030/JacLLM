#!/usr/bin/env bash
# Serve a GGUF with Unsloth Studio on 127.0.0.1:8888 (OpenAI-compatible /v1, plus the Studio web UI).
#   bash script/eval/agent/serve_unsloth.sh <model> [Q4_K_M|bf16|...]
# Studio prints its API key in the log on first start; copy it to ~/.config/jacllm/unsloth_api_key for opencode/pi.
# --disable-tools: without it Studio runs its own tool loop and the agent's tool calls never reach the client.
set -uo pipefail
MODEL="$1"; QUANT="${2:-Q4_K_M}"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$ROOT/output/serve/$MODEL"; mkdir -p "$OUT"
exec "$HOME/.local/bin/unsloth" run --model "$ROOT/output/gguf/$MODEL/$MODEL-$QUANT.gguf" --disable-tools \
    --max-seq-length 65536 -p 8888 -H 127.0.0.1 \
    --temperature 0.6 --top-p 0.95 --top-k 20 --min-p 0 > "$OUT/unsloth_run.log" 2>&1 < /dev/null
