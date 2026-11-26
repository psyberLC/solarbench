---
id: eval-latency
title: 'Real-time mode: the world does not wait'
track: eval
milestone: v1
priority: core
needs: gpu
size: small
status: todo
owner: ""
depends_on: []
touches:
  - "solarbench/eval/timing.py"
  - "scripts/evaluate.py"
  - "tests/test_timing.py"
done_when:
  - "tools/check.sh"
  - "tools/check.sh --gpu  # oracle under fixed:0.5 still runs; its score is reported, not asserted"
---
## Why
A model that thinks for four seconds is a different controller from one that answers in forty milliseconds. Lockstep evaluation hides that.

## What
- `solarbench/eval/timing.py`: while a policy is thinking, the simulation advances and the robot holds its last command.
- `scripts/evaluate.py --latency lockstep | measured | fixed:<seconds>`; the mode and the per-step delays go into the result.
- Unit test with a fake environment and a slow fake policy.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
