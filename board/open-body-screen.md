---
id: open-body-screen
title: 'Body screen: which robots can physically do each task'
track: eval
milestone: open
priority: core
needs: cpu
size: large
status: todo
owner: ""
depends_on: []
touches: []
done_when:
  - "a script regenerates the table from robot descriptions and task specs for at least ten bodies"
---
## Why
Whether a body can reach under a 0.6 m table, hold 16 N·m at the wrist or carry its share of a 30 kg module needs no policy to answer.

## What
- For each openly described robot: reachability of the task poses, torque margin along the oracle trajectory, payload margin.
- A table of bodies by tasks with pass, marginal or fail and the limiting joint.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
