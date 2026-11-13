#!/usr/bin/env bash
# jac_coder (jacBuilder's verification_runner, IDE mode) on a scenario against serve.sh's proxy.
#   bash script/eval/agent/run_jaccoder.sh <model> [scenario]
# Needs jacBuilder's jac.toml [byllm.compaction] ctx_window set to the served context (see README.md).
set -uo pipefail
MODEL="$1"; SCENARIO="${2:-todo_stage1}"; TEMPLATE="${TEMPLATE:-empty}"   # TEMPLATE: a jacBuilder assets/templates/<name>.jacpack to start from
A="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$A/../../.." && pwd)"
SCENARIO_DIR="${SCENARIO_DIR:-$A/scenarios/$SCENARIO}"   # the request can come from another dir (continue_run.py); output stays under $SCENARIO
JACBUILDER="${JACBUILDER:-$ROOT/../jacBuilder}"
CALLS="$ROOT/output/serve/$MODEL/calls.jsonl"
OUT="$ROOT/output/eval/agent/$SCENARIO"; RUN_ID="jaccoder-${MODEL}_$(date +%m-%d_%H-%M)"; mkdir -p "$OUT"
export PATH="$HOME/.jacbin_pinned:$HOME/miniforge3/envs/jaccoder/bin:$PATH"
export AGENT_BROWSER_ARGS=--no-sandbox          # Ubuntu AppArmor blocks Chrome's user-namespace sandbox
export OPENAI_API_KEY="$(cat "${KEY_FILE:-$HOME/.config/jacllm/llama_api_key}")"
export OPENAI_BASE_URL=http://127.0.0.1:8080/v1 OPENAI_API_BASE=http://127.0.0.1:8080/v1   # jac 0.34.28 ignores [byllm.model] base_url; litellm reads these
export JACCODER_TRACK_COST=1 JACCODER_WEB_MODE=1 JACCODER_AUTONOMOUS_MODE=1 JACCODER_STRUGGLE_LOG=1
START_LINE=$(wc -l < "$CALLS")
cd "$JACBUILDER"
jac --version
# own PID namespace, as in run_agent.sh: the model's shell commands cannot see or kill anything outside it
bwrap --unshare-pid --die-with-parent --dev-bind / / --proc /proc jac run evaluation/verification_runner/runner.jac -- \
    --scenario "$SCENARIO_DIR" --output-dir "$OUT" --run-id "$RUN_ID" \
    --model openai/local --template "$TEMPLATE" --trigger manual 2>&1 | tee "$OUT/$RUN_ID.log"
mv "$OUT/$RUN_ID.log" "$OUT/$RUN_ID/run.log"
tail -n +$((START_LINE + 1)) "$CALLS" > "$OUT/$RUN_ID/calls.jsonl"
python3 "$ROOT/script/dataset/trajectory/view.py" "$OUT/$RUN_ID/calls.jsonl" --client jaccoder --out "$OUT/$RUN_ID/view.html"
echo "$OUT/$RUN_ID"
