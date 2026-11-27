#!/usr/bin/env bash
# Run scripted_brain.py against the R2 bolt task (no viewer) for one press depth and turn step.
#   OUT=/scratch/dir NOTES/probes/scripted_seat.sh PRESS_MM TURN_DEG [EPISODES] [STANDOFF_MM]
set -uo pipefail
cd "$(dirname "$0")/../.."
OUT=${OUT:?set OUT to a scratch folder}; PRESS=$1; TURN=$2; EPISODES=${3:-4}; STANDOFF=${4:-2.0}
DIR="$OUT/press${PRESS}-turn${TURN}-standoff${STANDOFF}"; mkdir -p "$DIR"
.venv/bin/python NOTES/probes/scripted_brain.py --press "$PRESS" --turn "$TURN" --standoff "$STANDOFF" > "$DIR/brain.log" 2>&1 &
BRAIN=$!
sleep 2
SOLARBENCH_ENDPOINT_URL=http://127.0.0.1:8084/v1 .venv/bin/python scripts/evaluate.py \
    --task SolarBench-T3-ClampTighten-UR16e-R2-v0 --split dev --episodes "$EPISODES" --num_envs 1 --viz none \
    --policy "endpoint:scripted,wrench=on,reasoning=off,commands=assist,privileged=on,rounds=40" \
    --out_dir "$DIR" env.episode_length_s=60 2>&1 | cat > "$DIR/run.log"
kill "$BRAIN"
grep -E "^== episode" "$DIR/brain.log"
