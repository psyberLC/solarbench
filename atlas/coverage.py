"""Which physical skills unlock which field tasks.

Reads tasks.csv and prints (1) how many tasks need each skill and (2) the greedy order in which adding
skills makes the most tasks fully doable. A task is doable when every skill it lists is available.

    python atlas/coverage.py
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

CSV = Path(__file__).with_name("tasks.csv")
REMOTE = "remote-only"  # desk work: no field skill needed


def load(path: Path = CSV) -> list[set[str]]:
    with path.open() as f:
        return [{p.strip() for p in row["primitives"].split(";") if p.strip()} for row in csv.DictReader(f)]


def skill_counts(tasks: list[set[str]]) -> list[tuple[str, int]]:
    return Counter(skill for task in tasks for skill in task).most_common()


def unlock_order(tasks: list[set[str]]) -> list[tuple[str, int]]:
    """Greedy: at each step add the skill that makes the most tasks fully doable. Ties go to the commoner skill."""
    field = [t for t in tasks if REMOTE not in t]
    freq = Counter(skill for task in field for skill in task)
    have: set[str] = set()
    order = []
    while len(have) < len(freq):
        best = max(sorted(set(freq) - have), key=lambda s: (sum(t <= have | {s} for t in field), freq[s]))
        have.add(best)
        order.append((best, sum(t <= have for t in field)))
    return order


if __name__ == "__main__":
    tasks = load()
    field = sum(REMOTE not in t for t in tasks)
    print(f"{len(tasks)} tasks, {field} done in the field\n\nTasks needing each skill:")
    for skill, n in skill_counts(tasks):
        print(f"  {n:3d}  {skill}")
    print("\nTasks fully doable as skills are added:")
    for skill, n in unlock_order(tasks):
        print(f"  {n:3d}/{field}  + {skill}")
