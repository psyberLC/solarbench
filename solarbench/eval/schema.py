"""Result-file contract: what every file under ``results/`` must contain.

``validate`` returns a list of problems (empty means valid). ``rankable`` adds the conditions a result must
meet before it may appear in a published table: held-out split, a recorded commit, and a clean working tree.
"""

from __future__ import annotations

from pathlib import Path

SCHEMA_VERSION = 1
RATES = ("success", "safe_success", "damage")
PROVENANCE = ("date", "solarbench_git", "solarbench_dirty", "versions", "gpu", "physics", "physics_dt", "decimation")
EPISODE = ("success", "safe_success", "damage", "duration_s")


def validate(result: dict) -> list[str]:
    errors: list[str] = []

    def need(obj: dict, keys, where: str) -> bool:
        missing = [k for k in keys if k not in obj]
        if missing:
            errors.append(f"{where}: missing {missing}")
        return not missing

    if not need(result, ("task", "policy", "split", "provenance", "summary", "episodes"), "result"):
        return errors
    need(result["provenance"], PROVENANCE, "provenance")
    summary, episodes = result["summary"], result["episodes"]
    if need(summary, ("episodes", "valid_episodes", "sim_error_rate", *RATES), "summary"):
        if summary["episodes"] != len(episodes):
            errors.append(f"summary.episodes={summary['episodes']} but {len(episodes)} episode records")
        for key in RATES:
            cell = summary[key]
            if need(cell, ("rate", "ci95", "k", "n"), f"summary.{key}"):
                if cell["n"] != summary["valid_episodes"]:
                    errors.append(f"summary.{key}.n={cell['n']} != valid_episodes={summary['valid_episodes']}")
                valid = [e for e in episodes if not e.get("sim_error", False)]
                k = sum(bool(e.get(key)) for e in valid)
                if cell["k"] != k:
                    errors.append(f"summary.{key}.k={cell['k']} but the episode records give {k}")
    for i, ep in enumerate(episodes):
        if not need(ep, EPISODE, f"episodes[{i}]"):
            break
        if ep["safe_success"] and (not ep["success"] or ep["damage"]):
            errors.append(f"episodes[{i}]: safe_success without success, or with damage")
    return errors


def rankable(result: dict) -> list[str]:
    """Reasons this result may not be published in a ranked table (empty means it may)."""
    reasons = validate(result)
    prov = result.get("provenance", {})
    if result.get("split") != "test":
        reasons.append(f"split is {result.get('split')!r}, not the held-out 'test' split")
    if not prov.get("solarbench_git"):
        reasons.append("no commit recorded")
    if prov.get("solarbench_dirty") is not False:
        reasons.append("working tree was not clean when the run was made")
    return reasons


def result_path(out_dir: str | Path, task: str, policy: str, split: str, backend: str, commit: str | None) -> Path:
    """Where a new result file goes. An existing file is never overwritten: a later run of the same cell is
    named with its commit, and numbered if that name is taken too."""
    folder, stem = Path(out_dir) / task, f"{policy}_{split}_{backend}"
    tag = (commit or "nocommit")[:7]
    names = [stem, f"{stem}_{tag}", *(f"{stem}_{tag}_{i}" for i in range(2, 1000))]
    return next(folder / f"{name}.json" for name in names if not (folder / f"{name}.json").exists())
