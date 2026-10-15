#!/usr/bin/env bash
# Serve a GGUF with llama-server and run the pi tool-use FIM eval (run_eval.py) against it.
#   bash script/eval/tool_fim/serve_eval.sh <gguf> <tag> [limit] [parallel]   (limit 0 = whole valid split)
set -uo pipefail
GGUF="$1"; TAG="$2"; LIMIT="${3:-0}"; NP="${4:-4}"
cd "$(dirname "$0")/../../.."
PY="${PY:-/home/imrui/miniforge3/envs/tornith/bin/python}"
LLAMA_CPP="${LLAMA_CPP:-$HOME/.unsloth/llama.cpp}"                 # Unsloth Studio's prebuilt llama.cpp
PORT="${PORT:-8080}"
CTX=24576                                                          # per slot: trajectories run to ~8k; v1.3-A thinks at length and overflowed 16k

# Studio's CUDA backend needs the CUDA 13 runtime from its venv, else llama.cpp silently runs on CPU (docs/CLOUD_GPU.md).
for d in "$LLAMA_CPP/build/bin" "$HOME"/.unsloth/studio/unsloth_studio/lib/python3*/site-packages/nvidia/cu13/lib; do
    [ -d "$d" ] && LD_LIBRARY_PATH="$d:${LD_LIBRARY_PATH:-}"
done
export LD_LIBRARY_PATH
"$LLAMA_CPP/build/bin/llama-server" --list-devices 2>&1 | grep -q CUDA \
    || { echo "llama-server sees no CUDA device (would run on CPU); check LD_LIBRARY_PATH"; exit 1; }

"$LLAMA_CPP/build/bin/llama-server" -m "$GGUF" -ngl 99 -np "$NP" -c $((NP * CTX)) --alias local \
    --jinja -fa on --port "$PORT" --host 127.0.0.1 > "logs/llama_server_${TAG}.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
until curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; do
    kill -0 $SERVER 2>/dev/null || { echo "llama-server died"; tail -20 "logs/llama_server_${TAG}.log"; exit 1; }
    sleep 3
done
sleep 2; kill -0 $SERVER 2>/dev/null || { echo "llama-server exited; port $PORT is served by something else"; exit 1; }
echo "llama-server ready"

LIMIT_ARG=(); [ "$LIMIT" != 0 ] && LIMIT_ARG=(--limit "$LIMIT")
$PY script/eval/tool_fim/run_eval.py --base-url "http://127.0.0.1:$PORT/v1" --model local \
    --tag "$TAG" --workers "$NP" "${LIMIT_ARG[@]}"
