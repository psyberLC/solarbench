---
id: open-hidden-split
title: Hidden evaluation split and runner
track: eval
milestone: open
priority: core
needs: gpu
size: large
status: todo
owner: ""
depends_on: []
touches: []
done_when:
  - "an outside policy container is evaluated end to end without network access"
---
## Why
Public seeds can be tuned against. Rankings need scenes nobody has seen, run by someone other than the entrant.

## What
- The split design in `docs/vision.md`: hidden generator settings and assets, seeds redrawn every run, sandboxed policy container.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
