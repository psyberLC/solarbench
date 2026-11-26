#!/usr/bin/env bash
# Hardware probe: runs Isaac Lab 3.0 (kit-less, Newton) training jobs and
# samples whole-GPU memory with nvidia-smi. Reproduces the memory figures in docs/sources.md, section A.
#
# Usage: ISAACLAB_DIR=/path/to/IsaacLab(v3.0.0) ./scripts/phase0_vram_probe.sh
# Setup:  git clone --depth 1 --branch v3.0.0 https://github.com/isaac-sim/IsaacLab.git
#         cd IsaacLab && UV_HTTP_TIMEOUT=600 uv sync
set -euo pipefail
: "${ISAACLAB_DIR:?set ISAACLAB_DIR to an Isaac Lab v3.0.0 checkout}"
OUT="${OUT:-$(pwd)/phase0_probe_out}"
mkdir -p "$OUT"
cd "$ISAACLAB_DIR"

echo "idle GPU memory: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"

run() {
  local tag=$1; shift
  ( while true; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits; sleep 0.5; done ) > "$OUT/vram_$tag.txt" &
  local sampler=$!
  local start; start=$(date +%s)
  set +e
  timeout 900 uv run isaaclab train --rl_library rsl_rl "$@" > "$OUT/log_$tag.txt" 2>&1
  local rc=$?
  set -e
  kill "$sampler"; wait "$sampler" 2>/dev/null || true
  echo "$tag rc=$rc wall=$(( $(date +%s) - start ))s peak_gpu_mem=$(sort -n "$OUT/vram_$tag.txt" | tail -1)MiB" \
       "$(grep -E 'Steps per second' "$OUT/log_$tag.txt" | tail -1 | xargs)"
}

run g1flat_512   --task Isaac-Velocity-Flat-G1  --num_envs 512  --max_iterations 30 --viz none physics=newton_mjwarp
run g1flat_4096  --task Isaac-Velocity-Flat-G1  --num_envs 4096 --max_iterations 10 --viz none physics=newton_mjwarp
run g1rough_1024 --task Isaac-Velocity-Rough-G1 --num_envs 1024 --max_iterations 10 --viz none physics=newton_mjwarp
run factory_64   --task IsaacContrib-Factory-Franka --num_envs 64 --max_iterations 5 --viz none physics=newton_mjwarp
