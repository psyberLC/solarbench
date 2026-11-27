#!/usr/bin/env bash
# Watch Nemotron work the R2 bolt task in the Newton viewer, for looking, not for results.
# Differs from the experiment (NOTES/run_all.sh) on purpose: no time limit (the sim stops an episode only after a day
# of sim time, and on the live-viewer branch the work order no longer states a limit), no round cap, and episodes
# repeat until Ctrl-C. Its result file goes to the scratch folder given as OUT, never to NOTES/runs or results/.
# Needs the server (BUDGET=8192 PARALLEL=1 NOTES/serve.sh --daemon) and the proxy (NOTES/probes/watch_proxy.py).
#   OUT=/some/scratch/dir NOTES/live.sh [thinking=on|off]
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${OUT:?set OUT to a scratch folder}
THINKING=${1:-thinking=on}; THINKING=${THINKING#thinking=}
if [ "$THINKING" = on ]; then SAMPLING="reasoning=on,temperature=1.0,max_tokens=12288"
else SAMPLING="reasoning=off,temperature=0,max_tokens=1024"; fi
mkdir -p "$OUT"
SOLARBENCH_ENDPOINT_URL=http://127.0.0.1:8081/v1 SOLARBENCH_ENDPOINT_LOG="$OUT/calls-live.jsonl" \
    exec .venv/bin/python scripts/evaluate.py --task SolarBench-T3-ClampTighten-UR16e-R2-v0 \
    --policy "endpoint:NVIDIA-Nemotron-3-Nano-30B-A3B-Q4_K_M,wrench=on,$SAMPLING,rounds=1000000" \
    --split dev --episodes 1000 --num_envs 1 --viz newton_gl --out_dir "$OUT" env.episode_length_s=86400
