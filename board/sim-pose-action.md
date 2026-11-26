---
id: sim-pose-action
title: 'Action mode: absolute end-effector pose per step'
track: sim
milestone: v1
priority: core
needs: gpu
size: medium
status: todo
owner: ""
depends_on: [sim-obs-channels]
touches:
  - "solarbench/tasks/actions.py"
  - "solarbench/tasks/clamp_env.py"
  - "solarbench/tasks/clamp_env_cfg.py"
  - "solarbench/tasks/__init__.py"
  - "tests/test_actions.py"
  - "docs/tasks.md"
done_when:
  - "tools/check.sh --gpu"
  - ".venv/bin/python -m pytest -q tests/test_actions.py"
---
## Why
The second rung (R2). Reasoning models emit one target pose per round, not small deltas at 30 Hz.

## What
- `solarbench/tasks/actions.py`: turn a base-frame pose target into rate-limited steps for the existing IK, under the same joint torque and velocity limits.
- Config switch `action_mode` on the bolt task: `ee_delta` (today) or `ee_pose`. Task ids for the new mode get their own name; existing ids keep their behaviour.
- The oracle, replayed through `ee_pose`, still succeeds.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
