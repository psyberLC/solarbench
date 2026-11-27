"""Tables for NOTES/REPORT.md, read from the result files and call logs that NOTES/run_all.sh wrote.

Writes NOTES/results.md. Every number in it is computed here from those files; nothing is typed in.
Usage: .venv/bin/python NOTES/analyze.py [runs folder]
"""

from __future__ import annotations

import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from solarbench.eval.stats import bootstrap_ci, wilson_ci

RUNS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "runs"
ORDER = [("floor", "Floor: `zero`"), ("ceiling", "Ceiling: `oracle` replayed as TOOL_POSE"),
         ("model-force-off", "Model, force off, reasoning on"), ("model-force-on", "Model, force on, reasoning on"),
         ("speed-probe", "Speed probe: force on, reasoning off")]
STAGES = ("engaged", "snug", "in_spec", "released")
# Centre of the top of the bolt head in the base frame, as every work order of this task states it
# ("The centre of the top of its head is at (0.420, 0.015, 0.439) m in the base frame").
HEAD = (0.420, 0.015, 0.439)
# The bolt's axis out of the head, in the base frame, as the work orders state it ("(-0.000, 0.342, 0.940)") and as
# the task's layout gives it (solarbench/tasks/layout.py: the clamp's z axis in the arm's frame is (0, 0.342, 0.9397)).
AXIS = (0.0, 0.342, 0.9397)
NEAR, ALIGNED = 0.010, 15.0  # aimed at the bolt: within this many m of the head top, socket axis within this many deg
TIME_LIMIT = 30.0


def pct(k, n):
    lo, hi = wilson_ci(k, n)
    return f"{k}/{n} ({100 * k / n:.0f}%; {100 * lo:.0f}–{100 * hi:.0f}%)" if n else "—"


def load(name):
    log = RUNS / f"{name}.log"
    if not log.exists():
        return None
    text = log.read_text(errors="replace")
    wrote = re.search(r"  wrote (\S+\.json)", text)
    wall = re.search(r"^wall (\d+)s", text, re.M)
    if not wrote:
        return {"name": name, "missing": True}
    result = json.loads(Path(wrote.group(1)).read_text())
    calls = []
    if (RUNS / f"{name}.calls.jsonl").exists():
        calls = [json.loads(line) for line in (RUNS / f"{name}.calls.jsonl").read_text().splitlines() if line]
    return {"name": name, "result": result, "file": wrote.group(1), "wall_s": int(wall.group(1)) if wall else None,
            "calls": calls}


def episode_calls(run):
    """The calls of each episode in the result, matched by environment and order on that environment."""
    by_env = defaultdict(list)
    for ep in run["result"]["episodes"]:
        by_env[ep["env_id"]].append(ep)
    calls = defaultdict(list)
    for call in run["calls"]:
        calls[(call["env"], call["episode_on_env"])].append(call)
    out = {}
    for env, eps in by_env.items():
        for k, ep in enumerate(sorted(eps, key=lambda e: e["episode"])):
            out[ep["episode"]] = calls.get((env, k), [])
    return out


def axis_error(command):
    """Degrees between a TOOL_POSE's socket axis (the tool's z) and the direction into the head (minus AXIS)."""
    x, y, z, w = command[1][3:7]
    tool_z = (2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y))  # the tool's z axis, base frame
    cos = -sum(a * b for a, b in zip(tool_z, AXIS, strict=True))
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def axis_as_quaternion(command):
    """The bolt's axis written into the quaternion's vector part with w = 0 (either sign): a half turn about it."""
    x, y, z, w = command[1][3:7]
    return max(abs(x), abs(w)) < 0.02 and math.dist((abs(y), abs(z)), (abs(AXIS[1]), abs(AXIS[2]))) < 0.02


def aimed(command):
    """Whether a TOOL_POSE puts the socket face near the head top with the socket pointing into the head."""
    return math.dist(command[1][:3], HEAD) <= NEAR and axis_error(command) <= ALIGNED


def label(ep, calls):
    """Failure label from the episode record (and, for the first three rules, its calls), in this order."""
    if ep["damage"]:
        return "over-force"
    if calls and not any(c["parsed"] for c in calls):
        return "malformed output"
    if not ep["stage_engaged"]:
        poses = [c["command"] for c in calls if c["parsed"] and c["command"][0] == 2]
        return "no contact" if any(aimed(p) for p in poses) else "wrong target"
    if not ep["stage_snug"]:
        return "lost contact"
    if not ep["stage_in_spec"]:
        return "under-force"
    return "time out"


def furthest(ep):
    return max((i + 1 for i, s in enumerate(STAGES) if ep[f"stage_{s}"]), default=0)


def main():
    runs = {name: load(name) for name, _ in ORDER}
    lines = ["# Results of the laptop runs", "",
             "Written by `NOTES/analyze.py` from the result files and call logs in `NOTES/runs/`. Task "
             "`SolarBench-T3-ClampTighten-UR16e-R2-v0`, dev split, Newton, lockstep. Rates are k/n with the 95% "
             "Wilson interval; means carry a 95% bootstrap interval.", "",
             "## Outcomes", "",
             "| Run | Policy | Safe success | Damage | Engaged | Snug | In spec | Released | Furthest stage, mean |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, title in ORDER:
        run = runs[name]
        if run is None or run.get("missing"):
            lines.append(f"| {title} | not run or did not finish | | | | | | | |")
            continue
        r, s = run["result"], run["result"]["summary"]
        n = s["valid_episodes"]
        valid = [e for e in r["episodes"] if not e.get("sim_error")]
        m, lo, hi = bootstrap_ci([furthest(e) for e in valid])
        cells = [pct(s[k]["k"], n) for k in ("safe_success", "damage", *(f"stage_{x}" for x in STAGES))]
        lines.append(f"| {title} | `{r['policy'].split(',')[0]}`… | " + " | ".join(cells)
                     + f" | {m:.2f} ({lo:.2f}–{hi:.2f}) of 4 |")
    lines += ["", "Simulator errors: " + ", ".join(
        f"{name} {runs[name]['result']['summary']['sim_error_rate']:.0%}" for name, _ in ORDER
        if runs[name] and not runs[name].get("missing"))]

    lines += ["", "## Model calls", "",
              "A round is one command asked for: one call, or two when the first reply could not be read.", "",
              "| Run | Calls | Rounds | Rounds per episode, mean | Wall per round, s: median (p90) | "
              "Tokens read per call, mean (cached) | Tokens written per call, mean (max) | Unreadable calls | "
              "Rounds with no command | Cut off at max_tokens | Calls writing ≥ 2,048 tokens | "
              "Episodes hit the round cap | Episodes per hour |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, title in ORDER[2:]:
        run = runs[name]
        if run is None or run.get("missing") or not run["calls"]:
            lines.append(f"| {title} | no calls logged | | | | | | | | | | | |")
            continue
        calls = run["calls"]
        rounds = defaultdict(list)
        for c in calls:
            rounds[(c["env"], c["episode_on_env"], c["tick"])].append(c)
        walls = sorted(sum(c["wall_s"] for c in cs) for cs in rounds.values())
        per_episode = Counter((env, k) for env, k, _ in rounds)
        capped = sum(v >= 20 for v in per_episode.values())
        read = statistics.mean(c["tokens_read"] or 0 for c in calls)
        cached = statistics.mean(c["tokens_cached"] or 0 for c in calls)
        written = [c["tokens_written"] or 0 for c in calls]
        no_cmd = sum(not any(c["parsed"] for c in cs) for cs in rounds.values())
        eph = run["result"]["summary"]["episodes"] / run["wall_s"] * 3600 if run["wall_s"] else float("nan")
        lines.append(
            f"| {title} | {len(calls)} | {len(rounds)} | {statistics.mean(per_episode.values()):.1f} | "
            f"{statistics.median(walls):.1f} ({walls[int(0.9 * (len(walls) - 1))]:.1f}) | {read:.0f} ({cached:.0f}) | "
            f"{statistics.mean(written):.0f} ({max(written)}) | "
            f"{pct(sum(not c['parsed'] for c in calls), len(calls))} | "
            f"{pct(no_cmd, len(rounds))} | {sum(c.get('finish') == 'length' for c in calls)} | "
            f"{pct(sum(w >= 2048 for w in written), len(calls))} | "
            f"{capped} of {len(per_episode)} | {eph:.1f} |")
    lines += ["", "Tokens written include the thinking. The server cut thinking at 2,048 tokens "
              "(`--reasoning-budget`); a call that wrote 2,048 or more almost certainly reached that cut, "
              "since the answer itself is about 60 "
              "tokens.", "",
              "Episodes per hour counts the episodes in the result over the run's whole wall time, start-up "
              "included. Calls and rounds include episodes that were still running when the result's episodes "
              "were complete; those episodes are not in the result.", ""]

    lines += ["## What the model commanded", "",
              "Over the episodes in each result. The socket seats only with its axis within 6° of the bolt's.", "",
              "| Run | Poses | Socket axis within 6° of pointing into the head | Within 15° | Bolt axis written as the "
              "quaternion (w = 0) | Median socket-axis error, deg | Median distance to the head top, mm | DONE |",
              "|---|---|---|---|---|---|---|---|"]
    for name, title in ORDER[2:]:
        run = runs[name]
        if run is None or run.get("missing"):
            continue
        cs = [c for calls in episode_calls(run).values() for c in calls if c["parsed"]]
        poses = [c["command"] for c in cs if c["command"][0] == 2]
        errs = [axis_error(p) for p in poses]
        lines.append(f"| {title} | {len(poses)} | {sum(e <= 6 for e in errs)} | {sum(e <= 15 for e in errs)} | "
                     f"{pct(sum(axis_as_quaternion(p) for p in poses), len(poses))} | {statistics.median(errs):.0f} | "
                     f"{1e3 * statistics.median(math.dist(p[1][:3], HEAD) for p in poses):.1f} | "
                     f"{sum(c['command'][0] == 127 for c in cs)} |")
    lines += [""]

    lines += ["## Failure labels", "",
              "One label per failed episode, assigned in this order: damage → over-force; no reply in the "
              "episode could be read → malformed output; never engaged → no contact if some command put the "
              f"socket face within {NEAR * 1e3:.0f} mm of the head top with the socket axis within {ALIGNED:.0f}° of "
              "pointing into the head, else wrong target; engaged but never snug → lost "
              "contact; snug but never in the window → under-force; in the window but never withdrawn → time out.",
              "", "| Run | Failed | Labels |", "|---|---|---|"]
    detail = []
    for name, title in ORDER[2:]:
        run = runs[name]
        if run is None or run.get("missing"):
            continue
        calls = episode_calls(run)
        failed = [e for e in run["result"]["episodes"] if not e["safe_success"] and not e.get("sim_error")]
        counts = Counter(label(e, calls[e["episode"]]) for e in failed)
        lines.append(f"| {title} | {len(failed)} | " + ", ".join(f"{k}: {v}" for k, v in counts.most_common()) + " |")
        for e in sorted(failed, key=lambda e: e["episode"]):
            cs = calls[e["episode"]]
            poses = [c["command"] for c in cs if c["parsed"] and c["command"][0] == 2]
            nearest = min((math.dist(p[1][:3], HEAD) for p in poses), default=float("nan"))
            n_aimed = sum(aimed(p) for p in poses)
            best_axis = min((axis_error(p) for p in poses), default=float("nan"))
            dones = sum(c["parsed"] and c["command"][0] == 127 for c in cs)
            ended = "time limit" if e["duration_s"] >= TIME_LIMIT - 0.05 else f"{e['duration_s']:.1f} s"
            detail.append(f"| {name} | {e['episode']} | {label(e, cs)} | {furthest(e)} | {len(cs)} | "
                          f"{sum(not c['parsed'] for c in cs)} | {1e3 * nearest:.1f} | {best_axis:.0f} | {n_aimed} | "
                          f"{dones} | {ended} | "
                          f"{e['installed_torque_Nm']:.2f} |")
    lines += ["", "### Per episode", "",
              "| Run | Episode | Label | Furthest stage | Calls | Unreadable | Nearest aim to head top, mm | "
              "Best socket-axis error, deg | Poses aimed at the bolt | DONE sent | Ended | Installed torque, N·m |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|", *detail, ""]
    (RUNS.parent / "results.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
