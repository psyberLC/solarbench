# Plan: Nemotron 3.5 Super on RTU's RUDENS cluster

Written 2026-11-27 by claude-code (for psyberLC), before anyone has logged in. Everything marked **unverified** has to be checked on the cluster first; `NOTES/hpc/discover.sh` prints most of it.

## What is known
**The cluster** (from https://hpc-platforma.rtu.lv; the detailed user guide, https://hpc-guide.rtu.lv, could not be read from here: the fetch was refused by this session's permission check, so it still needs reading by you):
- RUDENS, RTU HPC. Login `ssh <user>@ui-2.hpc.rtu.lv`, SSH keys only, uploaded in the Waldur portal (https://nohap.hpc-net.lv, Credentials → SSH keys; wait 5 minutes). Web terminal: Open OnDemand, https://ood.hpc.rtu.lv/.
- Use is charged to a Waldur project allocation in euros covering CPU hours, GPU hours and memory.
- A MATLAB example requests GPUs with the feature `l40s`, so there are NVIDIA L40S GPUs (48 GB, Ada). **Unverified**: GPUs per node, other GPU models, driver version, scheduler (Slurm or PBS), queues, walltime, containers, internet on compute nodes, storage paths and quotas.

**The model** (Hugging Face cards, released 2026-10-15, licence OpenMDW-1.1): the official "Nemotron 3.5 Super" is `nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B`, a vision-language Mamba–transformer mixture of experts, 120B parameters with 12B active, up to 1M tokens of context, with multi-token prediction. It answers text-only prompts like ours.
| Variant | Size | Cards' hardware |
|---|---|---|
| `…-BF16` | 249 GB | 4× H100 or 2× GB200 |
| `…-NVFP4` | 75.1 GB | 1× H200, 2× H100, 1× RTX PRO 6000, 1× GB200, DGX Spark |
| `RedHatAI/…-FP8` (third party) | not checked (about 125 GB expected for 124B parameters at one byte) | not stated |
Serving per the cards: vLLM `vllm/vllm-openai:v0.32.0`, `--reasoning-parser nemotron_v3 --tool-call-parser qwen3_coder --enable-auto-tool-choice --trust-remote-code`, MTP speculative decoding; sampling temperature 1.0, top-p 0.95 for text; thinking switched with `chat_template_kwargs.enable_thinking` (also a `medium_effort` option). No thinking-budget option is documented.

## The hard question: which variant fits L40S
- **None of the cards lists L40S.** NVFP4 is a Blackwell format; on Hopper the cards still list 2× H100, but whether vLLM runs NVFP4 on Ada (L40S) is **unverified**. If it does, 2× L40S (96 GB) holds the 75 GB of weights with little room left; 4× is safer.
- **FP8 runs natively on Ada.** The third-party FP8 checkpoint on 4× L40S (192 GB, tensor parallel 4) is the most likely fit, if a node has 4 GPUs and vLLM supports this architecture's FP8 on Ada (**unverified**).
- BF16 needs 8× L40S (384 GB) on one node, or multi-node tensor/pipeline parallelism.
- Fallback with what already works here: llama.cpp with a 4-bit GGUF, if one exists for Super (**unverified**), over 2–4 L40S, the same stack as the laptop.
Decision rule: take the largest single node with L40S GPUs; prefer FP8 on 4 GPUs; try NVFP4 on 2 if only 2; llama.cpp otherwise.

## How a run is laid out
One batch job on one GPU node runs both halves, so they talk over `localhost` and no ports leave the node:
1. vLLM serves the model on the node's GPUs (port 8000, bound to 127.0.0.1).
2. `scripts/evaluate.py` runs the R2 task on the same node, `--viz none`, with `SOLARBENCH_ENDPOINT_URL=http://127.0.0.1:8000/v1`. The simulation used about 0.3 GB of GPU memory on the laptop, so it can share a GPU with vLLM if `--gpu-memory-utilization` leaves room (e.g. 0.90). Isaac Lab needs a recent NVIDIA driver (the laptop plan asked for >= 580.65): **unverified** on RUDENS.
3. Policy string, as on the laptop's best setup: `endpoint:<served model name>,wrench=on,reasoning=on,temperature=1.0,tools=on,privileged=on,notes=NOTES/probes/lessons_tools.md,rounds=40`. The adapter reads vLLM's `reasoning` field as well as llama.cpp's `reasoning_content`. Thinking is kept natively in the tool loop.
4. Logs and result files go to project storage; nothing is written to `results/` until a run is part of a planned experiment.

## Steps
1. **First login.** Upload the SSH key in Waldur, `ssh <user>@ui-2.hpc.rtu.lv`, clone the fork (`git clone git@github.com:psyberLC/solarbench.git`, branch `live-viewer` once pushed), run `bash NOTES/hpc/discover.sh | tee discover-login.txt`. Read hpc-guide.rtu.lv for the scheduler, GPU request syntax, containers, storage and rules on services.
2. **Interactive GPU job** on an L40S node (syntax from the guide), run `discover.sh` again there: GPU count, driver, internet access.
3. **Software.** If Apptainer exists: `apptainer pull vllm.sif docker://vllm/vllm-openai:v0.32.0` on a node with internet. For the simulation: `uv sync --extra ovphysx` in the clone (needs internet; on the laptop it pulled about 10 GB), or an Isaac Lab container. If compute nodes have no internet, do all downloads on the login node into project storage.
4. **Weights.** Download the chosen variant into project storage (`huggingface-cli download …` or `hf download …`), check the checksums against Hugging Face, as on the laptop.
5. **Smoke tests**, in the interactive job: start vLLM, send one tool-call request (the test in this session: `push` / `turn` tools; it should answer with a parsed tool call and short thinking); run `tools/check.sh --gpu` for the simulation.
6. **First run**: one viewerless episode of the helped scenario (`tools=on,privileged=on`, the lessons file), compared with Lightning's run in `NOTES/LIVE_LESSONS.md`.
7. **Then the experiment proper**: the action plan's runs (floor, ceiling, model with force off and on) on the dev split without privileged data, so the numbers can stand next to `NOTES/REPORT.md`; the helped runs stay exploratory.

## Questions for the HPC centre (if the guide does not answer them)
- How many L40S per node, and are there nodes with larger GPUs (A100/H100/H200)?
- NVIDIA driver version on the GPU nodes (Isaac Lab needs a recent one).
- Apptainer available, and may it pull from Docker Hub / nvcr.io?
- Internet (or a proxy) from compute nodes for Hugging Face and PyPI?
- Where should 100–250 GB of model weights live, and what does a GPU hour cost against the allocation?
