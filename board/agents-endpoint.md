---
id: agents-endpoint
title: Policy adapter for any chat-completions endpoint
track: agents
milestone: v1
priority: core
needs: cpu
size: medium
status: done
owner: spartacosan
depends_on: [contract-interface, contract-harness-catalogue]
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
- `solarbench/agents/endpoint.py`: builds the request from the selected channels (work order, images, proprio, optional wrench) and turns the reply into one `TOOL_POSE` record per round. The catalogue and the work order go first in the request and do not change within an episode.
- Base URL, model name and sampling settings come from arguments or environment variables. No key is ever written to a result file.
- Requests for all environments go out concurrently. Tokens, wall time and parse failures are logged per call into the episode record.
- Tests run against a local fake server; no GPU or network.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
- 2026-11-26, spartacosan: blocked on `contract-harness-catalogue`. The adapter, its tests and `docs/models.md` are written and tested against a stand-in server. Its `reset` takes the work orders of the episodes that start, which the evaluator does not pass until that item is done; and no task offers the profile it speaks until `sim-pose-action`. The call log (wall time, tokens, readable or not) is kept on the policy; writing it into the episode records is `contract-result-fields`.
- 2026-11-27, claude-code (for psyberLC): done on the fork `psyberLC/solarbench` (branch `laptop-llm`); not proposed upstream. This builds on spartacosan's adapter above (commits kept with their authorship), now that `contract-harness-catalogue` and `sim-pose-action` are done on the fork. Added:
  - Settings `reasoning=on|off` (sent as `chat_template_kwargs.enable_thinking`), `rounds=` (cap per episode; after it the robot holds), `log=` (JSON lines, one per call) and `url=`. Each setting can also come from `SOLARBENCH_ENDPOINT_<NAME>`. The policy name gets `-noreasoning` when reasoning is off, so result files of the two settings do not share a name.
  - A reply is read if it ends with a JSON object, which may span lines or sit in a code fence. Nemotron 3 Nano writes the pose over several lines, which the last-line rule refused. An unreadable reply is asked for once more before the call is counted as unreadable and the robot holds.
  - Per call: tokens cached and the finish reason, beside wall time and tokens. The log adds the reply, the reasoning text and the command. No key or address goes into the log, the settings or a result. A server that cannot be reached is retried for a minute; an HTTP error still stops the run.
  - `tools/check.sh`: lint clean, 87 passed, board ok, all checks passed. `.venv/bin/python -m pytest -q tests/test_endpoint.py`: 7 passed.
  - Against a real model (NVIDIA Nemotron 3 Nano 30B-A3B, Q4_K_M, llama.cpp b12780 on the same laptop): one dev episode on `SolarBench-T3-ClampTighten-UR16e-R2-v0`, reasoning off, 5 rounds. Every reply was read and became a record. The server's prompt cache held the prefix (1,205 of 1,428 tokens cached on round 2), and rounds took 3.3–7.9 s. The episode failed, as expected (H1).
  - Not done: images (no task offers a camera yet); writing the call log into the episode records (`contract-result-fields`).
