---
id: deps-watch
title: Watch the simulator stack for releases that matter
track: infra
milestone: ongoing
priority: core
needs: none
size: small
repeat: monthly
status: todo
owner: ""
depends_on: []
touches:
  - "board/*.md"
done_when:
  - "this item's log has a dated entry naming the versions read and what was found"
  - "a new item exists for any change to contact, solver or actuator defaults that could move a result"
---
## Why
Results depend on solver and contact defaults. A silent change upstream can move them.

## What
- Read the release notes of Isaac Lab, Newton, Warp, MuJoCo-Warp, OvPhysX and OVRTX since the last entry in this log (the first pass starts from the versions pinned in `uv.lock`). Note anything touching contact, friction, solver settings, actuators or rendering.
- Do not change pinned versions here. If an upgrade looks worthwhile or risky, write an item that says what to test.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
