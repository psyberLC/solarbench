#!/usr/bin/env bash
# The one gate. Everything merged to main passes this; run it before asking for review.
#   tools/check.sh          lint, unit tests (which validate every result file) and the board; no GPU, about 10 s
#   tools/check.sh --gpu    also runs bolt tightening and the connector with the oracle and the zero policy, about 20 min
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-.venv/bin/python}
[ -x "$PY" ] || PY=python3

echo "== lint";            "$PY" -m ruff check solarbench scripts tests tools
echo "== unit tests";      "$PY" -m pytest -q tests
echo "== board";           "$PY" tools/board.py check; echo "ok"

if [ "${1:-}" = "--gpu" ]; then
    out=$(mktemp -d)
    for task in SolarBench-T3-ClampTighten-UR16e-v0 SolarBench-T2-MC4-G1-v0; do
        echo "== oracle on $task"
        "$PY" scripts/evaluate.py --task "$task" --policy oracle --split dev --episodes 8 --num_envs 8 \
            --viz none --out_dir "$out" | grep -E "^==|  success|safe_success|damage|sim_error"
        echo "== zero policy on $task (must not succeed)"
        "$PY" scripts/evaluate.py --task "$task" --policy zero --split dev --episodes 8 --num_envs 8 \
            --viz none --out_dir "$out" | grep -E "  success" | tee /dev/stderr | grep -q "(0/8)"
    done
fi
echo "all checks passed"
