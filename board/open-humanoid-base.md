---
id: open-humanoid-base
title: A walking humanoid under real torque limits
track: sim
milestone: open
priority: core
needs: gpu
size: large
status: todo
owner: ""
depends_on: []
touches: []
done_when:
  - "the connector task runs with a free-floating base; oracle result on held-out seeds"
---
## Why
The humanoid is fixed at the pelvis today. Site work needs it to walk, kneel and brace.

## What
- A whole-body controller for the G1 that holds the datasheet limits, integrated as a fixed layer under the policy contract.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
