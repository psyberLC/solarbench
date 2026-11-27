#!/usr/bin/env bash
# First login on RTU's RUDENS cluster: print what NOTES/HPC_PLAN.md needs to serve a model there (the laptop keeps
# the simulation). Read-only: it changes nothing. Copy it across and run it on the login node
# (ssh <user>@ui-2.hpc.rtu.lv), then again inside an interactive job on a GPU node.
#   bash discover.sh 2>&1 | tee discover-$(hostname).txt
set -u
echo "== host"; hostname; uname -r; ldd --version 2>&1 | head -1
echo "== scheduler"
for c in sbatch sinfo squeue qsub qstat pbsnodes; do command -v "$c" > /dev/null && echo "$c: $(command -v "$c")"; done
command -v sinfo > /dev/null && sinfo -o "%P %a %l %D %c %m %G %f" | head -40
command -v qstat > /dev/null && qstat -Q 2> /dev/null | head -40
command -v pbsnodes > /dev/null && pbsnodes -a 2> /dev/null \
    | grep -E "^[[:alnum:]]|ngpus|ncpus|mem =|properties|feature|gpu_model" | head -80
echo "== GPUs on this node"
if command -v nvidia-smi > /dev/null; then
    nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv
    nvidia-smi | grep -i "cuda version"
else
    echo "no nvidia-smi here"
fi
echo "== modules"
type module > /dev/null 2>&1 || for f in /etc/profile.d/modules.sh /usr/share/lmod/lmod/init/bash; do [ -f "$f" ] && . "$f"; done
type module > /dev/null 2>&1 && module avail 2>&1 | grep -iE "cuda|python|conda|miniforge|apptainer|singularity|gcc|vllm" | head -40
echo "== containers"
for c in apptainer singularity docker podman; do command -v "$c" > /dev/null && echo "$c: $("$c" --version 2>&1 | head -1)"; done
echo "== storage"
df -h "$HOME" | tail -1
for d in /scratch /home_beegfs /mnt/beegfs /beegfs /project /projects /tmp; do [ -d "$d" ] && echo "$d: $(df -h "$d" | tail -1)"; done
command -v quota > /dev/null && quota -s 2> /dev/null | head
echo "== internet from this node"
for u in https://huggingface.co https://pypi.org https://github.com https://registry-1.docker.io https://nvcr.io; do
    printf "%s: " "$u"; curl -sI --max-time 8 -o /dev/null -w "%{http_code}\n" "$u" || echo unreachable
done
env | grep -i "_proxy" || echo "no proxy variables set"
echo "== network: can this node reach the login node's SSH port, and is anything already on port 8000"
(timeout 3 bash -c "echo > /dev/tcp/ui-2.hpc.rtu.lv/22" 2> /dev/null && echo "ui-2.hpc.rtu.lv:22 reachable") \
    || echo "ui-2.hpc.rtu.lv:22 not reachable from here"
command -v ss > /dev/null && (ss -ltn | grep -q ":8000 " && echo "port 8000 in use" || echo "port 8000 free")
