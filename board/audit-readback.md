---
id: audit-readback
title: 'Physics self-audit: read the engine back'
track: audit
milestone: v1
priority: core
needs: gpu
size: medium
status: todo
owner: ""
depends_on: []
touches:
  - "solarbench/audit/*"
  - "scripts/audit.py"
  - "tools/check.sh"
done_when:
  - ".venv/bin/python scripts/audit.py --all  # exits 0"
  - ".venv/bin/python scripts/audit.py --all physics=ovphysx  # exits 0"
---
## Why
A published audit of another benchmark found that configured friction never reached the engine. We should prove ours does.

## What
- `solarbench/audit/readback.py`: after a task loads, read mass, inertia, friction, joint limits and effort limits from the engine and compare them with `solarbench/specs`.
- Run for every registered task on both backends. Any mismatch beyond tolerance fails.
- `scripts/audit.py` prints the table; the GPU check runs it.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
