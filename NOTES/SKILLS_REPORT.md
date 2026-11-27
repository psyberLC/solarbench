# Skills for a model: oracle vs fixed script vs Nemotron 3.5 Super and Lightning

Runs of 2026-11-27 by claude-code (for psyberLC), the simulation always on the laptop (Super served from RTU's HPC), on the fork's `live-viewer` branch. Exploratory: these are not benchmark results, they are not in `results/`, and the setups below are easier than the benchmark's tasks. How the setups came about is in [LIVE_LESSONS.md](LIVE_LESSONS.md).

## 32 episodes: oracle vs fixed script vs Nemotron 3.5 Super
Run 2026-11-27, 16:56–18:39, with the same setup as the 8-episode comparison below, on dev episodes 0–31. The model is `nemotron-3.5-super-vl` (Nemotron 3.5 Super VL 120B-A12B). It was served by vLLM on RTU's HPC and reached over HTTPS through a Cloudflare tunnel. The server's quantisation and settings are not recorded here. Thinking was on, temperature 1.0, top-p the server's default. Bolt: unprivileged skills. Connector: privileged phase skills, the only kind the task allows. The code was commit `3ace4f2`; the Super connector run was repeated at `e41a5ba` (below). Script: `OUT=NOTES/report-runs-32 EPISODES=32 MODEL=nemotron-3.5-super-vl UPSTREAM=<server> HOST=remote TEMP=1.0 NOTES/report_runs.sh`. Full tables and per-episode outcomes: [report-runs-32/tables.md](report-runs-32/tables.md).

| | Bolt (T3, R2): safe success | median release, s | Connector (T2): safe success | median release, s |
|---|---|---|---|---|
| oracle (privileged) | 30/32 (94%, 80–98) | 15.0 | 32/32 (100%, 89–100) | 5.1 |
| skills, fixed sequence | 32/32 (100%, 89–100), unprivileged | 18.0 | 29/31 valid (94%, 79–98), privileged | 5.3 |
| skills, Nemotron 3.5 Super | 26/32 (81%, 65–91), unprivileged | 16.9 | 28/31 valid (90%, 75–97), privileged | 5.3 |

No run damaged anything. Every bolt episode was valid. On the connector, the script run and the Super run each lost one episode to a numerical failure (episodes 3 and 14), which the evaluator excludes.

**Bolt.**
- **Super's safe episodes landed 15.47–16.11 N·m.** That is its own choice of 16 N·m, inside the 14–18 window. In all but two of the 26 it used the minimal 6 calls (stand off, close in, `seat`, `tighten_to`, `unload`, `retract`); the other two took 7.
- **Model use.** 215 calls, median 209 tokens and 2.3 s per call, 27.2 min of model time in all. Two calls ran into the 12,288-token cap without a tool call (episodes 4 and 29); the adapter asked again.
- **The losses come from one recovery choice.** On 6 bolts (episodes 9, 13, 16, 17, 18, 29 in the script run) `seat` ends "not seated after 10 s". The socket is on the head but has not dropped over the flats. The fixed script ignores that and calls `tighten_to`, whose turning under a press drops the socket onto the flats. It won all 6, engaging late (20.6–27.2 s) and releasing with as little as 2 s to spare.
  - **What Super did.** Its `seat` failed on 6 bolts (9, 16, 17, 18, 28, 29). On episode 28 it re-aimed once and then called `tighten_to`, and won. On the other 5 it believed the message: it re-aimed, rotated the socket or called `seat` again. All 5 ran out of time. On 9, 16, 17 and 18 no stage was reached in time; on 29 it seated at 24 s and timed out tightening at 11 N·m.
  - **The skill shares the blame.** `seat` reports failure where `tighten_to` would succeed, and nothing in its description says so. The script's order works by accident, not by design.
- **Episode 8 was lost after the bolt was in spec.** Super reached 15.9 N·m (in spec at 15.6 s) and unloaded. `retract` then twice ended "the socket is still on the head", a failure the script never met. Super then aimed with the socket rotated while it was still on the head, which turned the bolt back. It ended at 1.0 N·m installed, never released. This is the one case where a model's recovery undid finished work. No damage is scored for loosening.
- **The oracle lost 2 episodes, 13 and 18.** Both are hard bolts for the skills too. In each it installed 16.09 N·m, inside the window, and ran the full 30 s without the evaluator ever counting the `engaged` stage. That stage needs the tool within depth, lateral and angle limits of the head, and the oracle never moved on to release. This was not investigated. It looks like the oracle turning the bolt from just outside the geometric engagement limits, and it may matter upstream; it is an observation from one run, not a confirmed defect.

**Connector** (before the fix in the next section).
- **Super ordered the four steps minimally in 28 of 32 episodes.** That is grasp, unplug, plug_in, release. It used 135 calls, median 124 tokens per call, and 3.3 min of model time; every call was a usable tool call. One 429 from the server was waited through.
- **Every failure of the script and of Super is the same `plug_in` flaw.** The skill ends "finished" with the latch not engaged. That happened to the script on episodes 11 and 21, and to Super on 5, 10 and 25: different episodes, so it is not tied to a connector. On Super's three the plug was 17–29 mm off the sleeve's axis; the script's log does not record the offset.
  - **What the script did.** It released anyway and failed.
  - **What Super did.** It saw the latch was not engaged and called `plug_in` again, twice, or `grasp`. From the misaligned pose, the repeated skill lost the grip and pulled the housing away (to 438 mm out on episode 5), so the retries never helped.
  - **The oracle never met this.** It runs the same phases without the held tick that the phase skills add at each skill boundary (see the 8-episode notes below). That tick is the likely cause, but this is not verified.
- **This tests sequencing, not control,** because the skills run the oracle's own controller. Super's 28/31 and the script's 29/31 are not distinguishable at this sample size.

**What changed during these runs.** The first Super connector run stopped after 16 episodes: the HPC server answered `429 Too Many Requests` and the phases adapter had no retry. Commit `e41a5ba` gives both adapters one request function that waits on 429 (the server's `Retry-After`, else 30 s, at most ten times). The run was then repeated from episode 0. The stopped run's partial logs are not kept. Nothing else changed between runs.

## The three problems these runs showed, and what was done
Investigated the same day with probes that run the evaluator in-process and log the simulator's state tick by tick (`NOTES/probes/phases_probe.py`, `NOTES/probes/bolt_engage_probe.py`). The probes' own outputs were scratch files and are not kept; the numbers below are read from them.

### 1. Connector: a held tick between skills jammed some insertions (fixed, rerun)
- **What happened.** The phase skills held the robot still for one tick at each skill boundary while the model was asked. With a fixed plan on 64 dev episodes and 16 environments, that version got 63/64. Every insertion that failed began 0.75–0.8 mm off the sleeve's axis and caught the mouth's rim. The oracle's realignment moves on the first tick the offset is under 0.8 mm, and the offset swings between about 0.1 and 0.9 mm.
- **The hold, not the offset, is the cause.** The same plan with no hold, which is exactly the oracle, got 64/64, and its insertions from 0.78–0.8 mm off all latched.
- **The fix** (commit `1188a14`). The model is asked on the tick a skill ends; the simulation waits for it. If it picks the step the oracle was already starting, that tick runs the oracle's action, so the natural order moves exactly as the oracle does. Any other choice holds the robot for that tick, so the model gets no motion it did not choose. `plug_in` now says "ended without the latch engaging" instead of "finished". With the fix, the fixed plan got 64/64.
- **Rerun**, 32 dev episodes, one environment, the same setup as above. Tables: [report-runs-32-t2fix/tables.md](report-runs-32-t2fix/tables.md).

| Connector (T2), safe success | before the fix | after the fix | median release, s (after) |
|---|---|---|---|
| oracle (privileged) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 5.1 |
| phase skills, fixed sequence | 29/31 valid (94%, 79–98) | 31/31 valid (100%, 89–100) | 5.1 |
| phase skills, Nemotron 3.5 Super | 28/31 valid (90%, 75–97) | **32/32 (100%, 89–100)** | 5.1 |

Super used the minimal 4 calls in every episode: 128 calls, median 106 tokens, 2.1 min of model time. Each script run lost one episode to a numerical failure, which the evaluator excludes. The phase skills no longer cost time against the oracle.

### 2. Bolt: `seat` failed on a wedged socket and did not say so (fixed, checked with the script, Super not rerun)
- **What happens.** On some bolts the socket comes down onto the hex only 1.9–2.2 mm (2.5 mm counts as seated; when properly seated it sits at about 5 mm). There it wedges on the chamfered corners and turns the bolt from that position. In the oracle runs it turned the bolt for about 7 of its 10 seating seconds, at a steady 0.7–1.0 N·m: the bolt's running torque, under the 2 N·m "corner caught" guard.
- **Pressing harder does not seat it.** The oracle's 7 mm press while tightening left it at 2.2 mm. In the skill runs, `tighten_to`, with its firmer press and its following of the sensed sideways force, finished seating every such socket.
- **The fix** (commits `85b526d`, `69eee67`). Every successful seat in the script runs took 3.9 s or less, that is 56 degrees of searching, less than the hex's 60-degree period. So `seat` now gives up once it has searched 75 degrees with the socket on the head. It says how far on the socket is, says it is likely wedged when that is 1.5 mm or more, and says that `tighten_to` can finish seating it. Its description says the same.
- **Check.** The fixed script, rerun on the same 32 episodes at `85b526d` (before the wording change): **32/32 safe** (100%, 89–100), installed 14.63–15.65 N·m. The new message fired on 5 bolts (9, 16, 17, 18, 29). Bolts that had seated late before released sooner: episodes 9, 13, 16, 17 and 18 by 2.6–4.5 s, episode 29 by 1.0 s. The median release fell from 18.0 to 17.5 s. Result: [report-runs-seatcheck/](report-runs-seatcheck/).
- **Super rerun, stopped at episode 8.** Same setup as the 32-episode run, commit `05a7a14`. The rule was that the run stops as soon as an earlier failure repeats. Logs, with no result file because the run was stopped: [report-runs-32-seatfix/](report-runs-32-seatfix/).
  - **Episodes 0–7:** all on the clean 6-call path, tightened to 15.6–16.0 N·m.
  - **Episode 8:** failed as before. `tighten_to` reached its 15 s limit at 15.87 N·m. After `unload`, `retract` twice ended with the socket jammed on the head, pressing about 131 N into it. An aim and a third `retract` ran out the time without a release.
  - **Where it was stopped:** during episode 9, the first of the wedged bolts. So the `seat` fix is still **untested with a model**.
  - **Super's bolt rate stays the 32-episode run's 26/32 (81%, 65–91).**
- **Not addressed by any fix:** the episode-8 failure. `tighten_to` ran slowly to its time limit and the socket then stuck on the flats. The same thing happens on the same bolt in both runs, so it is not chance.

### 3. Bolt oracle: its two losses are the same wedge (reported, not changed)
- **What happened.** Episodes 13 and 18, the oracle's two losses, are wedged sockets. The oracle turned each bolt to 16.09 N·m from 1.9–2.2 mm on and waited for an engagement that never came. The evaluator is right not to count a socket 2 mm onto the head as engaged, so the check stays as it is.
- **Only when episodes run back to back.** The failure reproduced in all three one-environment runs (17/19 twice, 30/32). With 16 environments the oracle got 32/32, including 13 and 18, with the socket about 5 mm on, 0.1 mm off the axis and 2° of tilt whenever the bolt turned.
- **Unexplained.** Why running episodes one after another on one environment changes the outcome is not known. A probe showed the arm's target starts each episode on the tool, so it is not a stale target.
- **For the maintainer, not fixed here.** The oracle and the evaluator are upstream code. Two upstream questions: whether the oracle should detect a socket that turns the bolt without seating, and why one-environment runs differ.

---

## Earlier: 8 episodes with Nemotron 3.5 Lightning on the laptop

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

## Nemotron 3.5 Super on the humanoid (viewer, 3 episodes)
The same endpoint drove the connector task's phase skills (privileged by necessity, as above), dev episodes 0–2, temperature 1.0: **3/3 safe success**, the minimal 4 calls each (grasp, unplug, plug_in, release), 51–270 tokens and 0.7–1.7 s per call, released at 7.0, 7.0 and 5.1 s. Recording: `live-runs/super-humanoid/`. As with Lightning, this tests ordering four named steps, which both models do without error.

## What this does not show
- Anything about controlling a robot without skills: there, on the same bolt task, Nemotron 3 Nano and 3.5 Lightning never succeeded safely in `NOTES/REPORT.md` and `LIVE_LESSONS.md`.
- Anything about the humanoid without privileged data (impossible as the task is built).
- Rankings: 32 (or 8) episodes, one seed, the dev split, models not pre-registered; intervals are wide. Model sampling and GPU arithmetic are not exactly repeatable, and Super and Lightning ran on different tool descriptions (the 50 mm stand-off came after the Lightning runs), so the two models are not compared.

## Provenance
- Every run: commit `b993000` of `live-viewer` (laptop-llm + upstream PR #14 merged locally), Newton physics, RTX 4060 Laptop GPU, `solarbench_dirty: true` because the runs' own outputs were written under `NOTES/` while they ran.
- Script: `NOTES/report_runs.sh`; result files, call logs and the recorded model exchanges (requests, thinking, tool calls) under `report-runs/<run>/`, unedited apart from one change: llama-server reports its model as the GGUF's local file path, which is shortened to `~/llm/models/…` in the recorded exchanges.
- Model server: `NOTES/serve.sh` with `MODEL=…Lightning…Q4_0.gguf TOP_P=0.95 BUDGET=4096 PARALLEL=1 CTX=131072`.
- Not verified: anything beyond these 8 episodes; the skills' behaviour on the test split.
