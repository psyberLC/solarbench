---
id: atlas-sources
title: Fill the gaps in the task atlas
track: atlas
milestone: v1
priority: stretch
needs: none
size: medium
status: todo
owner: ""
depends_on: []
touches:
  - "atlas/tasks.csv"
  - "atlas/README.md"
  - "tests/test_atlas.py"
done_when:
  - "rows exist for tracker maintenance from at least one tracker maker's manual, and for security, fencing and lightning protection, each with its source"
  - "tools/check.sh  # the atlas test is updated to the new counts in the same change"
---
## Why
The atlas rests mostly on one guide and one inverter manual. Whole subsystems are missing.

## What
- Add tasks from tracker manufacturers' maintenance manuals, an industry annual maintenance plan, and site security and lightning protection guidance.
- One row per task, with the source link, in the existing columns. Only tasks a source lists.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
