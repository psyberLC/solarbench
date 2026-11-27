# Watching models drive the bolt task: what we learned

Exploratory viewer runs on the laptop, 2026-11-27, by claude-code (for psyberLC), on the local branch `live-viewer` (laptop-llm + the user's upstream PR #14, merged locally, which made the simulation about 7× faster). Not results: every run is the same single episode (dev split, episode 0, the same bolt), with no time limit in the work order (`env.episode_length_s` raised), and most runs read the oracle's privileged data. None of this may be compared with `NOTES/REPORT.md` or used as a benchmark number. The scored result files and call logs that survive are in `NOTES/live-runs/`, unedited.

## What was run

| Run | Model and setup | Outcome |
|---|---|---|
| Claude, attempt 1 | Claude Opus 5.5 as a subagent answering through files (`NOTES/probes/agent_bridge.py`), the same pose interface and prompt as Nemotron, no privileged data, 40 rounds | Seated, snug, in the window, then over-tightened. Its own run never ended (no time limit); a replay of its 40 replies scored seated, snug, in spec, **18.97 N·m (damage)**, not released. The replay's state drifted from the original in the 3rd–4th decimal from round 4, so the score is close, not exact |
| Claude, attempt 2 | + helper commands (aim, push, turn), privileged readings, notes from attempt 1 | **Safe success**, 53 rounds, released at 28.3 s, 15.03 N·m |
| Claude, attempt 3 | + offset as a vector, a briefing aimed at fewer rounds | **Safe success**, 25 rounds, released at 15.4 s, 15.61 N·m |
| Nemotron 3 Nano 30B-A3B Q4_K_M | many variants: pose JSON, helper commands, privileged readings, prose notes, a log line, thinking on/off, caps 2,048 and 8,192 | Never seated. Stopped each time |
| Nemotron 3.5 Lightning 30B-A3B Q4_0 | prose notes, then a decision table, then kept thinking | Never seated; overthinking. Stopped |
| Nemotron 3.5 Lightning, tool calls | native tool calls, facts instead of a procedure, privileged readings, temperature 0.6, 2,048 cap | Seated 9.5 s, snug 13.6 s, **in spec 14.7 s** (15.37 N·m), then turned back and forth and ended at **21.5 N·m (damage)**, not released. 35 rounds, median 349 thinking tokens |
| Nemotron 3.5 Lightning, tool calls, corrected facts | as above, with the torque window and the unloading turn stated in numbers, 4,096 cap; every exchange recorded (`live-runs/lightning-tools3/exchanges.jsonl`) | Caught the head only 1.6–2.1 mm deep (never counted as seated) yet ran the bolt down; at 5.65 N·m turned another 30° to **19.23 N·m (damage)**; later reached 15.8 N·m and unloaded, then lost the socket and spent the last 19 of its 40 rounds searching again. Stopped before the episode ended, so **no scored result file**; figures are from the recorded readings (a reading is taken when a command ends, so the true peak is at least 19.23). Median 234 thinking tokens |

## Lessons about the models
1. **Small open models pattern-match when they cannot reason.** Without thinking, Nano copied the bolt axis into the quaternion, repeated its previous command 20 times, and copied an example log line word for word while spinning the wrist in place. Any concrete example in a prompt gets copied; give a form to fill, not a sample.
2. **Nano reads a procedure but does not carry it out.** Even with every number pre-digested it pushed five times at one angle, or turned without pushing, and its own log recorded angles it never tested.
3. **Overthinking comes from ambiguity and from forgetting, more than from the model.** Nano spent 6–8k thinking tokens a round re-deciding the depth sign and the offset correction; Lightning spent up to 8.3k (32 "actually") re-reading numbered notes. Stating depth in words, giving ready commands, and keeping thinking cut this sharply.
4. **A decision table makes a small model a slow transcriber.** With the table Lightning copied the whole state report and walked every row each round, always hitting the 2,048-token cap. A contradiction in the table (row 7 matching at its own stand-off) cost a full capped round: when the rules conflict, doubt is the right response.
5. **Native tool calls suit Lightning best.** With tools and plain facts it thought a median of 349 tokens a round (10–40 s), alternated turn and push on its own, seated, ran the bolt down and reached the window. That is the interface NVIDIA's examples use.
6. **What then failed was semantics, not geometry.** Lightning read "has reached 14 N·m" as "exactly 14", decided it had overshot at 15.4, followed a vague fact ("a small reverse turn unloads it without loosening") with 10° and 20° reverse turns that loosened the bolt to 5 N·m, and finally turned 30° twice from 8 N·m, ignoring the slope it had been given. Every "small" needs a number, and the success window needs saying as a window. `NOTES/probes/lessons_tools.md` now says both.
7. **Short thinking became careless thinking.** With the corrected facts Lightning thought a median of 234 tokens and spent 339 on the step that broke the clamp: it had been told that 30° past snug adds about 15 N·m and did not do the arithmetic. It also lost the thread once the socket came off, searching to re-seat when only the release was left. Rewriting the notes as facts had dropped "push on until the head is about 5 mm inside", and a socket 1.6–2 mm on the head turns the bolt without counting as seated.
8. **Claude's advantage was memory and bookkeeping**, not only geometry: it kept its own context, tracked which angles it had tested, built a model of the wrist's lag (0.29°/N·m) and the torque slope (0.57 N·m/°), and landed where it predicted.

## Lessons about the interface and the task
- **The chat template drops earlier thinking** whenever a new user message arrives (Nemotron's `truncate_history_thinking`, on by default). Sending each state as a user message made the models start from zero every round. In a tool-calling loop the states are tool results, so the template keeps the thinking without any switch.
- **The force-torque sensor clips at ±10 N·m** (UR16e data sheet, `ASSUMPTIONS.md` M12), below the 14–18 N·m window. Without privileged data, stopping inside the window is guesswork; that is how attempt 1 over-tightened.
- **R2 gives one pose per round with no correction of steady-state error.** An aim lands 0.3–0.5 mm off, the socket only drops on within about 0.2 mm, and turning under load drags it about 1 mm per 15°. The oracle corrects lateral error every tick; an agent has to do it itself (the ready aims in the readings now carry that correction). Fixing it in R2 itself would change the benchmark task: a board item, not part of this branch.
- **The `engaged` reading is stale on an episode's first report** (it carries the previous episode's value for one report).
- **The simulation is not exactly repeatable**: replaying identical replies drifted in the 3rd–4th decimal of contact forces after a few rounds.
- **A thinking cap that binds hurts more than it saves.** Without notes, 2,048 tokens cut most rounds; with the tool interface it rarely binds.
- **Tooling pitfalls met:** the live proxy dropped streamed tool calls until fixed; `tool_choice: "required"` with thinking on makes llama.cpp b12780 leak the thinking into the reply; newer vLLM names the thinking field `reasoning`, llama.cpp `reasoning_content` (the adapter reads both).

## What exists for the next runs (all on `live-viewer`, local)
- `solarbench/agents/endpoint.py`: `commands=assist`, `privileged=on`, `notes=<file>`, `keep_thinking=on`, `tools=on`.
- `NOTES/live.sh` (viewer runs), `NOTES/serve.sh` (`MODEL`, `TOP_P`, `BUDGET`, `PARALLEL`, `CTX`), `NOTES/probes/` (proxy, agent bridge, replay, scripted seating probe, lessons files).
- Tests: 94 pass; ruff clean. Nothing here has been reviewed by a person.
