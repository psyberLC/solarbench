---
id: infra-container
title: Container and batch-job templates
track: infra
milestone: v1
priority: core
needs: gpu
size: medium
status: todo
owner: ""
depends_on: []
touches:
  - "ops/container.def"
  - "ops/*.pbs"
  - "docs/compute.md"
done_when:
  - "ops/smoke.pbs completes on a GPU node and writes a valid result file"
  - "docs/compute.md describes the steps actually used"
---
## Why
Evaluation sweeps run on a shared cluster with an old base OS, no root and possibly no internet on compute nodes.

## What
- A container definition that runs the simulator and a model server; job templates for an evaluation sweep and for a server plus simulator on one node.
- Everything a job needs is staged beforehand. Record the driver, CUDA and container-runtime versions the run used.
- Result files produced in the container validate and match a local run within intervals.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
