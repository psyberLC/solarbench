---
id: audit-cross-gpu
title: Same result on a different GPU
track: audit
milestone: v1
priority: stretch
needs: gpu
size: small
status: todo
owner: ""
depends_on: []
touches:
  - "results/*/oracle_test_*"
  - "docs/tasks.md"
done_when:
  - "results/<task>/ holds an oracle result from a GPU model not yet listed in docs/tasks.md"
  - "the table in docs/tasks.md has a row for that GPU, and says whether its intervals overlap the reference"
---
## Why
GPU physics is not bit-identical across GPU models. The claim is that results agree within their intervals; each new card tests it.

## What
- Run the held-out oracle evaluation for one task on your GPU, from a clean tree.
- Commit the result file unedited and add a row to the table "Agreement across GPU models" in `docs/tasks.md`. A disagreement is a finding: report it, do not tune it away.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
