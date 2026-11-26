# Task atlas

What maintenance work is actually done on a ground-mounted solar plant, and which physical skills each task needs. The benchmark's tasks are chosen from here, so that a score says something about real work.

## Files
- `tasks.csv`: 107 tasks compiled from public sources (101 done in the field, 6 done remotely from a desk), one row each: subsystem, task, group (inspection or physical maintenance), frequency, tools, the physical skills ("primitives") a robot would need, hazards, whether isolation is required, and the source.
- `coverage.py`: counts tasks per skill and the order in which adding skills unlocks the most tasks.

```bash
python atlas/coverage.py
```

## What it shows
Of 101 tasks done in the field, getting to the place and reading something by eye covers 22. Adding wiping, torquing a fastener, opening an enclosure door, thermal imaging, handling a connector, swapping a part and lifting more than 20 kg brings that to 67. Opening an enclosure door (24 tasks), torquing a fastener (20) and handling a connector (13) are the three most common contact skills. With getting there and reading by eye, those three make 38 of the 101 field tasks fully doable.

## Limits
- **Sources.** Mostly NREL's *Best Practices for Operation and Maintenance of Photovoltaic and Energy Storage Systems* (3rd edition, 2018) and one central-inverter maintenance manual. Tracker manufacturers' manuals, the SolarPower Europe guideline's annual plan and the text of IEC 62446-2 were not available. Security, fencing and lightning protection are missing.
- **Labels.** The skill labels are one coder's judgement. A second independent coding is on the board (`atlas-second-coder`).
- **No labour hours.** No public source gives hours per task. Frequency is given where a source states it.
- **Not a field record.** This is what guidance documents say should be done, not a record of what is done on operating plants.
