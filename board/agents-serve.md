---
id: agents-serve
title: Serve open-weight models locally
track: agents
milestone: v1
priority: core
needs: gpu-large
size: medium
status: todo
owner: ""
depends_on: []
touches:
  - "ops/serve.sh"
  - "ops/README.md"
done_when:
  - "ops/serve.sh starts a server that answers a test request"
  - "the measurements are in ops/README.md"
---
## Why
The first results use open weights. A 27B model does not fit one 48 GB card unquantised.

## What
- A recipe that serves Qwen3.8-27B and the PEAR checkpoint behind a chat-completions endpoint on one or two 48 GB GPUs.
- Measure tokens per second and seconds per round at 1, 8 and 16 concurrent requests. If quantised, measure the accuracy cost on a public task and state it.
- Weights and wheels are staged so a node without internet can start the server.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
