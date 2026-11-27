#!/usr/bin/env bash
# Watch Nemotron work the R2 bolt task in the Newton viewer, for looking, not for results.
# Differs from the experiment (NOTES/run_all.sh) on purpose: no time limit (the sim stops an episode only after a day
# of sim time, and on the live-viewer branch the work order no longer states a limit), no round cap, and episodes
# repeat until Ctrl-C. Its result file goes to the scratch folder given as OUT, never to NOTES/runs or results/.
# Needs the server (BUDGET=8192 PARALLEL=1 NOTES/serve.sh --daemon) and the proxy (NOTES/probes/watch_proxy.py).
#   OUT=/some/scratch/dir NOTES/live.sh [thinking=on|off]
# Optional: URL (default the proxy, http://127.0.0.1:8081/v1), MODEL (the name the result carries), EPISODES
# (default 1000), ROUNDS (default no cap), COMMANDS (pose, the default, or assist: aim/push/turn helpers),
# PRIVILEGED (off, or on: the oracle's readings), LIMIT_S (episode limit in sim seconds, default 86400),
# LESSONS (a text file appended to the system message, e.g. NOTES/probes/lessons_bolt.md), KEEP (on: earlier thinking
# is sent back each round; serve with CTX=131072 and a small BUDGET), TEMP (sampling temperature with thinking, default 1.0),
# TOOLS (on: native tool calls instead of a line of JSON), HOST (remote: the model runs elsewhere, e.g. through a
# tunnel to the cluster).
# An agent answers through NOTES/probes/agent_bridge.py on port 8082.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${OUT:?set OUT to a scratch folder}
THINKING=${1:-thinking=on}; THINKING=${THINKING#thinking=}
if [ "$THINKING" = on ]; then SAMPLING="reasoning=on,temperature=${TEMP:-1.0},max_tokens=12288"
else SAMPLING="reasoning=off,temperature=0,max_tokens=1024"; fi
mkdir -p "$OUT"
SOLARBENCH_ENDPOINT_URL=${URL:-http://127.0.0.1:8081/v1} SOLARBENCH_ENDPOINT_LOG="$OUT/calls-${MODEL:-nemotron}-${COMMANDS:-pose}.jsonl" \
    exec .venv/bin/python scripts/evaluate.py --task SolarBench-T3-ClampTighten-UR16e-R2-v0 \
    --policy "endpoint:${MODEL:-NVIDIA-Nemotron-3-Nano-30B-A3B-Q4_K_M},wrench=on,$SAMPLING,rounds=${ROUNDS:-1000000},commands=${COMMANDS:-pose},privileged=${PRIVILEGED:-off}${LESSONS:+,notes=$LESSONS}${KEEP:+,keep_thinking=$KEEP}${TOOLS:+,tools=$TOOLS}${HOST:+,host=$HOST}" \
    --split dev --episodes "${EPISODES:-1000}" --num_envs 1 --viz newton_gl --out_dir "$OUT" env.episode_length_s="${LIMIT_S:-86400}"
