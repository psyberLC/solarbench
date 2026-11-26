---
id: contract-harness-catalogue
title: The evaluator reads a task's catalogue and delivers its work order
track: contract
milestone: v1
priority: core
needs: gpu
size: small
status: done
owner: psyberLC
depends_on: [contract-policy-inputs, sim-obs-channels]
touches:
  - "scripts/evaluate.py"
  - "solarbench/agents/__init__.py"
  - "solarbench/tasks/mc4_env.py"
  - "tests/test_agents.py"
done_when:
  - "tools/check.sh --gpu"
  - "a test policy that selects `proprio` runs on the bolt task, receives that channel and the work order, and its result is recorded as not privileged"
---
## Why
`contract-policy-inputs` builds a policy from a catalogue that the evaluator writes itself, with the privileged state vector as the only channel. `sim-obs-channels` gives the bolt task a catalogue of its own, with sensor channels and a work order. Nothing joins the two: a sensor-only policy cannot yet be run, and a policy that is not given the environment has no way to read the work order.

## What
- `scripts/evaluate.py` takes the catalogue from the task and hands the policy the channels it selected, as the task returns them. The catalogue and the clock that the evaluator builds today are removed.
- The connector task publishes its catalogue the same way (`solarbench/tasks/channels.py`): the clock and the privileged state vector.
- The work order reaches the policy as the `EPISODE` message of `docs/interface.md`: `reset` is called with the environments that start an episode and the work order of each.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
- 2026-11-26, claude-code (for psyberLC): done on the fork `psyberLC/solarbench` (branch `laptop-llm`); not proposed upstream. `scripts/evaluate.py` builds the policy from the catalogue the task publishes (`env.unwrapped.catalogue`) and hands it the channels it selected, as the task returns them; the evaluator's own catalogue and clock are removed. The connector publishes its catalogue the same way, with the clock and the privileged vector only, and now returns the clock among its observations. `reset(env_ids, work_orders)` is called for every environment before the first frame, then for each episode that starts. The connector has no work order yet (`agents-prompts`), so its EPISODE message carries an empty one.
  - `tools/check.sh --gpu` (RTX 4060 Laptop, 8 envs, Newton): lint clean, 72 unit tests passed, board ok; bolt tightening oracle 8/8 safe success, zero 0/8; connector oracle 8/8, zero 0/8; "all checks passed". The log file of that run was overwritten with NUL bytes partway, so these numbers are read from the four result files it wrote (`oracle_dev_newton.json` and `zero_dev_newton.json` per task).
  - Done-when probe (`NOTES/probes/probe_harness.py` on `laptop-llm`): a policy selecting only `proprio` ran through `scripts/evaluate.py` on `SolarBench-T3-ClampTighten-UR16e-v0` (dev, 2 episodes, 2 envs). The catalogue offered `['clock', 'proprio', 'wrench', 'policy']`; the policy was handed `['clock', 'proprio']`, proprio shape `[2, 19]`, on each of 899 ticks; each environment got a non-empty work order at both resets (it begins "# Work order: tighten a module clamp bolt …"); the result file says `privileged = False`.
  - Not done: `docs/interface.md` still says no task uses the catalogue layouts; it is outside this item's paths.
