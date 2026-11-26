---
id: contract-policy
title: Policy contract and registry
track: contract
milestone: v1
priority: core
needs: cpu
size: small
status: done
owner: spartacosan
depends_on: []
touches:
  - "solarbench/agents/__init__.py"
  - "scripts/evaluate.py"
  - "tests/test_agents.py"
done_when:
  - "tools/check.sh"
  - "tools/check.sh --gpu  # oracle and zero policy run through the registry"
---
## Why
Every brain, from the scripted oracle to a language model behind an endpoint, must plug in the same way.

## What
- `Policy` protocol (`reset`, `act`, `name`, `privileged`) in `solarbench/agents/__init__.py`.
- A policy is added as one new file, `solarbench/agents/<name>.py`; no shared file is edited.
- `scripts/evaluate.py` builds every policy through `make_policy`.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
