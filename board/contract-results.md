---
id: contract-results
title: Result-file contract
track: contract
milestone: v1
priority: core
needs: cpu
size: small
status: done
owner: spartacosan
depends_on: []
touches:
  - "solarbench/eval/schema.py"
  - "tests/test_schema.py"
done_when:
  - "tools/check.sh"
---
## Why
Tables, plots and the tracker are built from result files, so their shape must be fixed and checked.

## What
- `validate` and `rankable` in `solarbench/eval/schema.py`.
- Every file under `results/` is validated by the unit tests.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
