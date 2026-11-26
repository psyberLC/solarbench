---
id: atlas-coverage
title: 'Coverage figure: which skills unlock which tasks'
track: atlas
milestone: v1
priority: core
needs: cpu
size: small
status: todo
owner: ""
depends_on: []
touches:
  - "atlas/coverage.py"
  - "atlas/coverage.svg"
  - "atlas/README.md"
  - "tests/test_atlas.py"
done_when:
  - ".venv/bin/python atlas/coverage.py --plot  # writes atlas/coverage.svg"
---
## Why
Shows why these benchmark tasks were chosen, and what share of field work each physical skill opens up.

## What
- `atlas/coverage.py --plot` draws tasks unlocked as skills are added and writes `atlas/coverage.svg`. Use matplotlib, which the simulator environment already has, imported only under `--plot`.
- Mark the skills the benchmark has a task for: `plug-unplug-connector` and `torque-fastener` today; `open-door` is on the board.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
