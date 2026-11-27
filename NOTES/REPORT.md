# Report: an open-weight model driving SolarBench's bolt task on a laptop

Exploratory work on the fork [`psyberLC/solarbench`](https://github.com/psyberLC/solarbench), branch `laptop-llm`, 2026-11-26/27, by claude-code (for psyberLC). Nothing was pushed to, opened on or claimed in `rad-robotics/solarbench`; pushes to it are disabled in this clone (`git remote set-url --push origin DISABLED`).

**In one paragraph.** The bolt-tightening task now runs under profile R2 (one tool pose per command) on its own task id. The evaluator hands a policy the task's catalogue, the channels it selected and the work order. The maintainer's chat-completions adapter drives that task from a local llama.cpp server running NVIDIA Nemotron 3 Nano 30B-A3B (4-bit), on an 8 GB laptop GPU next to the simulator. The oracle, replayed as poses, succeeds 16/16. The model succeeded 0 times in 40 episodes, with force off, with force on and without reasoning. It aimed the socket at the bolt head but almost never pointed it along the bolt's axis, so it never made contact. These runs are exploratory: dev split, lockstep time, a model that is not pre-registered, quantised, with its thinking capped at 2,048 tokens. They rank nothing.

## 1. Machine and model plan
Details and measurements: [`NOTES/machine.md`](machine.md), [`NOTES/serve.md`](serve.md).

| | |
|---|---|
| Machine | Linux Mint 22.3, AMD Ryzen 7 8845HS (8 cores, AVX-512), 30.65 GiB RAM, RTX 4060 Laptop 8 GB (driver 615.71, CUDA 13.4). The desktop holds about 2 GiB of VRAM |
| Simulator footprint | About 0.2–0.4 GiB of GPU memory and about 1.1–1.6 GiB of RAM at 4 environments (Newton). The oracle sanity run scored 8/8 in 449 s |
| Model | NVIDIA Nemotron 3 Nano 30B-A3B, Q4_K_M GGUF from `ggml-org` (NVIDIA publishes no GGUF), 22.42 GB, SHA256 `0f111a0d…22a8`, checked |
| Server | llama.cpp b12780, prebuilt for CUDA 12.8, `NOTES/serve.sh`: 4 slots × 20,480 tokens, all layers on the GPU except 50 of 52 layers' experts, which stay in RAM (about 3.9 GB of VRAM). Model-card sampling (temperature 1.0, top-p 1.0) with reasoning on, greedy with it off. Thinking budget 2,048 tokens |
| Speed | One stream: 24–30 tokens/s written. Four at once: 12.7 each, about 45 in total. The prompt is read at 63–115 tokens/s; the server's cache keeps each conversation's prefix, so a round reads only its new ~300 tokens |

**Deviations from the plan, and why.**
- **Q4_K_M is 22.4 GB, not 18–20 GB.** Every Q4_K_M of this model is 22.4–24.7 GB. It fits: about 18 GB in RAM and 4 GB on the GPU.
- **The 6 GB simulator reserve was not kept.** The simulator measured 0.2–0.4 GB, and the desktop already uses 2 GB, so a 6 GB reserve would have left the model no GPU at all. I kept about 1.6 GB of headroom instead. The proof that both run together is in [`serve.md`](serve.md): GPU memory peaked at 6.94 of 7.86 GB with the server answering four requests during `tools/check.sh --gpu`, and the check passed.
- **Context 81,920, not 32,768.** With 4 slots, 32,768 gives 8,192 tokens per conversation, too few for 20 rounds plus the ~1,000-token prefix.
- **Thinking budget of 2,048 tokens** (`--reasoning-budget`). Uncapped, 2 of 4 first-round replies spent the whole 4,096-token reply limit thinking and returned nothing, and a round took 5 minutes. Capped, all answered in about 3 minutes with four at once. This changes the model's behaviour and is a confound for anything said about reasoning.
- **Round cap 20 per episode**, to keep each reasoning run to a few hours.
- **Clone in `~/Projects/solarbench-llm`**, the session folder, rather than `~/solarbench`.

## 2. What was built
Each item is one branch and one pull request into `psyberLC/solarbench:laptop-llm`, merged after `tools/check.sh` (and `--gpu` for the GPU items) passed locally. The fork has no CI. Each board file has the dated log and the quoted check output.

| Item | PR | What |
|---|---|---|
| `contract-harness-catalogue` | [#1](https://github.com/psyberLC/solarbench/pull/1) | `scripts/evaluate.py` takes the catalogue from the task and hands a policy exactly the channels it selected. `reset(env_ids, work_orders)` delivers the work order. The connector publishes its catalogue (clock and privileged vector). Probe: a `proprio`-only policy got `clock` and `proprio` and a work order at every reset, and its result is `privileged = False` |
| `sim-pose-action` | [#2](https://github.com/psyberLC/solarbench/pull/2) | `SolarBench-T3-ClampTighten-UR16e-R2-v0`. `TOOL_POSE` records run as rate-limited R1 steps through the existing IK and limits, and end as arrived, stalled or timed out with a completion record. `DONE` ends the episode. The oracle replayed as one-tick `TOOL_POSE` waypoints scored 8/8 (dev), with installed torques within 0.04 N·m of R1's on the same seeds; zero scored 0/8. Thresholds are in ASSUMPTIONS M13 |
| `agents-endpoint` | [#3](https://github.com/psyberLC/solarbench/pull/3) | The maintainer's adapter from the upstream `agents-endpoint` branch (their commits kept), plus a reasoning switch, a round cap, a JSON-lines call log, `url=`, a second ask after an unreadable reply, and a reader that accepts a JSON object over several lines. Tested against a fake server |
| `eval-latency` | — | Skipped, as the plan says. Every run here is lockstep: the simulation waits for the model, so a model that thinks for three minutes is scored as if it answered at once |

Also on `laptop-llm`, outside the board: `NOTES/` (machine, server, probes, run script, analysis, this report) and the run outputs in `NOTES/runs/`. For each run these are the result file, the console log, GPU and RAM samples, and for model runs `*.calls.jsonl`: one line per call, with the reply, the full reasoning text, the command, tokens and wall time.

## 3. Results
Tables below are copied from [`NOTES/results.md`](results.md), which `NOTES/analyze.py` writes from the result files and call logs in [`NOTES/runs/`](runs/). The per-episode table, with each failure label, is there too. All cells use the task `SolarBench-T3-ClampTighten-UR16e-R2-v0`, dev split, Newton, lockstep. Every cell ran on the same seeds: the bolt parameters drawn per episode match across runs.

**What they say.**
- **The task can be done through R2, and the model did not get near doing it.** The oracle, replayed as poses, scored 16/16. Nemotron scored 0 safe successes with force off (0/16), with force on (0/16) and without reasoning (0/8). It never seated the socket and never turned the bolt, so it also never damaged it. With 16 episodes, 0/16 is compatible with a true rate up to 19%.
- **H1 points the same way but is not tested here.** H1 is about other models, and its 10% threshold sits inside the 0–19% interval. **H2 and H3 are untestable on these numbers:** force on and off both scored zero with zero damage. The one difference is behavioural. With force on, episodes used more rounds (10.7 against 7.0 on average), and fewer ended with the model's own `DONE` (10 against 14 in the result's episodes).
- **The failure is upstream of contact: the socket's orientation.** The model aimed the socket face at the head well: the median distance to the head top was 8–13 mm with reasoning, and exactly the head top without it. But the socket pointed the wrong way. Of 300 commanded poses with reasoning, one had the socket axis within 6° of the bolt's (seating needs 6°); the median error was 160°. The commonest single error was writing the bolt's axis vector into the quaternion's vector part with w = 0, a half turn about the axis rather than a pose along it. That was 19% of poses with force off, 34% with force on, and every pose with reasoning off (greedy decoding repeated it in all 8 episodes). So 39 of the 40 model failures are labelled *wrong target*. The exception (force on, episode 3) found the right orientation once, in round 17 (0.4° off), and abandoned it the next round. Its reasoning also put the 2.5 mm seating offset on the wrong side of the head top.
- **Every reply was readable.** 513 calls, 0 unreadable, none cut off at `max_tokens`.
- **The thinking budget was binding.** 91% (force off) and 98% (force on) of reasoning calls wrote 2,048 tokens or more, so the server cut the model's thinking almost every round. These results are for Nemotron with its thinking capped. They do not show what it does when it can think to the end.
- **Speed.** With reasoning, a round took a median of 63–64 s, mostly one request at a time, and the cells ran at 4–6 episodes per hour: 2.5 and 4.0 hours of wall time. Without reasoning a round took 3.3 s and the cell ran at 21 episodes per hour, limited by the simulator. The server's cache held 87–93% of each prompt. All of this is lockstep (`eval-latency` was skipped): the simulated world waited a minute per round, which the robot would not get.

### Outcomes

| Run | Policy | Safe success | Damage | Engaged | Snug | In spec | Released | Furthest stage, mean |
|---|---|---|---|---|---|---|---|---|
| Floor: `zero` | `zero`… | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0.00 (0.00–0.00) of 4 |
| Ceiling: `oracle` replayed as TOOL_POSE | `oracle`… | 16/16 (100%; 81–100%) | 0/16 (0%; 0–19%) | 16/16 (100%; 81–100%) | 16/16 (100%; 81–100%) | 16/16 (100%; 81–100%) | 16/16 (100%; 81–100%) | 4.00 (4.00–4.00) of 4 |
| Model, force off, reasoning on | `endpoint:NVIDIA-Nemotron-3-Nano-30B-A3B-Q4_K_M`… | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0.00 (0.00–0.00) of 4 |
| Model, force on, reasoning on | `endpoint:NVIDIA-Nemotron-3-Nano-30B-A3B-Q4_K_M`… | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0.00 (0.00–0.00) of 4 |
| Speed probe: force on, reasoning off | `endpoint:NVIDIA-Nemotron-3-Nano-30B-A3B-Q4_K_M`… | 0/8 (0%; 0–32%) | 0/8 (0%; 0–32%) | 0/8 (0%; 0–32%) | 0/8 (0%; 0–32%) | 0/8 (0%; 0–32%) | 0/8 (0%; 0–32%) | 0.00 (0.00–0.00) of 4 |

Simulator errors: floor 0%, ceiling 0%, model-force-off 0%, model-force-on 0%, speed-probe 0%

### Model calls

A round is one command asked for: one call, or two when the first reply could not be read.

| Run | Calls | Rounds | Rounds per episode, mean | Wall per round, s: median (p90) | Tokens read per call, mean (cached) | Tokens written per call, mean (max) | Unreadable calls | Rounds with no command | Cut off at max_tokens | Calls writing ≥ 2,048 tokens | Episodes hit the round cap | Episodes per hour |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Model, force off, reasoning on | 139 | 139 | 7.0 | 63.7 (84.2) | 2523 (2190) | 2038 (2138) | 0/139 (0%; 0–3%) | 0/139 (0%; 0–3%) | 0 | 126/139 (91%; 85–94%) | 2 of 20 | 6.3 |
| Model, force on, reasoning on | 214 | 214 | 10.7 | 63.4 (70.8) | 3840 (3422) | 2089 (2124) | 0/214 (0%; 0–2%) | 0/214 (0%; 0–2%) | 0 | 209/214 (98%; 95–99%) | 5 of 20 | 4.0 |
| Speed probe: force on, reasoning off | 160 | 160 | 20.0 | 3.3 (6.8) | 4747 (4428) | 57 (57) | 0/160 (0%; 0–2%) | 0/160 (0%; 0–2%) | 0 | 0/160 (0%; 0–2%) | 8 of 8 | 21.2 |

Tokens written include the thinking. The server cut thinking at 2,048 tokens (`--reasoning-budget`); a call that wrote 2,048 or more almost certainly reached that cut, since the answer itself is about 60 tokens.

Episodes per hour counts the episodes in the result over the run's whole wall time, start-up included. Calls and rounds include episodes that were still running when the result's episodes were complete; those episodes are not in the result.

### What the model commanded

Over the episodes in each result. The socket seats only with its axis within 6° of the bolt's.

| Run | Poses | Socket axis within 6° of pointing into the head | Within 15° | Bolt axis written as the quaternion (w = 0) | Median socket-axis error, deg | Median distance to the head top, mm | DONE |
|---|---|---|---|---|---|---|---|
| Model, force off, reasoning on | 115 | 0 | 0 | 22/115 (19%; 13–27%) | 160 | 8.3 | 14 |
| Model, force on, reasoning on | 185 | 1 | 1 | 62/185 (34%; 27–41%) | 160 | 12.5 | 10 |
| Speed probe: force on, reasoning off | 160 | 0 | 0 | 160/160 (100%; 98–100%) | 160 | 0.0 | 0 |

### Failure labels

One label per failed episode, assigned in this order: damage → over-force; no reply in the episode could be read → malformed output; never engaged → no contact if some command put the socket face within 10 mm of the head top with the socket axis within 15° of pointing into the head, else wrong target; engaged but never snug → lost contact; snug but never in the window → under-force; in the window but never withdrawn → time out.

| Run | Failed | Labels |
|---|---|---|
| Model, force off, reasoning on | 16 | wrong target: 16 |
| Model, force on, reasoning on | 16 | wrong target: 15, no contact: 1 |
| Speed probe: force on, reasoning off | 8 | wrong target: 8 |

## 4. What did not work, what was skipped, what is not verified
**What limits these results.**
- **Lockstep, dev split, 16 episodes per cell, Newton only.** Nothing here is rankable, and the intervals are wide: 0/16 is compatible with up to 19%.
- **Every run's result file says `solarbench_dirty: true`.** The cause is the untracked analysis script and this report, which I was writing in `NOTES/` while the runs went. All five ran the code at commit `b76a721`; no tracked file changed during the runs. The console logs in `NOTES/runs/` have local home paths replaced by `~`; the result files and call logs are unedited.
- **A quantised model with capped thinking.** Q4_K_M, with thinking cut at 2,048 tokens. Neither is the model NVIDIA evaluates. H1 to H6 are about other models; Nemotron is not pre-registered.
- **Throughput set the design.** With four environments, rounds mostly went to the server one or two at a time. In lockstep the simulation stops while any request is open, and environments wake together only when their commands end on the same tick. So the four slots rarely ran full. That is why the round cap is 20 and why the speed probe has 8 episodes. A faster server, or the measured time mode (`eval-latency`), changes this.
- **The wrist sensor cannot see the torque window.** The UR16e's built-in sensor saturates at ±10 N·m (ASSUMPTIONS M12), below the 14–18 N·m window. With force on, the model can feel contact and the run-down, but not whether the bolt is in the window.

**Failure labels are a rule applied to a short record.**
- The episode record says which stages were reached, not how. "Lost contact" here means engaged but never snug, which could also be a socket that sat on the head and never turned the bolt. "Time out" means in the window but never withdrawn, including an episode the model ended with `DONE`. No episode reached those stages, so neither label was used.
- I wrote the first rule for "no contact" against "wrong target" from position alone. After seeing the first episodes, where positions were near the head but the socket pointed elsewhere, I added the orientation condition (socket axis within 15° of pointing into the head), before computing any table. The bolt axis it uses is the one the work order states, (0, 0.342, 0.940), checked against the task's layout code.

**Things that did not work as planned.**
- The log files of both `tools/check.sh --gpu` runs were overwritten with NUL bytes partway through, probably by a child process that reopens standard output. The numbers quoted in the board logs come from the result files those runs wrote, and the CPU part was rerun on its own to quote its output. Later runs piped their output through `cat`, which cannot be truncated, and their logs are intact.
- The oracle replay sends a waypoint every tick. It shows that the R2 pose path reproduces the R1 trajectory, not that coarse waypoints can do the task.
- The fork has no CI. Each PR was merged on local checks alone.

**Skipped.**
- `eval-latency` (as the plan says), so H6 and anything about thinking time are untested.
- PhysX runs of the R2 task and of the model.
- A loosening R2 id.
- Writing call statistics into the result files (`contract-result-fields`). They are only in `NOTES/runs/*.calls.jsonl`.

**Not verified.**
- That the model is the one NVIDIA released, beyond the file hash matching `ggml-org`'s published hash. The quantisation's accuracy cost was not measured.
- vLLM, the HPC section and every candidate model in it. Nothing there was run.
- That `mit-han-lab/Qwen3.8-27B-PEAR` is the PEAR paper's checkpoint.
- `docs/interface.md` ("no task uses them yet") and the bolt card in `docs/tasks.md` ("does not hand these to a policy yet") are out of date on the fork. Neither file was in the items' paths, and `docs/tasks.md` is append-only.

## 5. Moving to the HPC
The code needs no change: the adapter reads the server's address from `SOLARBENCH_ENDPOINT_URL` (or `url=`), and anything that speaks chat completions works. What changes is the server and where it runs.

**Serving with vLLM behind the same endpoint.** vLLM serves an OpenAI-compatible `/v1/chat/completions`. Point `SOLARBENCH_ENDPOINT_URL` at `http://<node>:8000/v1` and keep the policy string. Settings that move with it:
- Reasoning on or off goes through `chat_template_kwargs.enable_thinking`, which vLLM passes to the chat template as llama.cpp does. Check that each model's template reads that key.
- The thinking budget here was a llama.cpp server flag. Under vLLM, either leave thinking uncapped, which the datacentre can afford and which removes the confound, or find the equivalent control for that server and model. State which in the result.
- Sampling: send the model card's values explicitly (the adapter sends temperature; set top-p, top-k and min-p on the server or add them to the request). Servers' defaults differ, and some take them from the model's own generation config.
- Make sure prefix caching is on (`--enable-prefix-caching`; recent vLLM versions may enable it by default). Each request extends the previous one, so cache hits are what keep a round cheap.
- Allow at least as many concurrent sequences as environments.

None of the vLLM points above was tried here; check them against the vLLM version the cluster uses.

**Candidates.** Each is a Hugging Face repo I found by name; none was downloaded or run here.

| Model | Repo | Note |
|---|---|---|
| Nemotron 3 Nano 30B-A3B, unquantised | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16` (FP8 and NVFP4 also published) | The same model as here without quantisation or a thinking cap: separates the laptop's compromises from the model |
| Nemotron 3 Super 120B-A12B | `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16`, `-NVFP4` | About 240 GB in BF16 (120B parameters at 2 bytes). NVFP4 is a Blackwell-generation format; check the cluster's GPUs before choosing it |
| Cosmos Reason2 32B | `nvidia/Cosmos-Reason2-32B` | A vision-language model. Worth it only once a task offers cameras (`sim-cameras`, `sim-wire-cameras`) |
| Qwen3.8-27B (pre-registered) | `Qwen/Qwen3.8-27B`, `Qwen/Qwen3.8-27B-FP8` | One of the two brains in `paper/hypotheses.md` |
| PEAR (pre-registered) | `mit-han-lab/Qwen3.8-27B-PEAR` (and `-NVFP4`) appears to be the checkpoint of [PEAR](https://arxiv.org/abs/2611.18562); not confirmed against the paper | The other pre-registered brain |

**What to find out about the cluster first** ([`docs/compute.md`](../docs/compute.md)):
1. The NVIDIA driver version on the GPU nodes. The simulator stack needs 580.65 or later, and a container cannot bring its own.
2. Which GPUs have ray-tracing cores. Simulation does not need them; rendering may.
3. Whether compute nodes reach the internet. If not, stage wheels, model weights and robot descriptions beforehand.
4. The container runtime (Singularity or Apptainer with `--nv`) and its version.
5. Storage quotas, scratch paths and the purge policy. The environment is about 10 GB, and a 27B model about 54 GB unquantised.

The scheduler templates target Torque/PBS. Run the model server and the simulator on one node (two GPUs, or one large one), and one job per cell so that a failed job costs one cell.

**Board items that come next, in order.**
1. `infra-container`: container and job templates, with everything staged. Needed before anything runs on the cluster.
2. `agents-serve`: the vLLM (or other) recipe for Qwen3.8-27B and PEAR on 48 GB GPUs, with tokens per second at 1, 8 and 16 concurrent requests and the accuracy cost of any quantisation.
3. `eval-latency`: measured and fixed-delay time, so that the minutes a model thinks count. H6 needs it, and the numbers here are all lockstep.
4. `contract-result-fields`: the selection, prompt hash, model, server, sampling and per-call tokens in the result file. Today they live only in `NOTES/runs/*.calls.jsonl`.
5. `contract-skill-opcodes`, then `sim-guarded-skills`, then `agents-skill-tools`: rung R3, where the model names a force skill and a fixed controller does the contact. That is the rung H4 is about.

## 6. Decisions left to the developer and the maintainer
- Whether any of the three branches should be proposed upstream. They were written to the board's rules (one item, one branch, `touches` respected, dated log), but the fork's `agents-endpoint` builds on the maintainer's unmerged branch, and `docs/tasks.md` still says the evaluator does not hand channels to a policy.
- Your open upstream PR [rad-robotics/solarbench#14](https://github.com/rad-robotics/solarbench/pull/14) (`sim-bolt-newton-speed`, opened before this session) changes `solarbench/tasks/clamp_env.py`, which `sim-pose-action` also changes (it appends `ClampPoseEnv`). If both go upstream, one will need a rebase. The board's overlap check would flag the two claims as sharing a path.
- Whether to pre-register Nemotron (it is not in `paper/hypotheses.md`, so these runs are exploratory).
- Whether R2's arrival rule (0.5 mm and 0.005 rad, settled) and its stall rule are the right controller choices (ASSUMPTIONS M13).
