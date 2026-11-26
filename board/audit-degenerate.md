---
id: audit-degenerate
title: Degenerate policies must fail
track: audit
milestone: v1
priority: core
needs: gpu
size: small
status: todo
owner: ""
depends_on: []
touches:
  - "solarbench/agents/random.py"
  - "solarbench/agents/quit.py"
  - "tools/check.sh"
  - "results/*/zero_*"
  - "results/*/random_*"
  - "results/*/quit_*"
done_when:
  - "tools/check.sh --gpu"
  - "results/<task>/{zero,random,quit}_dev_newton.json show 0 successes"
---
## Why
A success check that passes without the work being done makes every score meaningless.

## What
- Policies `random` and `quit` (ends at the first step) as `solarbench/agents/random.py` and `quit.py`.
- For every registered task: zero, random and quit score 0 safe successes in 200 episodes.
- Add the three to the GPU check with a small episode count.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
