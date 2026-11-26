---
id: agents-skill-tools
title: Tool-call interface for the skills rung
track: agents
milestone: v1
priority: core
needs: cpu
size: medium
status: todo
owner: ""
depends_on: [sim-guarded-skills, agents-endpoint]
touches:
  - "solarbench/agents/skill_tools.py"
  - "tests/test_skill_tools.py"
  - "docs/models.md"
done_when:
  - "tools/check.sh"
  - ".venv/bin/python -m pytest -q tests/test_skill_tools.py"
---
## Why
Lets a model call the guarded skills, with images returned after each call.

## What
- Function declarations generated from `solarbench/tasks/skills.py`; one call per round; status and new images returned.
- A cap on calls per episode, recorded in the result.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
