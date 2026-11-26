# Where SolarBench is going

What is built today is in the [README](../README.md); what is being built is on the [board](../board/README.md). This page is the longer view: what the benchmark should be able to say about a robot and its model once it is complete. Nothing here is built unless the README says so. Where this page and [interface.md](interface.md) or [the hypotheses](../paper/hypotheses.md) differ, those files win.

## Tasks
One numbered list, used everywhere.

| # | Task | State |
|---|---|---|
| T1 | Reach the right module from a work order | planned |
| T2 | Connector: unplug and re-mate an MC4 pair | built for the humanoid hand; arm version on the board |
| T3 | Bolt: tighten into the torque window, or break loose and back off | built |
| T4 | Module handling: place one module with one robot; carry one with two | open track |
| T5 | Full module swap, from disconnecting to reconnecting | open track |
| T6 | Inspection: find and classify a fault from camera and thermal images | planned |
| T7 | Enclosure: open a latched door | on the board |

## Ten axes
An axis is a capability to be judged; a task is how it is measured. Each axis is meant to be scored over several tasks and variations, so that it cannot be won by fitting one scene.

| # | Axis | What is scored | Tasks | Why it matters on real plants |
|---|---|---|---|---|
| 1 | Fault localisation and triage | The right component found, the fault class, false dispatches | T6, T1 | Aerial surveys find about 249 DC-side issues per MW per year, and about a third of them cause 90% of lost power ([Raptor Maps, 2025](https://pages.raptormaps.com/hubfs/Marketing%20Content%20for%20Website/2025%20Raptor%20Maps%20Global%20Solar%20Report%20compressed.pdf)) |
| 2 | Site mobility | Reaching the target; time, energy, collisions; clearance under low tables | T1 | Every job starts with getting there |
| 3 | Connector work | Latch engaged, insertion force, cable bend radius | T2 | Connectors and junction boxes are linked to about 30% of plant incidents ([Sandia / EPRI](https://energy.sandia.gov/download/70736)) |
| 4 | Fastening and torque | Installed torque inside the window; damage | T3 | Industry guidance asks for torque checks every 6 to 12 months ([SolarPower Europe, 2025](https://www.solarpowereurope.org/insights/thematic-reports/operation-and-maintenance-best-practice-guidelines-version-6-0)) |
| 5 | Module handling | Lifting, placing and seating within glass stress and impact limits | T4 | Physical damage rose to half of module-level power loss in 2024 (Raptor Maps); hail is 73% of weather loss by value ([kWh Analytics](https://www.pv-magazine.com/2025/06/11/hail-risk-remains-top-issue-faced-by-solar-projects/)) |
| 6 | Multi-robot coordination | Load sharing, synchronisation, working with an unseen partner | T4 | A 30 kg module exceeds the payload of either arm modelled here |
| 7 | Long work orders | Progress through the stages of a whole job, and recovery after a failed step | T5 | Corrective work is diagnose, make safe, repair, verify |
| 8 | Electrical procedure | Isolate, verify dead, work, restore; breaking a connector under load is a hard failure | T2, T5 | The connectors "must not be disconnected under load" ([Stäubli](https://portal.segen.co.uk/reseller/docs/PV_MA231_de-en.pdf)) |
| 9 | Physical safety and damage | Glass stress, over-torque, cable over-pull, collisions | every task | A fast repair that breaks something is not a repair |
| 10 | Generalisation and robustness | Score kept under unseen variation; the gap between physics engines | every task | Plants differ in tables, modules, terrain and light |

Time and energy per operation are reported beside every axis and not scored as an axis of their own.

## Scoring
- **Episode:** progress through the task's stages, and zero if anything was damaged.
- **Task:** safe success with its 95% interval.
- **Axis:** the interquartile mean over the axis's tasks and variations, with bootstrap intervals.
- **Entry:** a profile across the axes for each pairing of robot and model. Never one number alone.
- **Ceiling and gap:** the oracle's profile for a robot is that robot's ceiling. A model's distance from it is the model's gap.

## Keeping it honest as it grows
Results on public seeds can be tuned against. Policies that score 90 to 97% on a public manipulation suite have dropped to 0 to 30% under modest changes of camera, object or starting state ([LIBERO-PRO](https://arxiv.org/abs/2510.03827), [LIBERO-Plus](https://arxiv.org/abs/2510.13626)). The design below follows the public, semi-private and private split used by [ARC Prize](https://arcprize.org/policy). It is the open track `open-hidden-split`.

- **Splits.** A public generator for training and development. A public test set on fixed seeds. A hidden set whose generator settings and assets nobody has seen, with seeds redrawn on every run, evaluated by someone other than the entrant.
- **Three kinds of novelty in the hidden set.** Unseen values inside the public ranges. Values outside them but within real-world specification. Mechanisms the public set does not contain, such as another clamp design or connector latch.
- **What varies.** Plant geometry (table type, tilt, clearance), modules, fasteners, connectors and cables, terrain, lighting and soiling, robot placement and sensor noise, the wording of the work order, and the partner robot.
- **What makes a hidden scene admissible.** Every parameter is within real-world specification; the oracle solves it within the robot's limits; a policy that does nothing, or acts at random, fails it.

## Interface
The contract is [interface.md](interface.md). It will need to grow for action sequences sent at control rate, as demonstration-trained models produce them (`open-vla-baselines`), and for several robots sharing observations (`open-carry`).

## Considered, not planned
Panel cleaning, vegetation, cable management, trackers and weather. Each needs a credible way to simulate something soft or fluid before it can be scored honestly.
