---
id: sim-wire-cameras
title: Camera images in the task observations
track: sim
milestone: v1
priority: core
needs: gpu
size: small
status: todo
owner: ""
depends_on: [sim-cameras, sim-ur-connector, sim-guarded-skills]
touches:
  - "solarbench/tasks/clamp_env.py"
  - "solarbench/tasks/clamp_env_cfg.py"
  - "solarbench/tasks/plug_env.py"
  - "solarbench/tasks/plug_env_cfg.py"
done_when:
  - "tools/check.sh --gpu"
  - "an episode saved with images replays as a video"
---
## Why
Joins the camera module to the two UR tasks.

## What
- Add `images/<camera>` and the camera calibration to the bolt and connector observations, off by default.
- Check memory at the environment counts used for evaluation.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
