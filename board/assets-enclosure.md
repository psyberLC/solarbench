---
id: assets-enclosure
title: Enclosure with hinged door and latch
track: assets
milestone: v1
priority: stretch
needs: cpu
size: medium
status: todo
owner: ""
depends_on: []
touches:
  - "assets/enclosure_*/*"
  - "solarbench/assets/build.py"
  - "solarbench/specs/params.py"
  - "scripts/build_assets.py"
  - "ASSUMPTIONS.md"
  - "docs/bringing_in_assets.md"
done_when:
  - "the validator passes for assets/enclosure_*/"
  - "tools/check.sh"
---
## Why
The asset for the door task, and the worked example for the asset guide.

## What
- Build it by following `docs/bringing_in_assets.md` end to end, and fix the guide wherever it was wrong or unclear.
- Passes SimReady validation; every dimension and force has a source or an ASSUMPTIONS.md entry.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
