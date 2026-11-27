# Plan: Nemotron 3.5 Super on RTU's RUDENS cluster, as the laptop's model endpoint

Written 2026-11-27 by claude-code (for psyberLC), before anyone has logged in. The simulation and the viewer stay on the laptop; the cluster only serves the model. Everything marked **unverified** has to be checked on the cluster first; `NOTES/hpc/discover.sh` prints most of it.

## What is known
**The cluster** (from https://hpc-platforma.rtu.lv; the detailed user guide, https://hpc-guide.rtu.lv, could not be read from here: the fetch was refused by this session's permission check, so it still needs reading by you):
- RUDENS, RTU HPC. Login `ssh <user>@ui-2.hpc.rtu.lv`, SSH keys only, uploaded in the Waldur portal (https://nohap.hpc-net.lv, Credentials → SSH keys; wait 5 minutes). Web terminal: Open OnDemand, https://ood.hpc.rtu.lv/.
- Use is charged to a Waldur project allocation in euros covering CPU hours, GPU hours and memory.
- A MATLAB example requests GPUs with the feature `l40s`, so there are NVIDIA L40S GPUs (48 GB, Ada). **Unverified**: GPUs per node, other GPU models, scheduler (Slurm or PBS), queues, walltime, containers, internet on compute nodes, storage, and whether a job may run a network service that is reached from outside.

**The model** (Hugging Face cards, released 2026-10-15, licence OpenMDW-1.1): the official "Nemotron 3.5 Super" is `nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B`, a vision-language Mamba–transformer mixture of experts, 120B parameters with 12B active, up to 1M tokens of context, with multi-token prediction. It answers text-only prompts like ours.
| Variant | Size | Cards' hardware |
|---|---|---|
| `…-BF16` | 249 GB | 4× H100 or 2× GB200 |
| `…-NVFP4` | 75.1 GB | 1× H200, 2× H100, 1× RTX PRO 6000, 1× GB200, DGX Spark |
| `RedHatAI/…-FP8` (third party) | not checked (about 125 GB expected for 124B parameters at one byte) | not stated |
Serving per the cards: vLLM `vllm/vllm-openai:v0.32.0`, `--reasoning-parser nemotron_v3 --tool-call-parser qwen3_coder --enable-auto-tool-choice --trust-remote-code`, MTP speculative decoding, `--enable-mamba-shared-prefix-checkpoint --mamba-cache-mode align` in the NVFP4 recipes; sampling temperature 1.0, top-p 0.95 for text; thinking switched with `chat_template_kwargs.enable_thinking` (also a `medium_effort` option). No thinking-budget option is documented.

## Which variant fits L40S
- **None of the cards lists L40S.** NVFP4 is a Blackwell format; on Hopper the cards still list 2× H100, but whether vLLM runs NVFP4 on Ada (L40S) is **unverified**. If it does, 2× L40S (96 GB) holds the 75 GB of weights with little room left; 4× is safer.
- **FP8 runs natively on Ada.** The third-party FP8 checkpoint on 4× L40S (192 GB, tensor parallel 4) is the most likely fit, if a node has 4 GPUs and vLLM supports this architecture's FP8 on Ada (**unverified**).
- BF16 needs 8× L40S (384 GB) on one node, or multi-node parallelism.
- Fallback with what already works on the laptop: llama.cpp with a 4-bit GGUF, if one exists for Super (**unverified**), over 2–4 L40S. The adapter, tool calls and proxy are already tested against llama.cpp.
Decision rule: take the largest single node with L40S GPUs; prefer FP8 on 4 GPUs; try NVFP4 on 2 if only 2; llama.cpp otherwise.

## How a run is laid out
- **Cluster:** one batch job on one GPU node runs vLLM for its walltime, listening on port 8000 and requiring an API key (`--api-key`, a random string generated for the job, never written into the repository). It writes its node name and the key's location to a file in your home directory.
- **Laptop:** an SSH tunnel through the login node to that node, `ssh -N -L 8000:<node>:8000 <user>@ui-2.hpc.rtu.lv`, so the model appears at `http://127.0.0.1:8000/v1`. Whether a login node may forward to a compute node's port is **unverified** (the alternative is a jump to the node itself, `ssh -J <user>@ui-2.hpc.rtu.lv -N -L 8000:127.0.0.1:8000 <user>@<node>`, if the cluster lets a job's owner SSH to its node).
- **The run, on the laptop:** `NOTES/live.sh` with the viewer, as before, pointed at the tunnel: `URL=http://127.0.0.1:8000/v1 HOST=remote MODEL=<served name> TOOLS=on PRIVILEGED=on LESSONS=NOTES/probes/lessons_tools.md TEMP=1.0 …`, and `SOLARBENCH_ENDPOINT_KEY` set in the shell from the key file (sent as a bearer token; the adapter never stores or logs it). `HOST=remote` makes the result file record the model as remote although the URL is local. The live proxy can sit in front of the tunnel as on the laptop (`watch_proxy.py --to http://127.0.0.1:8000`).
- **What crosses the network:** one request per round, a few kilobytes of state report in and a tool call out; the conversation grows by each round's thinking, which vLLM's prefix cache keeps on the cluster. The simulation waits for each answer, so network latency adds to each round but cannot change the physics.
- **The adapter is ready:** tool calls, kept thinking (native in the tool loop), vLLM's `reasoning` field as well as llama.cpp's `reasoning_content`, `host=remote`, bearer key from the environment.

## Steps
1. **First login.** Upload the SSH key in Waldur, `ssh <user>@ui-2.hpc.rtu.lv`, copy `NOTES/hpc/discover.sh` across (`scp`) and run `bash discover.sh | tee discover-login.txt`. Read hpc-guide.rtu.lv for the scheduler, GPU request syntax, containers, storage and the rules on services and ports.
2. **Interactive GPU job** on an L40S node (syntax from the guide); run `discover.sh` there too: GPU count and memory, driver, internet access.
3. **vLLM.** If Apptainer exists: `apptainer pull vllm.sif docker://vllm/vllm-openai:v0.32.0` on a node with internet; otherwise ask the centre (or use llama.cpp's prebuilt CUDA binaries, as on the laptop).
4. **Weights.** Download the chosen variant into project storage (`hf download <repo> --local-dir …`), check the checksums against Hugging Face, as on the laptop.
5. **Smoke test on the cluster**, in the interactive job: start vLLM bound to 127.0.0.1 and send one tool-call request with `curl` (the `push` / `turn` test from this session: it should answer with a parsed tool call and short thinking).
6. **Tunnel test from the laptop:** start vLLM as a batch job, open the tunnel, run the same request from the laptop, then one viewer episode of the helped scenario and compare with Lightning's run in `NOTES/LIVE_LESSONS.md`.
7. **Then the experiment proper:** the action plan's runs (model with force off and on) on the dev split without privileged data, so the numbers can stand next to `NOTES/REPORT.md`; the helped runs stay exploratory.

## Questions for the HPC centre (if the guide does not answer them)
- How many L40S per node, and are there nodes with larger GPUs (A100/H100/H200)?
- May a batch job run a service (vLLM on a port) for its walltime, and may it be reached from outside through an SSH tunnel via the login node? Is there a preferred way (Open OnDemand app, reverse proxy)?
- Apptainer available, and may it pull from Docker Hub / nvcr.io?
- Internet (or a proxy) from compute nodes for Hugging Face?
- Where should 100–250 GB of model weights live, and what does a GPU hour cost against the allocation?
