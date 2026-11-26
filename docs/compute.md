# Running on a batch cluster (optional)

Notes for running evaluation sweeps and model servers on a batch cluster where you have no root, the base operating system is old, and compute nodes may have no internet. The board item `infra-container` turns these notes into tested files under `ops/`; until it is done, treat this page as a plan, not a record.

## Which GPUs
Any NVIDIA GPU of the Turing generation or newer, with driver 580.65 or later ([sources](sources.md), section B). Headless simulation does not need ray-tracing hardware, so data-centre cards without it are fine. The state-based tasks fit in 8 GB. `python tools/board.py next` reads the machine's GPUs and lists the work it can take.

## What to find out first
Ask the cluster's support desk or check on a GPU node before building anything:

| Question | Why it matters |
|---|---|
| NVIDIA driver version on the GPU nodes (`nvidia-smi`) | The pinned simulator stack needs a recent driver; a container cannot bring its own |
| Which GPUs have ray-tracing cores | Data-centre cards such as the A100 have none. The Newton Warp renderer is plain CUDA and should not need them; the path-traced renderer may. Both are untested here on such cards |
| Do compute nodes reach the internet? | If not, wheels, model weights and robot models must be staged beforehand, and remote model endpoints cannot be called from a job |
| Container runtime and version | Singularity or Apptainer, with `--nv` |
| Storage: quotas, scratch paths, purge policy | The environment is about 10 GB; a 27B model is about 54 GB unquantised |

## Shape of a run
1. **Container.** An image with a current base OS, the pinned Python environment (`uv.lock`) and nothing proprietary that may not be redistributed. Old host operating systems cannot install current wheels natively.
2. **Stage.** On a node with internet: build the image, download model weights and the robot descriptions, copy them to shared storage.
3. **Smoke test.** One GPU, one task, eight oracle episodes. Compare the result with the same run on a workstation; they should agree within intervals, not bit for bit.
4. **Model server and simulator on one node.** A language model and the simulator each want a GPU. A 27B model needs two 48 GB cards or a quantised copy.
5. **Sweeps.** One job per cell of the experiment matrix, each writing its own result file, so a failed job costs one cell.

## Schedulers
The templates target Torque/PBS (`qsub`, `-l nodes=1:ppn=8:gpus=1`, `-l feature=<gpu type>`); Slurm equivalents are a small change.

## Reproducibility across machines
GPU physics is not bit-identical across GPU models. The claim this project makes is statistical: the same commit and seeds give results that agree within their intervals on different hardware. Every result file records the GPU, driver-independent package versions and the commit, so a disagreement can be traced.
