#!/usr/bin/env bash
# Serve a merged model's GGUF with llama-server on 127.0.0.1:8081 (API key required) behind log_proxy.py on
# $LISTEN (default 127.0.0.1:8080 plus the tailscale IP when there is one). Logs go to output/serve/<model>/.
#   bash script/eval/agent/serve.sh <model> [bf16|Q4_K_M|...]
# Expects output/gguf/<model>/{<model>-<quant>.gguf, mmproj-<model>-f16.gguf} and, if present, uses
# output/model/<model>/chat_template.jinja (the template the adapter was trained with) instead of the GGUF's.
# Run it under a memory cap, e.g.
#   systemd-run --user --unit jacllm-serve -p MemoryMax=10G -p MemorySwapMax=0 bash script/eval/agent/serve.sh <model>
set -uo pipefail
MODEL="$1"; QUANT="${2:-bf16}"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
G="$ROOT/output/gguf/$MODEL"; OUT="$ROOT/output/serve/$MODEL"; mkdir -p "$OUT"
KEY_FILE="${KEY_FILE:-$HOME/.config/jacllm/llama_api_key}"
LLAMA_CPP="${LLAMA_CPP:-$HOME/.unsloth/llama.cpp}"                 # Unsloth Studio's prebuilt llama.cpp
NP="${NP:-2}"; CTX="${CTX:-98304}"                                 # per slot; prod trajectories were trained at <= 64k
TS_IP="$(tailscale ip -4 2>/dev/null | head -n 1)"
LISTEN="${LISTEN:-127.0.0.1:8080${TS_IP:+,$TS_IP:8080}}"
[ -s "$KEY_FILE" ] || { echo "no API key at $KEY_FILE (create one: install -m 600 /dev/null $KEY_FILE, then write a random token)"; exit 1; }

# Studio's CUDA backend needs the CUDA 13 runtime from its venv, else llama.cpp silently runs on CPU (docs/CLOUD_GPU.md).
for d in "$LLAMA_CPP/build/bin" "$HOME"/.unsloth/studio/unsloth_studio/lib/python3*/site-packages/nvidia/cu13/lib; do
    [ -d "$d" ] && LD_LIBRARY_PATH="$d:${LD_LIBRARY_PATH:-}"
done
export LD_LIBRARY_PATH
"$LLAMA_CPP/build/bin/llama-server" --list-devices 2>&1 | grep -q CUDA || { echo "llama-server sees no CUDA device"; exit 1; }

TEMPLATE=(); [ -f "$ROOT/output/model/$MODEL/chat_template.jinja" ] && TEMPLATE=(--chat-template-file "$ROOT/output/model/$MODEL/chat_template.jinja")
# --cache-ram: the host-RAM prompt cache defaults to 8 GiB and got the server OOM-killed under a 8G cap (docs/SERVING.md)
"$LLAMA_CPP/build/bin/llama-server" \
    -m "$G/$MODEL-$QUANT.gguf" --mmproj "$G/mmproj-$MODEL-f16.gguf" "${TEMPLATE[@]}" --jinja \
    -ngl 99 -fa on -np "$NP" -c $((NP * CTX)) --alias local \
    --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 \
    --cache-ram 1024 \
    --api-key-file "$KEY_FILE" --metrics \
    --host 127.0.0.1 --port 8081 \
    --log-file "$OUT/llama_server.log" --log-timestamps --log-prefix &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
until curl -sf http://127.0.0.1:8081/health >/dev/null; do
    kill -0 $SERVER 2>/dev/null || { echo "llama-server died"; tail -n 20 "$OUT/llama_server.log"; exit 1; }
    sleep 2
done
echo "llama-server ready"
python3 "$ROOT/script/eval/agent/log_proxy.py" --listen "$LISTEN" --upstream 127.0.0.1:8081 --log "$OUT/calls.jsonl"
