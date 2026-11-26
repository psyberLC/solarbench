#!/usr/bin/env bash
# Run a command while sampling GPU memory used (MiB) and host RAM used (MiB) every 2 s.
# Usage: NOTES/monitor.sh <samples-file> <command...>
out=$1; shift
( while true; do
    echo "$(date +%s) $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) $(free -m | awk '/Mem:/{print $3}')"
    sleep 2
  done ) > "$out" &
mon=$!
start=$(date +%s)
"$@"; rc=$?
kill $mon
awk -v s="$start" -v e="$(date +%s)" 'NR==1{b=$2;br=$3} {if($2>m)m=$2; if($3>r)r=$3} END{printf "wall %ds  gpu MiB: start %d peak %d  RAM used MiB: start %d peak %d\n", e-s, b, m, br, r}' "$out"
exit $rc
