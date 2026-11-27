#!/usr/bin/env bash
# The skills comparison: oracle, a fixed script and Nemotron 3.5 Lightning on the same dev episodes of both tasks.
# Each task's own episode limit and work order, one environment, dev episodes 0..EPISODES-1. Model exchanges are
# recorded by NOTES/probes/watch_proxy.py next to each result. Needs the Lightning server on :8080
# (MODEL=…Lightning….gguf TOP_P=0.95 BUDGET=4096 PARALLEL=1 CTX=131072 NOTES/serve.sh --daemon).
#   NOTES/report_runs.sh            from the repository root; resumable (a run with a result file is skipped)
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=NOTES/report-runs
EPISODES=${EPISODES:-8}
LIGHTNING=NVIDIA-Nemotron-3.5-Lightning-30B-A3B-Q4_0
T3=SolarBench-T3-ClampTighten-UR16e-R2-v0
T2=SolarBench-T2-MC4-G1-v0

run() {  # name task policy [caller-port caller-args | proxy]
    local name=$1 task=$2 policy=$3 how=${4:-} dir=$OUT/$1 helper=""
    find "$dir" -name "*.json" -path "*SolarBench*" 2> /dev/null | grep -q . && { echo "$name: done before"; return; }
    mkdir -p "$dir"
    case $how in
        proxy) .venv/bin/python NOTES/probes/watch_proxy.py --log "$dir/exchanges.jsonl" > "$dir/proxy.log" 2>&1 &
               helper=$!; url=http://127.0.0.1:8081/v1 ;;
        script:*) .venv/bin/python NOTES/probes/scripted_skills.py ${how#script:} > "$dir/caller.log" 2>&1 &
                  helper=$!; url=http://127.0.0.1:8085/v1 ;;
        *) url= ;;
    esac
    sleep 3
    echo "$(date -Is) $name: start"
    SOLARBENCH_ENDPOINT_URL=$url SOLARBENCH_ENDPOINT_LOG="$dir/calls.jsonl" .venv/bin/python scripts/evaluate.py \
        --task "$task" --policy "$policy" --split dev --episodes "$EPISODES" --num_envs 1 --viz none \
        --out_dir "$dir" 2>&1 | cat > "$dir/run.log"
    [ -n "$helper" ] && kill "$helper"
    grep -aE "^==|success|damage|sim_error" "$dir/run.log"
}

run t3-oracle "$T3" oracle
run t3-script-unprivileged "$T3" "endpoint:scripted,wrench=on,reasoning=off,tools=on,skills=on,rounds=20" "script:"
run t3-lightning-unprivileged "$T3" \
    "endpoint:$LIGHTNING,wrench=on,reasoning=on,temperature=0.6,max_tokens=12288,rounds=30,tools=on,skills=on" proxy
run t2-oracle "$T2" oracle
run t2-script-privileged "$T2" "phases:scripted,notes=NOTES/probes/job_mc4.md,reasoning=off" \
    "script:--plan grasp,unplug,plug_in,release,done"
run t2-lightning-privileged "$T2" "phases:$LIGHTNING,notes=NOTES/probes/job_mc4.md" proxy
echo "$(date -Is) all runs attempted"
