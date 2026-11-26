---
id: paper-figure-1
title: The explainer figure
track: paper
milestone: v1
priority: core
needs: gpu
size: medium
status: todo
owner: ""
depends_on: []
touches:
  - "scripts/make_figure_1.py"
  - "paper/figures/*"
done_when:
  - ".venv/bin/python scripts/make_figure_1.py  # writes paper/figures/figure_1.svg"
  - "someone outside the team explains the task back correctly after ten seconds with the figure"
---
## Why
A reader should understand what is measured, and how, from one picture.

## What
- One rendered frame per task with the specification drawn on it: the torque window on a torque-angle trace, the latch on an insertion-force trace.
- Built by a script from a recorded episode, so it can be regenerated.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
