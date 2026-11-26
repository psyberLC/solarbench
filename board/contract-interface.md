---
id: contract-interface
title: Freeze the observation, action and timing contract
track: contract
milestone: v1
priority: core
needs: none
size: small
status: todo
owner: ""
depends_on: []
touches:
  - "docs/interface.md"
done_when:
  - "the status line of docs/interface.md reads `frozen v1`, in a pull request the maintainer approved"
---
## Why
The sim and agents tracks work in parallel against `docs/interface.md`. It must be agreed before either builds on it.

## What
- Read `docs/interface.md` against what the sim and agents items need, and correct anything that would not work.
- The maintainer changes the status line at the top to `frozen v1` and records the date.
- After the freeze, any change needs a new contract item.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
