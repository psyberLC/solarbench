---
id: eval-tracker
title: 'Tracker: results over model release dates'
track: eval
milestone: v1
priority: core
needs: cpu
size: small
status: todo
owner: ""
depends_on: [eval-margin]
touches:
  - "scripts/make_tracker.py"
  - "results/models.yaml"
  - "results/tracker.svg"
done_when:
  - ".venv/bin/python scripts/make_tracker.py  # writes results/tracker.svg from the checked-in results"
---
## Why
Re-running the frozen tasks on each new model, and seeing the trend in one figure, is the point of keeping this alive.

## What
- `results/models.yaml`: one entry per model (name, release date, open or closed weights, size).
- `scripts/make_tracker.py` reads rankable result files and draws safe success and margin to spec against release date, with the oracle and the real specification as reference lines.
- Only rankable results are plotted; others are listed as excluded with the reason.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
