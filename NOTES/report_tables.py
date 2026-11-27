"""Tables for NOTES/SKILLS_REPORT.md, read from the result files and call logs of NOTES/report_runs.sh.

  .venv/bin/python NOTES/report_tables.py > NOTES/report-runs/tables.md
"""

import json
import pathlib
import statistics

ROOT = pathlib.Path(__file__).parent / "report-runs"
RUNS = [("t3-oracle", "oracle (scripted, privileged)"),
        ("t3-script-unprivileged", "skills, fixed sequence, unprivileged"),
        ("t3-lightning-unprivileged", "skills, Nemotron 3.5 Lightning, unprivileged"),
        ("t2-oracle", "oracle (scripted, privileged)"),
        ("t2-script-privileged", "phase skills, fixed sequence, privileged"),
        ("t2-lightning-privileged", "phase skills, Nemotron 3.5 Lightning, privileged")]


def result(name: str) -> dict | None:
    found = list((ROOT / name).glob("SolarBench*/*.json"))
    return json.loads(found[0].read_text()) if found else None


def pct(r: dict) -> str:
    return f"{r['k']}/{r['n']} ({100 * r['rate']:.0f}%, {100 * r['ci95'][0]:.0f}–{100 * r['ci95'][1]:.0f})"


for task in ("T3", "T2"):
    rows = [(name, label, result(name)) for name, label in RUNS if name.startswith(task.lower())]
    rows = [(name, label, r) for name, label, r in rows if r]
    if not rows:
        continue
    stages = rows[0][2]["episodes"][0].keys()
    stages = [k[len("stage_"):] for k in stages if k.startswith("stage_")]
    print(f"\n### {rows[0][2]['task']}\n")
    head = ["", "privileged", "valid / run"] + stages + ["safe success", "damage", "time to release, s (median)"]
    print("| " + " | ".join(head) + " |\n|" + "---|" * len(head))
    for _, label, r in rows:
        s = r["summary"]
        released = [e["t_released"] for e in r["episodes"] if e.get("t_released", -1) >= 0 and not e["sim_error"]]
        cells = [label, "yes" if r["privileged"] else "no", f"{s['valid_episodes']}/{s['episodes']}"]
        cells += [pct(s[f"stage_{x}"]) for x in stages] + [pct(s["safe_success"]), pct(s["damage"])]
        cells.append(f"{statistics.median(released):.1f}" if released else "–")
        print("| " + " | ".join(cells) + " |")
    print()
    for name, label, r in rows:
        calls_file = ROOT / name / "calls.jsonl"
        if "Lightning" not in label or not calls_file.exists():
            continue
        calls = [json.loads(line) for line in calls_file.read_text().splitlines() if line.strip()]
        per, episode = {}, -1
        for c in calls:  # one environment: an episode's calls start again at round 1
            episode += c["round"] == 1
            per.setdefault(episode, []).append(c)
        written = [c["tokens_written"] for c in calls if c.get("tokens_written") is not None]
        print(f"{label}: {len(calls)} model calls over {len(r['episodes'])} episodes "
              f"(median {statistics.median(len(v) for v in per.values()):.0f} per episode), "
              f"thinking + reply median {statistics.median(written):.0f} tokens per call (max {max(written)}), "
              f"model time {sum(c['wall_s'] for c in calls) / 60:.1f} min; calls without a usable tool call: "
              f"{sum(not c['parsed'] for c in calls)}.")
        per_episode = []
        for e in r["episodes"]:
            mark = "sim error" if e["sim_error"] else "safe" if e["safe_success"] else (
                "damage" if e["damage"] else "failed")
            extra = f", {e['installed_torque_Nm']:.2f} N·m" if "installed_torque_Nm" in e else ""
            per_episode.append(f"ep {e['episode']}: {mark}{extra}")
        print("Per episode: " + "; ".join(per_episode) + ".\n")
    for _, label, r in rows:
        if "installed_torque_Nm" in r["episodes"][0]:
            torques = [f"{e['installed_torque_Nm']:.2f}" for e in r["episodes"]]
            print(f"{label}, installed torque by episode (N·m): {', '.join(torques)}")
