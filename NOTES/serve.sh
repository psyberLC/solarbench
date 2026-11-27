#!/usr/bin/env bash
# Start the model server for the laptop runs: Nemotron 3 Nano 30B-A3B (Q4_K_M) on llama.cpp b12780 (CUDA 12.8).
# Listens on 127.0.0.1:8080 only. Why each flag is set is in NOTES/serve.md.
#   NOTES/serve.sh            run in the foreground
#   NOTES/serve.sh --daemon   run in the background, log to ~/llm/server.log, wait until it answers
#   BUDGET=8192 PARALLEL=1 NOTES/serve.sh --daemon   a longer thinking cap and one conversation (viewer runs);
#                                                    the defaults are the settings of the laptop experiment
set -euo pipefail
MODEL="$HOME/llm/models/NVIDIA-Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"
ARGS=(-m "$MODEL" --host 127.0.0.1 --port 8080 --jinja
      --parallel "${PARALLEL:-4}" --ctx-size 81920
      -ngl 99 --n-cpu-moe 50
      --top-p 1.0 --top-k 0 --min-p 0
      --reasoning-budget "${BUDGET:-2048}")
if [ "${1:-}" = "--daemon" ]; then
    nohup "$HOME/llm/llama-server" "${ARGS[@]}" > "$HOME/llm/server.log" 2>&1 &
    for _ in $(seq 1 100); do
        curl -sf http://127.0.0.1:8080/health > /dev/null 2>&1 && { echo "server up (pid $!)"; exit 0; }
        sleep 3
    done
    echo "server did not come up; see ~/llm/server.log" >&2
    exit 1
fi
exec "$HOME/llm/llama-server" "${ARGS[@]}"
