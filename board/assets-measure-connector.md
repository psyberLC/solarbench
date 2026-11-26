---
id: assets-measure-connector
title: Measure a real MC4 pair
track: assets
milestone: v1
priority: core
needs: bench
size: small
status: todo
owner: ""
depends_on: []
touches:
  - "assets/measurements/mc4_*"
  - "solarbench/specs/params.py"
  - "ASSUMPTIONS.md"
done_when:
  - "assets/measurements/mc4_force.csv exists with raw readings and the instrument named"
  - "the spec entries change status from ASSUMED or STAND_IN to MEASURED"
  - "tools/check.sh --gpu"
---
## Why
Mating and unmating force are the largest assumed numbers in the connector task.

## What
- Follow the protocol in `docs/bringing_in_assets.md` (force gauge, at least 10 cycles, two connector pairs).
- Store the raw readings; replace the assumed values in `solarbench/specs/params.py`; update ASSUMPTIONS.md.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
