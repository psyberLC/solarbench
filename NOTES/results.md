# Results of the laptop runs

Written by `NOTES/analyze.py` from the result files and call logs in `NOTES/runs/`. Task `SolarBench-T3-ClampTighten-UR16e-R2-v0`, dev split, Newton, lockstep. Rates are k/n with the 95% Wilson interval; means carry a 95% bootstrap interval.

## Outcomes

| Run | Policy | Safe success | Damage | Engaged | Snug | In spec | Released | Furthest stage, mean |
|---|---|---|---|---|---|---|---|---|
| Floor: `zero` | `zero`… | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0.00 (0.00–0.00) of 4 |
| Ceiling: `oracle` replayed as TOOL_POSE | `oracle`… | 16/16 (100%; 81–100%) | 0/16 (0%; 0–19%) | 16/16 (100%; 81–100%) | 16/16 (100%; 81–100%) | 16/16 (100%; 81–100%) | 16/16 (100%; 81–100%) | 4.00 (4.00–4.00) of 4 |
| Model, force off, reasoning on | `endpoint:NVIDIA-Nemotron-3-Nano-30B-A3B-Q4_K_M`… | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0.00 (0.00–0.00) of 4 |
| Model, force on, reasoning on | `endpoint:NVIDIA-Nemotron-3-Nano-30B-A3B-Q4_K_M`… | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0/16 (0%; 0–19%) | 0.00 (0.00–0.00) of 4 |
| Speed probe: force on, reasoning off | `endpoint:NVIDIA-Nemotron-3-Nano-30B-A3B-Q4_K_M`… | 0/8 (0%; 0–32%) | 0/8 (0%; 0–32%) | 0/8 (0%; 0–32%) | 0/8 (0%; 0–32%) | 0/8 (0%; 0–32%) | 0/8 (0%; 0–32%) | 0.00 (0.00–0.00) of 4 |

Simulator errors: floor 0%, ceiling 0%, model-force-off 0%, model-force-on 0%, speed-probe 0%

## Model calls

A round is one command asked for: one call, or two when the first reply could not be read.

| Run | Calls | Rounds | Rounds per episode, mean | Wall per round, s: median (p90) | Tokens read per call, mean (cached) | Tokens written per call, mean (max) | Unreadable calls | Rounds with no command | Cut off at max_tokens | Calls writing ≥ 2,048 tokens | Episodes hit the round cap | Episodes per hour |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Model, force off, reasoning on | 139 | 139 | 7.0 | 63.7 (84.2) | 2523 (2190) | 2038 (2138) | 0/139 (0%; 0–3%) | 0/139 (0%; 0–3%) | 0 | 126/139 (91%; 85–94%) | 2 of 20 | 6.3 |
| Model, force on, reasoning on | 214 | 214 | 10.7 | 63.4 (70.8) | 3840 (3422) | 2089 (2124) | 0/214 (0%; 0–2%) | 0/214 (0%; 0–2%) | 0 | 209/214 (98%; 95–99%) | 5 of 20 | 4.0 |
| Speed probe: force on, reasoning off | 160 | 160 | 20.0 | 3.3 (6.8) | 4747 (4428) | 57 (57) | 0/160 (0%; 0–2%) | 0/160 (0%; 0–2%) | 0 | 0/160 (0%; 0–2%) | 8 of 8 | 21.2 |

Tokens written include the thinking. The server cut thinking at 2,048 tokens (`--reasoning-budget`); a call that wrote 2,048 or more almost certainly reached that cut, since the answer itself is about 60 tokens.

Episodes per hour counts the episodes in the result over the run's whole wall time, start-up included. Calls and rounds include episodes that were still running when the result's episodes were complete; those episodes are not in the result.

## What the model commanded

Over the episodes in each result. The socket seats only with its axis within 6° of the bolt's.

| Run | Poses | Socket axis within 6° of pointing into the head | Within 15° | Bolt axis written as the quaternion (w = 0) | Median socket-axis error, deg | Median distance to the head top, mm | DONE |
|---|---|---|---|---|---|---|---|
| Model, force off, reasoning on | 115 | 0 | 0 | 22/115 (19%; 13–27%) | 160 | 8.3 | 14 |
| Model, force on, reasoning on | 185 | 1 | 1 | 62/185 (34%; 27–41%) | 160 | 12.5 | 10 |
| Speed probe: force on, reasoning off | 160 | 0 | 0 | 160/160 (100%; 98–100%) | 160 | 0.0 | 0 |

## Failure labels

One label per failed episode, assigned in this order: damage → over-force; no reply in the episode could be read → malformed output; never engaged → no contact if some command put the socket face within 10 mm of the head top with the socket axis within 15° of pointing into the head, else wrong target; engaged but never snug → lost contact; snug but never in the window → under-force; in the window but never withdrawn → time out.

| Run | Failed | Labels |
|---|---|---|
| Model, force off, reasoning on | 16 | wrong target: 16 |
| Model, force on, reasoning on | 16 | wrong target: 15, no contact: 1 |
| Speed probe: force on, reasoning off | 8 | wrong target: 8 |

### Per episode

| Run | Episode | Label | Furthest stage | Calls | Unreadable | Nearest aim to head top, mm | Best socket-axis error, deg | Poses aimed at the bolt | DONE sent | Ended | Installed torque, N·m |
|---|---|---|---|---|---|---|---|---|---|---|---|
| model-force-off | 0 | wrong target | 0 | 4 | 0 | 2.5 | 49 | 0 | 1 | 4.3 s | 0.95 |
| model-force-off | 1 | wrong target | 0 | 4 | 0 | 2.5 | 110 | 0 | 1 | 3.1 s | 1.12 |
| model-force-off | 2 | wrong target | 0 | 6 | 0 | 0.0 | 160 | 0 | 1 | 9.9 s | 0.56 |
| model-force-off | 3 | wrong target | 0 | 8 | 0 | 7.3 | 136 | 0 | 1 | 9.8 s | 1.13 |
| model-force-off | 4 | wrong target | 0 | 4 | 0 | 2.4 | 90 | 0 | 1 | 5.6 s | 1.12 |
| model-force-off | 5 | wrong target | 0 | 6 | 0 | 0.5 | 152 | 0 | 1 | 9.6 s | 0.77 |
| model-force-off | 6 | wrong target | 0 | 12 | 0 | 0.0 | 160 | 0 | 1 | 17.9 s | 0.79 |
| model-force-off | 7 | wrong target | 0 | 7 | 0 | 2.5 | 160 | 0 | 1 | 6.1 s | 0.53 |
| model-force-off | 8 | wrong target | 0 | 9 | 0 | 0.0 | 79 | 0 | 1 | 8.0 s | 1.03 |
| model-force-off | 9 | wrong target | 0 | 20 | 0 | 2.7 | 160 | 0 | 0 | time limit | 0.90 |
| model-force-off | 10 | wrong target | 0 | 20 | 0 | 5.9 | 83 | 0 | 0 | time limit | 0.85 |
| model-force-off | 11 | wrong target | 0 | 7 | 0 | 10.2 | 160 | 0 | 1 | 12.0 s | 0.86 |
| model-force-off | 12 | wrong target | 0 | 4 | 0 | 97.5 | 160 | 0 | 1 | 4.5 s | 0.80 |
| model-force-off | 13 | wrong target | 0 | 4 | 0 | 2.5 | 139 | 0 | 1 | 4.9 s | 0.90 |
| model-force-off | 14 | wrong target | 0 | 8 | 0 | 2.5 | 23 | 0 | 1 | 14.0 s | 0.89 |
| model-force-off | 15 | wrong target | 0 | 6 | 0 | 2.5 | 160 | 0 | 1 | 5.6 s | 0.94 |
| model-force-on | 0 | wrong target | 0 | 4 | 0 | 2.5 | 160 | 0 | 1 | 5.7 s | 0.95 |
| model-force-on | 1 | wrong target | 0 | 5 | 0 | 0.0 | 91 | 0 | 1 | 5.9 s | 1.12 |
| model-force-on | 2 | wrong target | 0 | 6 | 0 | 0.0 | 160 | 0 | 1 | 10.4 s | 0.56 |
| model-force-on | 3 | no contact | 0 | 20 | 0 | 0.0 | 0 | 1 | 0 | time limit | 1.13 |
| model-force-on | 4 | wrong target | 0 | 19 | 0 | 5.1 | 136 | 0 | 0 | time limit | 1.12 |
| model-force-on | 5 | wrong target | 0 | 20 | 0 | 0.5 | 20 | 0 | 0 | time limit | 0.77 |
| model-force-on | 6 | wrong target | 0 | 5 | 0 | 0.0 | 44 | 0 | 1 | 10.1 s | 0.79 |
| model-force-on | 7 | wrong target | 0 | 9 | 0 | 2.5 | 160 | 0 | 1 | 8.7 s | 0.53 |
| model-force-on | 8 | wrong target | 0 | 20 | 0 | 2.2 | 180 | 0 | 0 | time limit | 1.03 |
| model-force-on | 9 | wrong target | 0 | 20 | 0 | 6.0 | 160 | 0 | 0 | time limit | 0.90 |
| model-force-on | 10 | wrong target | 0 | 20 | 0 | 5.2 | 159 | 0 | 0 | time limit | 0.85 |
| model-force-on | 11 | wrong target | 0 | 7 | 0 | 5.1 | 90 | 0 | 1 | 8.5 s | 0.86 |
| model-force-on | 12 | wrong target | 0 | 4 | 0 | 2.5 | 73 | 0 | 1 | 3.0 s | 0.80 |
| model-force-on | 13 | wrong target | 0 | 7 | 0 | 0.0 | 160 | 0 | 1 | 6.4 s | 0.90 |
| model-force-on | 14 | wrong target | 0 | 18 | 0 | 2.5 | 159 | 0 | 1 | 19.4 s | 0.89 |
| model-force-on | 15 | wrong target | 0 | 11 | 0 | 2.5 | 148 | 0 | 1 | 7.0 s | 0.94 |
| speed-probe | 0 | wrong target | 0 | 20 | 0 | 0.0 | 160 | 0 | 0 | time limit | 0.95 |
| speed-probe | 1 | wrong target | 0 | 20 | 0 | 0.0 | 160 | 0 | 0 | time limit | 1.12 |
| speed-probe | 2 | wrong target | 0 | 20 | 0 | 0.0 | 160 | 0 | 0 | time limit | 0.56 |
| speed-probe | 3 | wrong target | 0 | 20 | 0 | 0.0 | 160 | 0 | 0 | time limit | 1.13 |
| speed-probe | 4 | wrong target | 0 | 20 | 0 | 0.0 | 160 | 0 | 0 | time limit | 1.12 |
| speed-probe | 5 | wrong target | 0 | 20 | 0 | 0.0 | 160 | 0 | 0 | time limit | 0.77 |
| speed-probe | 6 | wrong target | 0 | 20 | 0 | 0.0 | 160 | 0 | 0 | time limit | 0.79 |
| speed-probe | 7 | wrong target | 0 | 20 | 0 | 0.0 | 160 | 0 | 0 | time limit | 0.53 |
