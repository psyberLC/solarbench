# The field: robot control and its benchmarks

A map of the work this project builds on and is measured against, kept current by the board item `field-watch`. Tags: **[P]** read in a primary source, **[S]** secondary source only, **[X]** seen only in a public post by the authors. Scores are the authors' or vendors' own.

## Watch list
The entries to re-check on each pass: new versions, released weights, leaderboard changes, and new work citing them that reports results on contact, force or damage.

| Entry | Link | Why it is watched | Last checked |
|---|---|---|---|
| PEAR (reasoning model trained in simulation to drive arms) | https://arxiv.org/abs/2611.18562 | The open-weight model the first experiment uses | 2026-11-25 |
| uni-robot-agent | https://github.com/Open-RUA/uni-robot-agent | Open harness and the untrained baseline for PEAR | 2026-11-25 |
| Force2Act and Force2Act-Bench | https://arxiv.org/abs/2611.29208 | Closest benchmark: force tasks without a target window or damage score | 2026-11-25 |
| RoboColosseum | https://arxiv.org/abs/2611.02497 | Real-robot comparisons of agents and VLAs; its agent interface | 2026-11-25 |
| RoboDojo, and the audit of it | https://arxiv.org/abs/2607.04434 , https://p-b-p-b.github.io/blog/2026/what-does-robodojo-really-simulate/ | Where agents fail on contact; what a physics audit should check | 2026-11-25 |
| Astranomy on RoboLab-120 | https://research.nvidia.com/labs/srl/projects/astranomy/ | The cleanest comparison of control interfaces for one model | 2026-11-25 |
| Vals Robo-bench | https://www.vals.ai/benchmarks/robo_bench | Coding agents in simulation with force limits | 2026-11-25 |
| GR00T 2 | https://research.nvidia.com/labs/gear/gr00t-2 | Weights announced but not yet released | 2026-11-25 |
| "Post-Astra Robotics" | https://yifank.github.io/post-astra-robotics/ | Per-task failure numbers for agents on contact | 2026-11-25 |

## 1. Where things stood in November 2026
- **Reasoning models now drive robots through harnesses.** GPT-6 Astra / 6.2, Claude Opus 5.5 / Fable 5.2 and Gemini 4 are scored on robot control alongside VLAs.
- **In real-world head-to-heads, agents edge out VLAs.** RoboColosseum ran 5,699 comparisons at 124 sites: agents made more progress in 394 of 901 paired runs, VLAs in 265. No system passed 13% success in any category, and every model scored 0% on the Unitree G1 fine-tune track. [P] https://arxiv.org/abs/2611.02497
- **The interface matters as much as the model.** Astra on RoboLab-120: agentic 74.8%, direct end-effector pose 66.3%, joint targets 50.2%, B-spline 38.8%; agentic costs $36.40 per episode. [P] https://research.nvidia.com/labs/srl/projects/astranomy/
- **Contact is where agents fail.** On RoboDojo, agents score 90–96% on reasoning tasks but 0% on key insertion, 0% on the egg holder and 4% on plugging a charger; they receive no force signal, and need 8.6 min of wall time for 24.5 s of motion. [P] https://yifank.github.io/post-astra-robotics/
- **Force sensing helps more than more demonstrations.** FORCA on a UR5e: drawer opening 4/10 with camera only, 10/10 with wrist force. [P] https://josefchen.substack.com/p/agentic-robotics-flips-the-build
- **Open reasoning models can be trained to do it.** PEAR: Qwen3.8-27B trained by RL in simulation with zero demonstrations; LIBERO 74.4% (base model 1.6%), real dual-arm 18/30. Apache-2.0 code; weights on Hugging Face. [P] https://arxiv.org/abs/2611.18562 , https://github.com/mit-han-lab/pear
- **Benchmarks are being audited.** RoboDojo's configured friction never reached the engine (0.5 for every object), joint limits were ±573°, and quitting at step 0 scored 100 on 54 of 54 tasks. [P] https://p-b-p-b.github.io/blog/2026/what-does-robodojo-really-simulate/

## 2. Neighbouring benchmarks, and what each does not cover
| Benchmark | Setup | Does not cover |
|---|---|---|
| **Force2Act-Bench** (24 Nov) [P] https://arxiv.org/abs/2611.29208 | Genesis, one Flexiv arm, 5 force tasks (pivot, press-push, wipe, round plug, USB-A), 305 trials; wrist F/T at 15 Hz | No target force or window; no damage metric (force clipped at 60 N); no LLM agents evaluated; one body; no industrial tasks |
| **Vals Robo-bench** [P] https://www.vals.ai/benchmarks/robo_bench | MuJoCo, 13 Franka + 11 G1 tasks, coding agents; wrist F/T, protective stops, datasheet speed limits | No spec windows; damage only ends the episode; one seed; 21 of 24 tasks private |
| **RoboDojo** [P] https://arxiv.org/abs/2607.04434 | Isaac Sim, 42 tasks | Force. An independent audit reported physics and scoring defects (above); its authors are working on fixes |
| **RoboColosseum** [P] https://robocolosseum.ai | Real SO-101, YAM, Franka, G1; 124 sites; Rasch-scaled ranking; 10,000 free evaluation hours for academics; all rollouts released | Force and damage metrics; model rankings disagree across robots (Kendall's W 0.24) |
| **RoboLab-120 / Astranomy** [P] | One model, one robot, four interfaces | Bodies, force |

**Unmeasured by all of them** (as far as we could find):
1. Whether applied force or torque lands inside a task-specified window, with under- and over-shoot graded.
2. Damage or over-force as a scored outcome.
3. Industrial connector, fastener, cabinet and panel work.
4. A controlled body × model × interface comparison.
5. Actuator limits (payload, torque saturation) as an outcome.
6. An LLM agent on a force-instrumented benchmark.
7. An open-weight local model on contact-rich tasks.
8. Proof that the configured contact physics is what the engine actually uses.

## 3. Open-weight models that can act as the brain
| Model | What it is | Interface | Hardware needed |
|---|---|---|---|
| **Qwen3.8-27B-PEAR** [P] | Reasoning model trained in sim to drive arms | Images + arm state + embodiment prompt in; one JSON end-effector pose per round out; our IK executes | About 54 GB in BF16 [inferred]: two L40S, or quantise. 1–4 s per round |
| **Qwen3.8-27B base** in **uni-robot-agent** (MIT) [P] https://github.com/Open-RUA/uni-robot-agent | The no-training baseline for PEAR (8.06% on RoboDojo) | Tools `move`, `hold`, `capture_scene`, `finish`, or code-as-policy; any Responses-compatible endpoint; has Isaac Lab adapters | Same |
| **Qwen3.8-Flash-Next** [P] | Best published open zero-shot agent (31.39 on RoboDojo) | Same harness | 125B: several GPUs |
| **RoboJev-27B** [S] | Success grader, not an actor | Video in, verdict out | One 48 GB GPU, or quantised [not measured] |
| **Xiaomi-Robotics-1-5B**, **SANA-Robot 4.5B** [S] | Small VLA / world-action model | Action chunks; needs demos and post-training | One GPU |
| **GR00T N1.7** [P] | Open VLA with a G1 tag | Policy server; fine-tune for new bodies | 16 GB for inference |
| **GR00T 2** [P] | Announced 10 Nov; G1, Franka, YAM | — | Not stated; weights not released yet |
| **Mistral Robostral Navigate** [S] | 8B, navigation only | Image point + heading | Not stated. No manipulation results found |

**Speed vs thinking is unsettled.** PEAR at low reasoning effort takes 1.1 s per round instead of 4.3 s, and LIBERO success falls from 74.4% to 21.9%. Whether a small fast model beats a large slow one on contact is an open question our latency axis can answer.

## 4. Other things worth knowing
- **Simulators:** MuJoCo 4 added speculative contacts [X]; Skild open-sourced the Steel solver [X]; NVIDIA opened SimReady Central with 3,500+ free assets [X], a possible home for the solar assets.
- **Force-aware learning:** FLoRe (humanoid force-reactive loco-manipulation), OpenTac and LingBot-Touch (tactile), and joint-encoder drift as a contact sensor [all X].
- **Did the robot skill emerge?** One probe suggests frontier models were trained on robotics data rather than acquiring the skill unprompted [S].

## Changes
Dated notes from each pass, newest last.
- 2026-11-25: first version.
