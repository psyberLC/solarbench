# Model server on the laptop

Set up 2026-11-26/27 by claude-code (for psyberLC). Everything here is outside the repository's Python environment, under `~/llm/`.

## What is installed
| What | Where | Source and check |
|---|---|---|
| llama.cpp b12780 (`1.1.0-dev`, commit `09c141064`), prebuilt for CUDA 12.8 | `~/llm/b12780/` | GitHub release `b12780` of `ggml-org/llama.cpp`. SHA256 of `llama-b12780-bin-ubuntu-cuda-12.8-x64.tar.gz`: `dccde682…bfdb`; of `cudart-llama-b12780-bin-ubuntu-cuda-12.8-x64.tar.gz`: `f68edfa7…c12d`. Both match the digests GitHub publishes |
| Wrapper that adds the bundled CUDA runtime to the library path | `~/llm/llama-server` | written here |
| NVIDIA Nemotron 3 Nano 30B-A3B, Q4_K_M GGUF (22.42 GB) | `~/llm/models/NVIDIA-Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf` | `ggml-org/NVIDIA-Nemotron-3-Nano-30B-A3B-GGUF`. SHA256 `0f111a0d49777a2a0178758b1aee14e5365c495987499401ef3ebe87754322a8`, which matches Hugging Face's |

CUDA 12.8 rather than 13.5: the driver reports CUDA 13.4, which runs any 12.x runtime; the 13.5 build might need a newer driver. No CUDA toolkit is installed; none is needed.

## How it is started
`NOTES/serve.sh` (or `NOTES/serve.sh --daemon`). Flags and why:

| Flag | Why |
|---|---|
| `--host 127.0.0.1 --port 8080` | This machine only |
| `--jinja` | The model's own chat template, which has the `enable_thinking` switch |
| `--parallel 4 --ctx-size 81920` | Four simultaneous conversations (one per environment) of up to 20,480 tokens each. The plan's 32,768 gives 8,192 per conversation. The fixed prefix is about 1,000 tokens (system 601 without force, 674 with; work order 347) and each round adds about 300 plus the reply, so 20 rounds need about 9,000 and the larger context leaves room for a reply that rambles |
| `-ngl 99 --n-cpu-moe 50` | Every layer on the GPU except the expert weights of the first 50 of 52 MoE layers, which stay in RAM. llama.cpp's own `--fit` chose 50 to 52 depending on free memory. With 50 the server holds about 3.9 GB of GPU memory, which leaves about 1.6 GB over the desktop (about 2 GB) and the simulator (about 0.3 GB) |
| `--top-p 1.0 --top-k 0 --min-p 0` | The model card's sampling for reasoning (temperature 1.0, top-p 1.0); llama-server's defaults would otherwise add top-k 40 and min-p 0.05. Temperature is sent per request |
| `--reasoning-budget 2048` | Caps thinking at 2,048 tokens, after which the model must answer. Without it, 2 of 4 first-round replies used all 4,096 tokens on thinking and returned nothing, and a round took up to 5 minutes. With it, all four answered in 185 s. This is a setting of this laptop run that changes the model's behaviour; the model card describes a thinking budget as a supported control |

## Measured
Single request, short prompt: prompt read at 77–115 tokens/s (11 tokens/s on the very first call while the weights were paged in), written at 24–27 tokens/s.

The real first round (system message, work order and one state, 1,280 tokens), four requests at once:

| Reasoning | Budget | Simulator running too | Tokens written per request | Per request | All four | Wall time of the round |
|---|---|---|---|---|---|---|
| on | none | yes (`tools/check.sh --gpu`) | 1,915–4,096 (one hit the cap) | 12–12.6 tok/s | 34.5 tok/s | 345 s |
| on | none | no | 2,571–4,096 (two hit the cap) | 12.2–14.3 tok/s | 46.0 tok/s | 297 s |
| on | 2,048 | no | 2,091–2,111 | 12.7 tok/s | 45.4 tok/s | 185 s |
| off | n/a | no | about 50 | | 64 tok/s | 3.1 s |

`NOTES/probes/bench_server.py` produced these.

## Simulator and server together
- While four reasoning requests were answered (the first row above), `tools/check.sh --gpu` ran the bolt oracle and zero policy on the same GPU. GPU memory peaked at 6,938 of 7,863 MiB, with no out-of-memory error, and the check passed.
- The R2 oracle (8 episodes, 4 environments) ran with the server loaded: GPU memory 6,702–6,963 MiB, 464 s against 449 s without the server, 8/8 safe success.
- During a model run the two take turns: the simulation waits while the model answers (lockstep), so they never compete for long.

## Restarting
```bash
kill $(pgrep -x llama-server); NOTES/serve.sh --daemon
```
`NOTES/run_all.sh` does this itself if the server stops answering.
