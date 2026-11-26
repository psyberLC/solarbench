---
id: open-fleet-interface
title: Run unchanged on shared real-robot evaluation fleets
track: agents
milestone: open
priority: core
needs: cpu
size: medium
status: todo
owner: ""
depends_on: []
touches: []
done_when:
  - "one configuration runs in simulation here and through the fleet interface without edits"
---
## Why
Public fleets evaluate agents through a fixed tool interface. Matching it lets a configuration tested here run there.

## What
- An adapter between the policy contract and the fleet's agent interface (images, labelled proprioception, one tool call per turn).

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
