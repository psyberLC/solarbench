---
id: assets-measure-bolt
title: Measure a real clamp bolt
track: assets
milestone: v1
priority: core
needs: bench
size: small
status: todo
owner: ""
depends_on: []
touches:
  - "assets/measurements/m8_*"
  - "solarbench/specs/params.py"
  - "ASSUMPTIONS.md"
done_when:
  - "assets/measurements/m8_clamp_torque.csv exists"
  - "spec entries change status to MEASURED"
  - "tools/check.sh --gpu"
---
## Why
The torque-angle curve of the bolt model is assumed from handbook values.

## What
- Torque wrench and angle marks on an M8 end clamp on a rail: running torque, snug point, angle from snug to 16 N·m, breakaway torque.
- Raw readings stored; spec values and ASSUMPTIONS.md updated.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
