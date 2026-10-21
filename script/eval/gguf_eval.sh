#!/usr/bin/env bash
# Serve a GGUF with llama-server and run infer (openrouter.py --base-url) + gate over the batch.py EVAL_SET.
#   bash script/eval/gguf_eval.sh <gguf> <tag> <limit> [parallel]   (limit 0 = all)
set -uo pipefail
GGUF="$1"; TAG="$2"; LIMIT="$3"; NP="${4:-16}"
ROOT=/workspace/JacLLM
PY=/root/miniforge3/envs/jacllm/bin/python
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

"$LLAMA_CPP/build/bin/llama-server" -m "$GGUF" -ngl 99 -np "$NP" -c $((NP * 8192)) \
    --jinja -fa on --port 8080 --host 127.0.0.1 > "logs/llama_server_${TAG}.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
until curl -sf http://127.0.0.1:8080/health >/dev/null; do
    kill -0 $SERVER 2>/dev/null || { echo "llama-server died"; tail -20 "logs/llama_server_${TAG}.log"; exit 1; }
    sleep 3
done
# A healthy port isn't proof it's ours: another listener (e.g. a proxy) can answer.
sleep 2; kill -0 $SERVER 2>/dev/null || { echo "llama-server exited; port 8080 is served by something else"; tail -5 "logs/llama_server_${TAG}.log"; exit 1; }
echo "llama-server ready"

for td in code_completion:Nitin-9k-py2jac-idiom code_gen:opus-synth-v2 py2jac:opus-synth-v2 \
          js2jac:Nitin-3k-js2jac-idiom osp:Nitin-1k-osp; do
    task=${td%%:*}; ds=${td#*:}
    echo "=== $task / $ds"
    $PY script/eval/infer/openrouter.py --base-url http://127.0.0.1:8080/v1 --model local \
        --out-tag "$TAG" --task "$task" --ds "$ds" --limit "$LIMIT" --workers "$NP" \
        --max-tokens 2048 --temperature 0 --repeat-penalty 1.05 --timeout 1800 | grep -vE "^\s*$"
    pred=$(ls -td output/eval/$task/$ds/${TAG}_*/ | head -1)predictions.jsonl
    $PY script/eval/gate.py --pred "$pred" | grep -E "^n=|check="
done
