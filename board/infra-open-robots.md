---
id: infra-open-robots
title: Robot models built from openly licensed descriptions
track: infra
milestone: v1
priority: core
needs: gpu
size: medium
status: todo
owner: ""
depends_on: []
touches:
  - "solarbench/tasks/robots.py"
  - "solarbench/assets/robots.py"
  - "assets/robots/*"
  - "assets/LICENSES.md"
  - "scripts/build_assets.py"
  - "ASSUMPTIONS.md"
done_when:
  - "tools/check.sh --gpu with the network disabled"
  - "assets/LICENSES.md lists every third-party source"
---
## Why
Robot models are fetched from a vendor asset server at run time. That needs internet and forbids redistribution.

## What
- Build the G1, the UR arm and the Husky from their BSD-licensed URDF or MJCF sources into `assets/`, with the datasheet limits applied.
- A licence manifest lists every third-party file and its terms. No task downloads anything at run time.
- Oracle results are unchanged within intervals.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
