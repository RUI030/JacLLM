# Tool-use FIM spike: SFT v1.3-A on pi trajectories → merge bf16 → GGUF Q8_0 → pi eval on held-out files,
# v1.3-A GGUF (baseline) vs the new one. Data: python script/dataset/sft/tool_fim.py (run before this). Log to logs/:
#   setsid nohup bash script/train/recipe/1015-toolfim-v13A/run.sh \
#     > logs/1015-toolfim-v13A.log 2>&1 < /dev/null &
# An interrupted run resumes with `train.py --resume output/adapter/1015-toolfim-v13A/sft/checkpoint-N`.
set -euo pipefail
cd "$(dirname "$0")/../../../.."
PY=/home/imrui/miniforge3/envs/tornith/bin/python
R=script/train/recipe/1015-toolfim-v13A
OUT=output/adapter/1015-toolfim-v13A/sft
NAME=JacLLM-SFT-Ornith-9B-toolfim-spike
BASE_GGUF=output/model/JacLLM-SFT-Ornith-9B-v1.3A_GGUF/JacLLM-SFT-Ornith-9B-v1.3A-Q8_0.gguf
LLAMA_CPP="$HOME/.unsloth/llama.cpp"
LIMIT=${LIMIT:-0}
stamp() { echo "===== $(date '+%m-%d %H:%M:%S') $*"; }

stamp "sft";        $PY script/train/train.py --recipe $R/sft.yaml
stamp "merge bf16"; $PY script/merge_lora.py --adapter $OUT/adapter --no-4bit --out output/model/$NAME-bf16
stamp "gguf q8_0";  mkdir -p output/model/${NAME}_GGUF
PYTHONPATH="$LLAMA_CPP/gguf-py" $PY "$LLAMA_CPP/convert_hf_to_gguf.py" output/model/$NAME-bf16 \
    --outtype q8_0 --outfile output/model/${NAME}_GGUF/$NAME-Q8_0.gguf
stamp "eval toolfim";  bash script/eval/tool_fim/serve_eval.sh output/model/${NAME}_GGUF/$NAME-Q8_0.gguf toolfim-spike "$LIMIT"
stamp "eval v13A";     bash script/eval/tool_fim/serve_eval.sh $BASE_GGUF v13A "$LIMIT"
stamp "ALL_DONE"
