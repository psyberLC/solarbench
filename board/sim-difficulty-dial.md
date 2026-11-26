---
id: sim-difficulty-dial
title: 'Difficulty dial: distance from the real specification'
track: sim
milestone: v1
priority: core
needs: gpu
size: medium
status: todo
owner: ""
depends_on: [sim-ur-connector, sim-pose-action]
touches:
  - "solarbench/tasks/difficulty.py"
  - "solarbench/tasks/clamp_env_cfg.py"
  - "solarbench/tasks/plug_env_cfg.py"
  - "scripts/build_assets.py"
  - "assets/mc4_*_c*/*"
  - "tests/test_difficulty.py"
  - "docs/tasks.md"
done_when:
  - "tools/check.sh --gpu"
  - "oracle success at dial 1.0 is unchanged from the checked-in result"
---
## Why
Success at one fixed difficulty saturates at 0% or 100%. A dial with the real value marked gives a number that keeps moving.

## What
- One scalar per task, 1.0 at the real specification: torque-window width for the bolt, radial clearance for the connector.
- `solarbench/tasks/difficulty.py` maps the scalar to task parameters. Connector variants are built from specs by `scripts/build_assets.py`.
- The dial value is written into every episode record. Relaxed levels are never reported as the task itself.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
