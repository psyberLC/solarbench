"""Statistics for SolarBench results: Wilson intervals for rates, percentile bootstrap for continuous metrics.

Robot-evaluation results are usually reported from few trials; the protocol therefore always reports the
interval, never a bare rate (rliable, Agarwal et al. 2021; Wilson 1927).
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence


def wilson_ci(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (95 % by default)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def bootstrap_ci(
    values: Sequence[float], stat=None, n_boot: int = 2000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float, float]:
    """Point estimate and percentile-bootstrap interval of ``stat`` (mean by default)."""
    vals = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not vals:
        return (float("nan"), float("nan"), float("nan"))
    stat = stat or (lambda xs: sum(xs) / len(xs))
    rng = random.Random(seed)
    boots = sorted(stat([rng.choice(vals) for _ in vals]) for _ in range(n_boot))
    lo = boots[int(alpha / 2 * n_boot)]
    hi = boots[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return (stat(vals), lo, hi)


def summarize(records: list[dict], stages: Sequence[str]) -> dict:
    """Benchmark summary for one (task, policy, split, backend) cell.

    Episodes with a simulator error are excluded from every rate and reported as ``sim_error_rate``.
    """
    valid = [r for r in records if not r.get("sim_error", False)]
    n = len(valid)
    out: dict = {
        "episodes": len(records),
        "valid_episodes": n,
        "sim_error_rate": (len(records) - n) / len(records) if records else float("nan"),
    }
    rates = [f"stage_{s}" for s in stages] + ["success", "safe_success", "damage"]
    for key in rates:
        k = sum(bool(r[key]) for r in valid)
        lo, hi = wilson_ci(k, n)
        out[key] = {"rate": k / n if n else float("nan"), "ci95": [lo, hi], "k": k, "n": n}
    succ = [r for r in valid if r["success"]]
    out["time_to_success_s"] = dict(
        zip(("mean", "lo", "hi"), bootstrap_ci([r["duration_s"] for r in succ]), strict=True)
    )
    for key in ("peak_push_force_N", "peak_hand_force_N", "peak_cable_tension_N", "installed_torque_Nm",
                "peak_installed_torque_Nm", "preload_N", "vel_limit_violation_steps"):
        if valid and key in valid[0]:
            out[key] = dict(zip(("mean", "lo", "hi"), bootstrap_ci([r[key] for r in valid]), strict=True))
            out[key]["max"] = max(r[key] for r in valid)
    return out
