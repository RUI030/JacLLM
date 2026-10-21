#!/usr/bin/env bash
# Serve a GGUF on its own port, then run the Nitin harness as the non-root jacgrader user.
#   bash script/eval/Nitin-test/run_gguf.sh <gguf> <tag> <dev|test> [limit] [port]
# Needs a non-root `jacgrader` user (useradd -m jacgrader) and jac at /workspace/bin/jac.
set -uo pipefail
GGUF="$1"; TAG="$2"; SPLIT="$3"; LIMIT="${4:-0}"; PORT="${5:-8091}"   # not 8081: RunPod nginx listens there and proxies to 8080; NP=16
ROOT=/workspace/JacLLM
LLAMA_CPP="${LLAMA_CPP:-/workspace/unsloth-studio/llama.cpp}"   # Unsloth Studio's prebuilt llama.cpp
cd "$ROOT"

# Studio's CUDA backend links CUDA 13 runtime libs that live in its venv; without
# them llama.cpp silently falls back to CPU (~600x slower prompt processing).
for d in "$LLAMA_CPP/build/bin" /workspace/unsloth-studio/unsloth_studio/lib/python3*/site-packages/nvidia/cu13/lib; do
    [ -d "$d" ] && LD_LIBRARY_PATH="$d:${LD_LIBRARY_PATH:-}"
done
export LD_LIBRARY_PATH
"$LLAMA_CPP/build/bin/llama-server" --list-devices 2>&1 | grep -q CUDA \
    || { echo "llama-server sees no CUDA device (would run on CPU); check LD_LIBRARY_PATH"; exit 1; }

"$LLAMA_CPP/build/bin/llama-server" -m "$GGUF" -ngl 99 -np $NP -c $((NP * 8192)) \
    --jinja -fa on --port "$PORT" --host 127.0.0.1 > "logs/llama_server_${TAG}.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
until curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null; do
    kill -0 $SERVER 2>/dev/null || { echo "llama-server died"; tail -20 "logs/llama_server_${TAG}.log"; exit 1; }
    sleep 3
done
# A healthy port isn't proof it's ours: another listener (e.g. a proxy) can answer.
sleep 2; kill -0 $SERVER 2>/dev/null || { echo "llama-server exited; port $PORT is served by something else"; tail -5 "logs/llama_server_${TAG}.log"; exit 1; }
echo "llama-server ready on :$PORT"

# jacgrader: non-root (embedded postgres refuses root), clean env (no HF_TOKEN),
# 4 xdist workers per `jac test` (auto = 128 on this box, ~30GB per test).
su - jacgrader -c "cd $ROOT && export PATH=/workspace/bin:\$PATH PYTEST_XDIST_AUTO_NUM_WORKERS=4 && \
    /usr/local/bin/python script/eval/Nitin-test/run_eval.py --base-url http://127.0.0.1:${PORT}/v1 \
    --tag $TAG --split $SPLIT --limit $LIMIT --gen-workers $NP --timeout 120"
