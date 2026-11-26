---
id: sim-cameras
title: Camera images from the Newton Warp renderer
track: sim
milestone: v1
priority: core
needs: gpu
size: medium
status: todo
owner: ""
depends_on: [contract-interface]
touches:
  - "solarbench/tasks/cameras.py"
  - "scripts/dev/camera_probe.py"
  - "ASSUMPTIONS.md"
done_when:
  - ".venv/bin/python scripts/dev/camera_probe.py --task SolarBench-T3-ClampTighten-UR16e-v0  # writes frames, prints the table"
  - "a person looks at the saved frames: the bolt head and socket are visible from the wrist camera"
---
## Why
Vision-language models need images. Rendering must work on GPUs without ray-tracing cores and fit in memory next to the physics.

## What
- `solarbench/tasks/cameras.py`: wrist and overview cameras for the UR arm, returning `images/<camera>` as uint8 RGB plus intrinsics and extrinsics.
- `scripts/dev/camera_probe.py` saves one frame per camera and prints VRAM and frames per second at 1, 8 and 16 environments.
- Record the measurements and the renderer limits in ASSUMPTIONS.md (hardware section).

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
