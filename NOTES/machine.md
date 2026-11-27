# Machine and model plan

Measured 2026-11-26 by claude-code (for psyberLC). Exploratory work on the fork `psyberLC/solarbench`, branch `laptop-llm`.

## Machine
| What | Measured |
|---|---|
| OS | Linux Mint 22.3 (Ubuntu 24.04 base), kernel 7.0.0-43-generic, x86_64 |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB, compute capability 8.9 |
| Driver | 615.71.09 (CUDA UMD 13.4); the floor is 580.65 |
| VRAM in use before anything runs | 1.8 to 2.1 GiB (Xorg and the Cinnamon desktop), so about 5.7 to 6.0 GiB free |
| CPU | AMD Ryzen 7 8845HS, 8 cores / 16 threads, AVX-512 (incl. VNNI, BF16) |
| RAM | 32,140,132 kB (30.65 GiB, 32.9 GB) total; about 6.4 GiB in use by the desktop at idle; 2 GiB swap |
| Disk | 699 GB free on `/` |

Hard-stop checks (section 0 of the action plan): Linux x86_64, an NVIDIA GPU, 8 GB of VRAM (the card is sold as 8 GB and reports 8188 MiB) and a driver above 580.65. All pass.

## Simulator footprint (measured, step 2)
The oracle sanity run (`SolarBench-T3-ClampTighten-UR16e-v0`, dev split, 8 episodes, `--num_envs 4`, Newton on `cuda:0`):

| | |
|---|---|
| Result | safe success 8/8 (95% CI 67.6%–100%), damage 0/8 |
| Wall time | 449 s, including about 60 s of start-up |
| GPU memory | 2031 MiB before, 2221 MiB peak: **the simulator itself took about 0.2 GiB** |
| Host RAM | 6446 MiB before, 7582 MiB peak: about 1.1 GiB |

Sampled every 2 s with `NOTES/monitor.sh`; samples are in `NOTES/runs/oracle_sanity.mon`.

## Model plan
The plan's table puts this machine in the first row (RAM ≥ 32 GB): **NVIDIA Nemotron 3 Nano 30B-A3B at 4 bits**, served by `llama-server` with the MoE experts in RAM.

- **Repo and file:** NVIDIA publishes no GGUF of this model (its repos are BF16, FP8 and NVFP4). I used the quantisation from `ggml-org`, the llama.cpp project's own organisation on Hugging Face: [`ggml-org/NVIDIA-Nemotron-3-Nano-30B-A3B-GGUF`](https://huggingface.co/ggml-org/NVIDIA-Nemotron-3-Nano-30B-A3B-GGUF), file `NVIDIA-Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf`.
- **Size:** 22.42 GB, not the 18–20 GB the plan estimated. Every Q4_K_M of this model I found is 22.4–24.7 GB; the 18 GB files are Q4_0 and IQ4.
- **SHA256 (published by Hugging Face):** `0f111a0d49777a2a0178758b1aee14e5365c495987499401ef3ebe87754322a8`. The hash of the downloaded file is checked against it in `NOTES/serve.md`.

Why it fits:
- **The plan's 6 GB VRAM reserve for the simulator does not apply here.** The simulator measured 0.2 GiB. The desktop already holds about 2 GiB, so a 6 GiB reserve would leave the model no GPU at all. I keep a margin of about 1.5 GiB for the simulator and the desktop instead, and give the model what is left (about 4 GiB): attention, the dense layers and as many expert layers as fit. The flags are in `NOTES/serve.sh`. The proof that both run together is in step 3.
- **RAM:** 30.65 GiB total − 6.4 GiB desktop − 1.1 GiB simulator leaves about 23 GiB. The model needs about 22.4 GB − ~4 GB on the GPU ≈ 18 GB in RAM, plus a small KV cache. Nemotron 3 Nano is a hybrid Mamba–Transformer, so only a few layers keep a KV cache. The file is memory-mapped, so under pressure its pages are dropped and re-read rather than killed.
- About 3B parameters are active per token, so the experts stay usable on the CPU (8 Zen 4 cores with AVX-512).
