---
id: sim-door-task
title: Enclosure door with a latch
track: sim
milestone: v1
priority: stretch
needs: gpu
size: large
status: todo
owner: ""
depends_on: [assets-enclosure, sim-obs-channels]
touches:
  - "solarbench/tasks/door_env.py"
  - "solarbench/tasks/door_env_cfg.py"
  - "solarbench/oracle/door_oracle.py"
  - "solarbench/oracle/__init__.py"
  - "solarbench/tasks/__init__.py"
  - "ASSUMPTIONS.md"
  - "docs/tasks.md"
done_when:
  - "tools/check.sh --gpu"
  - "held-out oracle result on both backends"
---
## Why
Opening an enclosure door is the most common contact skill in the task atlas (24 tasks), and nothing in the benchmark covers it.

## What
- A hinged door with a quarter-turn latch on a combiner-box-sized enclosure, as a task for the UR arm.
- Success: latch released and door open beyond a set angle without exceeding hinge or handle load limits.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
