"""Seed splits. ``dev`` is for development and tuning; ``test`` seeds are held out and must only be used for
reported numbers. Randomization ranges are identical across splits for now (only the seeds differ); harder
held-out variation splits (unseen clearances, start poses, module SKUs) are planned (ASSUMPTIONS B2).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Split:
    name: str
    base_seed: int
    description: str


SPLITS = {
    "dev": Split("dev", 0, "development seeds; tune freely"),
    "test": Split("test", 100_000, "held-out seeds; report only"),
}
