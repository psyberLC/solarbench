---
id: sim-pose-action
title: 'Action mode: absolute end-effector pose per step'
track: sim
milestone: v1
priority: core
needs: gpu
size: medium
status: done
owner: psyberLC
depends_on: [sim-obs-channels]
touches:
  - "solarbench/tasks/actions.py"
  - "solarbench/tasks/clamp_env.py"
  - "solarbench/tasks/clamp_env_cfg.py"
  - "solarbench/tasks/__init__.py"
  - "tests/test_actions.py"
  - "docs/tasks.md"
  - "scripts/evaluate.py"
  - "solarbench/agents/__init__.py"
done_when:
  - "tools/check.sh --gpu"
  - ".venv/bin/python -m pytest -q tests/test_actions.py"
---
## Why
The second rung (R2). Reasoning models emit one target pose per round, not small deltas at 30 Hz.

## What
- `solarbench/tasks/actions.py`: run a `TOOL_POSE` record of `docs/interface.md` as rate-limited steps for the existing IK, under the same joint torque and velocity limits, and write its completion when it arrives, stalls or times out.
- Profile R2 on the bolt task under a task id of its own; existing ids keep their behaviour.
- The oracle, replayed as `TOOL_POSE` records, still succeeds.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
- 2026-11-26, claude-code (for psyberLC): done on the fork `psyberLC/solarbench` (branch `laptop-llm`); not proposed upstream. New task id `SolarBench-T3-ClampTighten-UR16e-R2-v0` (`ClampPoseEnv`); the `-v0` ids are unchanged. `solarbench/tasks/actions.py` holds one `TOOL_POSE` per environment and turns it into the R1 step the task already runs: the commanded pose moves toward the target by at most R1's limits per tick, through the same IK and joint limits. It completes the record as arrived, stalled or timed out, and `DONE` ends the episode. Thresholds are in ASSUMPTIONS M13. The file is pure torch so the CPU-only CI can test it.
  - `touches` grew by `scripts/evaluate.py` and `solarbench/agents/__init__.py`. Under R2 the evaluator's "no command" is a buffer of `NOP` records. The evaluator tells a task the selection when the task asks for it (`select`), because a completion reports force only to a policy that selected `wrench` (`docs/interface.md`, section 5). The oracle, on a task that takes no R1 steps, sends each step as a one-tick `TOOL_POSE` to where that step puts the tool.
  - Oracle replayed as `TOOL_POSE` records (dev, 8 episodes, 4 envs, Newton, RTX 4060 Laptop): safe success 8/8 (95% CI 67.6%–100%), damage 0/8. Its installed torques per episode are within 0.04 N·m of the R1 oracle's on the same seeds (16.08, 16.07, 15.98, 16.05, 15.99, 16.08, 16.06, 16.06 against 16.05, 16.04, 15.97, 16.06, 15.99, 16.04, 16.09, 16.06 N·m). Zero policy on the R2 id: 0/8. The run was made with the model server resident on the same GPU.
  - Free-space waypoints (`NOTES/probes/probe_r2.py` on `laptop-llm`): moves of 5 cm, and turns of 0.5 rad about the tool axis, arrive within 0.5 mm and 0.005 rad in 22–26 ticks.
  - `tools/check.sh --gpu`: bolt oracle 8/8, zero 0/8; connector oracle 8/8, zero 0/8; "all checks passed". These are read from the result files, because the log file was overwritten partway, as in `contract-harness-catalogue`. `tools/check.sh` rerun on its own: lint clean, 80 passed, board ok, all checks passed. `.venv/bin/python -m pytest -q tests/test_actions.py`: 8 passed.
  - Not verified: the replay sends a waypoint every tick, so it shows that the pose path, the wake rule and the records reproduce the R1 trajectory, not that coarse waypoints can do the task. No R2 run on PhysX. No loosening R2 id. The bolt card's line "The evaluator does not hand these to a policy yet" is out of date since `contract-harness-catalogue`; `docs/tasks.md` is append-only, so it is left for its owner.
