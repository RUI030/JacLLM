# v1.35: cpt -> sft (v1.3-A recipe on the rewritten SFT sets). Stop Unsloth Studio's llama-server first (~12GB of the 5080).
# Log to logs/:
#   setsid nohup bash script/train/recipe/1023-v135/run.sh > logs/1023-v135.log 2>&1 < /dev/null &
# An interrupted stage resumes with `train.py --resume <run>/checkpoint-N`.
set -euo pipefail
cd "$(dirname "$0")/../../../.."
PY=/home/imrui/miniforge3/envs/tornith/bin/python
R=script/train/recipe/1023-v135
stamp() { echo "===== $(date '+%m-%d %H:%M:%S') $*"; }

stamp "cpt"; $PY script/train/train.py --recipe $R/cpt.yaml
stamp "sft"; $PY script/train/train.py --recipe $R/sft.yaml
stamp "ALL_DONE"
