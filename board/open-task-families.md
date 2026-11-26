---
id: open-task-families
title: More task families from the atlas
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
  - "per family: validator pass, oracle result on both backends, degenerate policies fail"
---
## Why
With the connector, bolt and door tasks, 38 of the atlas's 101 field tasks are fully covered. Filters, fuses, grease points, gauges and cleaning are untouched.

## What
- Each new family follows `docs/bringing_in_assets.md` and `CONTRIBUTING.md`, with its own oracle, audit and task card.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
