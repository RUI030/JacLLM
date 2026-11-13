#!/usr/bin/env bash
# One coding agent (opencode | pi) on a scenario stage in a fresh empty Jac full-stack project, model `local`
# from serve.sh's proxy (provider `jacllm-llama` in opencode.json / pi models.json, see README.md).
#   bash script/eval/agent/run_agent.sh <opencode|pi> <model> [scenario] [stage]
# Run it under a memory cap so whatever the agent starts dies with it:
#   systemd-run --user --unit agent-<agent> -p MemoryMax=8G -p MemorySwapMax=0 bash script/eval/agent/run_agent.sh ...
# The agent runs in its own PID namespace (bwrap): it has run `pkill -f jac` and `ps aux | grep -i jac | xargs kill`,
# which killed itself, the runner, llama-server and the shared jac postgres. Inside it sees only its own processes,
# and all of them die with it. shims/ still refuses pkill/killall/pgrep with a hint.
set -uo pipefail
AGENT="$1"; MODEL="$2"; SCENARIO="${3:-todo_stage1}"; STAGE="${4:-stage_1.md}"
A="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$A/../../.." && pwd)"
JACBUILDER="${JACBUILDER:-$ROOT/../jacBuilder}"
CALLS="$ROOT/output/serve/$MODEL/calls.jsonl"
RUN="$ROOT/output/eval/agent/$SCENARIO/$AGENT-${MODEL}_$(date +%m-%d_%H-%M)"; mkdir -p "$RUN"
export PATH="$A/shims:$HOME/.jacbin_pinned:$HOME/miniforge3/envs/jaccoder/bin:$PATH"
export AGENT_BROWSER_ARGS=--no-sandbox          # Ubuntu AppArmor blocks Chrome's user-namespace sandbox
SANDBOX=(bwrap --unshare-pid --die-with-parent --dev-bind / / --proc /proc)

# The project lives in a temp dir: it holds node_modules (~300MB); only the diff is kept.
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
cd "$WORK" && jac create app --use "$JACBUILDER/assets/templates/empty.jacpack" --force --skip > "$RUN/setup.log" 2>&1
cd "$WORK/app" && jac install >> "$RUN/setup.log" 2>&1
git init -q . && git add -A && git commit -qm scaffold     # the agent's changes become a plain `git diff`
PROMPT="$(cat "$A/scenarios/$SCENARIO/$STAGE")

Environment: this directory is a Jac full-stack project (jac $(jac --version | awk '{print $2}') is on PATH). Start the dev server in the background with \`jac start main.jac\` (it serves http://localhost:8000). For browser checks use the \`agent-browser\` CLI (\`agent-browser open <url>\`, \`agent-browser snapshot\`, \`agent-browser fill <ref> <text>\`, \`agent-browser click <ref>\`, \`agent-browser screenshot <file>\`, \`agent-browser close\`). Stop the dev server when you are done."
printf '%s\n' "$PROMPT" > "$RUN/prompt.txt"
START_LINE=$(wc -l < "$CALLS")
date +%s > "$RUN/start_epoch"
case "$AGENT" in
  # --standalone: a private server that dies with this process. Without it `opencode run` attaches to (or starts)
  # the background `opencode serve --service`, where the session keeps running after timeout, outside the shims.
  opencode) timeout 1800 "${SANDBOX[@]}" "$HOME/.opencode/bin/opencode" run --standalone --auto -m jacllm-llama/local --format json "$PROMPT" > "$RUN/agent.jsonl" 2> "$RUN/agent.err" ;;
  pi)       timeout 1800 "${SANDBOX[@]}" "$HOME/.local/bin/pi" -p --mode json --model jacllm-llama/local "$PROMPT" > "$RUN/agent.jsonl" 2> "$RUN/agent.err" ;;
  *)        echo "unknown agent $AGENT"; exit 1 ;;
esac
echo "exit $?" > "$RUN/exit_code"
date +%s > "$RUN/end_epoch"
agent-browser close >/dev/null 2>&1
git add -A >/dev/null 2>&1
git diff --cached --stat HEAD > "$RUN/diff_stat.txt"
git diff --cached HEAD -- . ':!bun.lock' ':!package-lock.json' > "$RUN/diff.patch"
tail -n +$((START_LINE + 1)) "$CALLS" > "$RUN/calls.jsonl"     # every call in the window; view.html keeps this agent's
python3 "$ROOT/script/dataset/trajectory/view.py" "$RUN/calls.jsonl" --client "$AGENT" --out "$RUN/view.html"
echo "$RUN"
