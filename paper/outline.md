# Paper outline

Working title: *Does a sense of force close the contact gap? Measuring where contact fails when models drive robots on specification-level maintenance tasks.* The title is a question until the results answer it.

## What the paper is meant to contribute
None of this is established until the experiment has run.
1. **Tasks scored against real specifications**, with damage as a first-class outcome: a connector that must latch, a bolt that must land in the manufacturer's torque window. Chosen from an atlas of field maintenance tasks coded by the physical skills they need.
2. **A controlled comparison** of brain, interface and force feedback on the same body and tasks, with open-weight models, under real time.
3. **Margin to spec**: a measure that does not saturate, read as how far from the real tolerance a system still works.
4. **Checks on the benchmark itself**: engine read-back of every physical parameter, degenerate policies that must fail, invariance to time step and batch size, two physics engines. Only the last exists today.
5. **Open and re-runnable**: assets with sourced physical values, the assumptions ledger, result files with provenance, hypotheses frozen before the runs.

## Figures
| # | Figure | Built from |
|---|---|---|
| 1 | The two tasks, each with its specification drawn on a force or torque trace | A recorded episode (`paper-figure-1`) |
| 2 | Safe success across brain × interface × force feedback, at specification | Result files |
| 3 | Margin to spec per system, with the real specification as the reference line | Result files (`eval-margin`) |
| 4 | Failure labels per cell: where contact fails | Episode records |
| 5 | Success against measured thinking time | Result files (`eval-latency`) |
| 6 | Atlas coverage: tasks unlocked as skills are added, benchmark tasks marked | `atlas/coverage.py` |

## Sections
1. Introduction: the question, in one page with figure 1.
2. Related work: from [docs/field.md](../docs/field.md), limited to what the comparison needs.
3. Tasks and physics: specifications, contact models, the assumptions ledger, the audit.
4. Experimental design: [hypotheses.md](hypotheses.md) as run.
5. Results: figures 2–5, every hypothesis answered.
6. Limitations: simulation only, backend gap, one body, simulated force sensor.
7. What comes next: the open tracks on the board, briefly.

## Not in this paper
The ten-axis design, hidden evaluation, multi-robot work and real-robot trials. They are in [docs/vision.md](../docs/vision.md) and on the board as open tracks.
