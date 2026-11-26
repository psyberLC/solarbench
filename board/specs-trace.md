---
id: specs-trace
title: Test that every physical value traces to a source
track: assets
milestone: v1
priority: core
needs: cpu
size: small
status: todo
owner: ""
depends_on: [specs-keys]
touches:
  - "tests/test_specs.py"
done_when:
  - "tools/check.sh"
  - "the test fails when a source key in solarbench/specs has no entry in docs/sources.md, and when a value that is not CITED or MEASURED has no entry in ASSUMPTIONS.md"
---
## Why
The rule that every number has a source is only as good as the check behind it.

## What
- A unit test that walks every value in `solarbench/specs`: its source key appears in `docs/sources.md`; if its status is not CITED or MEASURED, its name appears in `ASSUMPTIONS.md`.
- Where the test finds a real gap, open an item for it. Do not edit sources or assumptions to make the test pass.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
