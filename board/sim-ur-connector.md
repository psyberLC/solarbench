---
id: sim-ur-connector
title: Connector task on the UR arm
track: sim
milestone: v1
priority: core
needs: gpu
size: large
status: todo
owner: ""
depends_on: [sim-obs-channels]
touches:
  - "solarbench/tasks/plug_env.py"
  - "solarbench/tasks/plug_env_cfg.py"
  - "solarbench/oracle/plug_oracle.py"
  - "solarbench/oracle/__init__.py"
  - "solarbench/tasks/__init__.py"
  - "solarbench/tasks/robots.py"
  - "tests/test_plug.py"
  - "ASSUMPTIONS.md"
  - "docs/tasks.md"
  - "results/SolarBench-T2-*UR*/*"
done_when:
  - "tools/check.sh --gpu"
  - "results/<task>/oracle_test_newton.json and oracle_test_ovphysx.json exist and validate"
---
## Why
The first experiment uses one body for both contact tasks. The connector task exists only for the humanoid hand.

## What
- New task: unmate and re-mate an MC4 pair with the UR arm. One connector half is held in a tool fixture, so the task is the contact, not the grasp. Say so in ASSUMPTIONS.md.
- Reuse the latch model (`solarbench/tasks/latch.py`), the MC4 assets and `channels.py`.
- Oracle in `solarbench/oracle/plug_oracle.py`; held-out oracle result on both physics backends.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
