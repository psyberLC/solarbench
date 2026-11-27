#!/usr/bin/env bash
# The laptop experiment (action plan, step 5): five runs on the R2 bolt task, dev split, one after another.
# Resumable: a run whose marker NOTES/runs/<name>.done exists is skipped. A run that fails is retried once after
# checking the model server, which is restarted with NOTES/serve.sh if it does not answer.
#   NOTES/run_all.sh                          from the repository root
#   setsid nohup NOTES/run_all.sh > NOTES/runs/run_all.out 2>&1 &     unattended
set -uo pipefail
cd "$(dirname "$0")/.."
TASK=SolarBench-T3-ClampTighten-UR16e-R2-v0
MODEL=NVIDIA-Nemotron-3-Nano-30B-A3B-Q4_K_M
OUT=NOTES/runs
ENVS=${ENVS:-4}
EPISODES=${EPISODES:-16}
export SOLARBENCH_ENDPOINT_URL=http://127.0.0.1:8080/v1
mkdir -p "$OUT"

server_up() { curl -sf --max-time 10 http://127.0.0.1:8080/health > /dev/null; }
ensure_server() {
    server_up && return 0
    echo "$(date -Is) server not answering; restarting"
    pid=$(pgrep -x llama-server) && kill "$pid" && sleep 5
    NOTES/serve.sh --daemon
}

run() {  # name episodes policy
    local name=$1 episodes=$2 policy=$3
    [ -e "$OUT/$name.done" ] && { echo "$(date -Is) $name: done before, skipped"; return 0; }
    for attempt in 1 2; do
        case $policy in endpoint:*) ensure_server ;; esac
        [ -e "$OUT/$name.calls.jsonl" ] && mv "$OUT/$name.calls.jsonl" "$OUT/$name.calls.failed-$(date +%s).jsonl"
        echo "$(date -Is) $name: start (attempt $attempt): $policy, $episodes episodes, $ENVS envs"
        SOLARBENCH_ENDPOINT_LOG="$OUT/$name.calls.jsonl" NOTES/monitor.sh "$OUT/$name.mon" \
            .venv/bin/python scripts/evaluate.py --task "$TASK" --policy "$policy" --split dev \
            --episodes "$episodes" --num_envs "$ENVS" --viz none --out_dir "$OUT" 2>&1 | cat > "$OUT/$name.log"
        if [ "${PIPESTATUS[0]}" -eq 0 ] && grep -q "  wrote " "$OUT/$name.log"; then
            grep -E "^==|stage_|success|damage|sim_error|wrote|^wall" "$OUT/$name.log"
            touch "$OUT/$name.done"
            return 0
        fi
        echo "$(date -Is) $name: failed (attempt $attempt); last lines:"; tail -5 "$OUT/$name.log"
    done
    return 1
}

M="endpoint:$MODEL"
run floor   "$EPISODES" zero
run ceiling "$EPISODES" oracle
run model-force-off "$EPISODES" "$M,wrench=off,reasoning=on,temperature=1.0,rounds=20"
run model-force-on  "$EPISODES" "$M,wrench=on,reasoning=on,temperature=1.0,rounds=20"
run speed-probe 8 "$M,wrench=on,reasoning=off,temperature=0,rounds=20"
echo "$(date -Is) all runs attempted"
