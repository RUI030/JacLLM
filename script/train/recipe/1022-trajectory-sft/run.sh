# Trajectory SFT: Codex trajectories on the merged v1.3-A CPT → merge bf16 → GGUF Q8_0 (for `unsloth start codex` / llama-server).
# Data first: python script/dataset/sft/tool_use.py --in-file dataset/raw/trajectory/codex.jsonl --out-dir dataset/sft/tool_use/codex \
#   --max-token 16384 --window --require-write      (stop Unsloth Studio's llama-server first: it holds ~12GB of the 5080)
# Log to logs/:
#   setsid nohup bash script/train/recipe/1022-trajectory-sft/run.sh \
#     > logs/1022-trajectory-sft.log 2>&1 < /dev/null &
# An interrupted run resumes with `train.py --resume output/adapter/1022-trajectory-sft/sft/checkpoint-N`.
set -euo pipefail
cd "$(dirname "$0")/../../../.."
PY=/home/imrui/miniforge3/envs/tornith/bin/python
R=script/train/recipe/1022-trajectory-sft
OUT=output/adapter/1022-trajectory-sft/sft
NAME=JacLLM-SFT-Ornith-9B-trajectory
LLAMA_CPP="$HOME/.unsloth/llama.cpp"
stamp() { echo "===== $(date '+%m-%d %H:%M:%S') $*"; }

stamp "sft";        $PY script/train/train.py --recipe $R/sft.yaml
stamp "merge bf16"; $PY script/merge_lora.py --adapter $OUT/adapter --no-4bit --out output/model/$NAME-bf16
stamp "gguf q8_0";  mkdir -p output/model/${NAME}_GGUF
PYTHONPATH="$LLAMA_CPP/gguf-py" $PY "$LLAMA_CPP/convert_hf_to_gguf.py" output/model/$NAME-bf16 \
    --outtype q8_0 --outfile output/model/${NAME}_GGUF/$NAME-Q8_0.gguf
stamp "ALL_DONE"
