# Skills for a small open model: oracle vs fixed script vs Nemotron 3.5 Lightning

Laptop runs of 2026-11-27 by claude-code (for psyberLC) on the fork's `live-viewer` branch. Exploratory: these are not benchmark results, they are not in `results/`, and the setups below are easier than the benchmark's tasks. How the setups came about is in [LIVE_LESSONS.md](LIVE_LESSONS.md).

## What was compared
Three brains on the **same 8 episodes** (dev split, episodes 0–7: the same bolts, connectors and draws), one environment at a time, each task's **own time limit and work order** (bolt 30 s, connector 24 s), code at commit `b993000`:
- **Oracle**: the scripted, privileged controller of each task (`solarbench/oracle/`), the ceiling.
- **Fixed script**: the skills below, called in a fixed order by `NOTES/probes/scripted_skills.py`, no model. It is the ceiling of a brain that uses the same skills.
- **Lightning**: NVIDIA Nemotron 3.5 Lightning 30B-A3B, Q4_0 GGUF (`ggml-org`, SHA256 `b09a3de2…133b`), llama.cpp b12780 on the laptop's RTX 4060 (8 GB), thinking on (cap 4,096 tokens), temperature 0.6, top-p 0.95, native tool calls, its earlier thinking kept in the conversation. No notes file beyond the tools' descriptions (and, for the connector, a short job description: the task has no work order yet).

**Bolt (T3, R2 pose interface): unprivileged.** The skills `seat`, `tighten_to`, `unload`, `retract` (`solarbench/agents/skills.py`) and the pose tools `aim`, `push`, `turn` use only what any policy has: the work order's head position and axis (printed to the millimetre), the tool pose (`proprio`) and the wrist force-torque sensor (`wrench`, ±10 N·m). `seat` searches for the hex flats under a light press and, once in contact, follows the sensed sideways force; `tighten_to` extrapolates torque above the sensor's range along the line its in-range readings make against the angle the tool actually turned. Result files record `privileged: false`.

**Connector (T2, humanoid G1, R1 interface): privileged by necessity.** The task offers only the privileged channel, so no unprivileged brain can act on it. The skills `grasp`, `unplug`, `plug_in`, `release` (`solarbench/agents/phases.py`) run the oracle's own controller for its phase groups; a brain only chooses the order. A run therefore tests sequencing, not control.

Model and script runs are a much easier task than the benchmark's: the skills do the control, every tick; the brain picks the next skill.

## Results
Rates are k/n (%, 95% Wilson interval); generated from the result files by `NOTES/report_tables.py` (full output: `report-runs/tables.md`).

### Bolt: `SolarBench-T3-ClampTighten-UR16e-R2-v0`
| | privileged | valid / run | engaged | snug | in spec | released | safe success | damage | time to release, s (median) |
|---|---|---|---|---|---|---|---|---|---|
| oracle | yes | 8/8 | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 0/8 (0%, 0–32) | 15.2 |
| skills, fixed script | **no** | 8/8 | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 0/8 (0%, 0–32) | 17.4 |
| skills, Lightning | **no** | 8/8 | 5/8 (62%, 31–86) | 4/8 (50%, 22–78) | 2/8 (25%, 7–59) | 2/8 (25%, 7–59) | 2/8 (25%, 7–59) | 0/8 (0%, 0–32) | 19.5 |

Installed torque by episode (N·m): oracle 16.02–16.08; script 15.43–15.59; Lightning 14.98, 1.12, 0.56, 15.59, 4.39, 2.94, 3.81, 0.53. Lightning: 58 calls, median 6 per episode, median 448 tokens per call (max 2,199), 22.0 min of model time, every call a usable tool call.

### Connector: `SolarBench-T2-MC4-G1-v0`
| | privileged | valid / run | grasped | unlocked | separated | realigned | relatched | released | safe success | damage | time to release, s (median) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| oracle | yes | 7/8 | 7/7 (100%, 65–100) | 7/7 | 7/7 | 7/7 | 7/7 | 7/7 | 7/7 (100%, 65–100) | 0/7 (0%, 0–35) | 5.1 |
| phase skills, fixed script | yes | 8/8 | 8/8 (100%, 68–100) | 8/8 | 8/8 | 8/8 | 7/8 (88%, 53–98) | 7/8 | 7/8 (88%, 53–98) | 0/8 (0%, 0–32) | 6.3 |
| phase skills, Lightning | yes | 8/8 | 8/8 (100%, 68–100) | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 (100%, 68–100) | 0/8 (0%, 0–32) | 6.8 |

Lightning: 32 calls (4 per episode, the shortest possible: grasp, unplug, plug_in, release), median 111 tokens per call, 2.1 min of model time. The oracle lost episode 1 to a numerical failure (an invalid episode, excluded by the evaluator); in an earlier one-environment oracle run the same episode was valid and succeeded, and in earlier script runs episodes 1 and 2 failed numerically, so these failures are not tied to an episode.

## What the runs show
- **The bolt can be done without privileged data, by skills.** The fixed script matched the oracle, 8/8 safe, with only the work order, the tool pose and the wrist sensor, landing 15.43–15.59 N·m on a 15.5 target, about 2 s slower than the oracle (median 17.4 s against 15.2 s). Its first version scored 0/4 (3 damaged); what made the difference was following the sensed sideways force to seat (the work order's millimetre geometry is too coarse) and fitting the sensor's torque against the measured turn (not the commanded one, nor the wrist's lag).
- **Lightning lost on sequencing under the time limit, not on control.** In 5 of 8 episodes its first call was `seat` straight from the start pose, though the tool description says to approach with the ready aim first; each failed `seat` burned its full 10 s of the 30 s, and the recoveries ran out of time (torques 0.5–4.4 N·m at the limit). The two safe episodes (0 and 3) are two of the three where it approached first. It never damaged the clamp and never sent an unusable call.
- **One skill flaw it exposed:** in episode 4 `tighten_to` crawled for 15 s and stopped at 4.3 N·m. Without privilege it slows from 2 N·m of sensed torque to sample the sensor's range; a reading that high before snug makes it crawl through the run-down. The fixed script never met this.
- **On the humanoid, ordering four skills is easy for it:** 8/8, the minimal 4 calls each, short thinking. The phase skills cost about 1 s against the oracle (a held tick at each skill boundary) and once tipped an episode into a failed re-latch.

## Nemotron 3.5 Super on the bolt (viewer, 3 episodes)
Later the same day, `nemotron-3.5-super-vl` (Nemotron 3.5 Super VL 120B-A12B, served by vLLM on RTU's HPC and reached over HTTPS; quantisation and server settings not recorded here) drove the same unprivileged bolt setup in the viewer, dev episodes 0–2, the task's 30 s limit, thinking on, temperature 1.0 (top-p the server's default). Recordings: `live-runs/super-arm/` and the first attempt `live-runs/super-arm-unguided/`.
- **First attempt, stopped after 2 episodes:** it aimed straight from the start pose to 0.5 mm off the head, which clipped the head and jammed the socket askew; seat failed twice and the time ran out. The tool descriptions had never said to stand off first. Lightning's two safe report episodes and the fixed script all had.
- **With `aim` and `seat` saying to stop 50 mm out first: 3/3 safe success** (`privileged: false`), the same 6 calls each (stand off, close in, seat, tighten_to(16), unload, retract(50)), installed 15.97, 15.99, 16.06 N·m, released at 15.7, 20.9, 18.0 s. Calls took 1.0–16.6 s (99–2,529 tokens), most under 3 s.
Three episodes are not a rate, and Lightning has not been rerun with the corrected descriptions, so the two models are not compared here.

## What this does not show
- Anything about controlling a robot without skills: there, on the same bolt task, Nemotron 3 Nano and 3.5 Lightning never succeeded safely in `NOTES/REPORT.md` and `LIVE_LESSONS.md`.
- Anything about the humanoid without privileged data (impossible as the task is built).
- Rankings: 8 episodes, one seed, the dev split, one quantised model on one laptop; intervals are wide. Model sampling and GPU arithmetic are not exactly repeatable.

## Provenance
- Every run: commit `b993000` of `live-viewer` (laptop-llm + upstream PR #14 merged locally), Newton physics, RTX 4060 Laptop GPU, `solarbench_dirty: true` because the runs' own outputs were written under `NOTES/` while they ran.
- Script: `NOTES/report_runs.sh`; result files, call logs and the recorded model exchanges (requests, thinking, tool calls) under `report-runs/<run>/`, unedited apart from one change: llama-server reports its model as the GGUF's local file path, which is shortened to `~/llm/models/…` in the recorded exchanges.
- Model server: `NOTES/serve.sh` with `MODEL=…Lightning…Q4_0.gguf TOP_P=0.95 BUDGET=4096 PARALLEL=1 CTX=131072`.
- Not verified: anything beyond these 8 episodes; the skills' behaviour on the test split.
