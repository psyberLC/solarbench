---
id: agents-endpoint
title: Policy adapter for any chat-completions endpoint
track: agents
milestone: v1
priority: core
needs: cpu
size: medium
status: todo
owner: ""
depends_on: [contract-interface]
touches:
  - "solarbench/agents/endpoint.py"
  - "tests/test_endpoint.py"
  - "docs/models.md"
done_when:
  - "tools/check.sh"
  - ".venv/bin/python -m pytest -q tests/test_endpoint.py"
---
## Why
One adapter serves a local open-weight model and a remote one alike: where the brain runs is a URL.

## What
- `solarbench/agents/endpoint.py`: builds the request from the contract observation (prompt, images, proprio, optional wrench), parses one end-effector pose per round.
- Base URL, model name and sampling settings come from arguments or environment variables. No key is ever written to a result file.
- Requests for all environments go out concurrently. Tokens, wall time and parse failures are logged per call into the episode record.
- Tests run against a local fake server; no GPU or network.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
