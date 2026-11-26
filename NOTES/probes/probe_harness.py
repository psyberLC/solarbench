"""GPU check for contract-harness-catalogue: a policy that selects only `proprio` runs through scripts/evaluate.py.

It registers a probe policy, then runs the evaluator unchanged in this process. The probe records which channels it
was handed and the work orders that reached it through reset, and checks the frame matches its selection every tick.
Usage: .venv/bin/python NOTES/probes/probe_harness.py --task <id> --split dev --episodes 4 --num_envs 2 --viz none
"""

import json
import runpy
import sys
from pathlib import Path

from solarbench.agents import register, select

SEEN = {"channels": set(), "work_orders": {}, "ticks": 0}


class Probe:
    name = "probe-proprio"

    def __init__(self, arg, catalogue):
        self.selection = select(catalogue, "proprio")
        SEEN["catalogue_channels"] = [c["name"] for c in catalogue["channels"]]

    def reset(self, env_ids, work_orders):
        for e, w in zip(env_ids.tolist(), work_orders, strict=True):
            SEEN["work_orders"].setdefault(e, []).append(w)

    def act(self, obs):
        assert set(obs) == {"clock", "proprio"}, sorted(obs)
        SEEN["channels"] |= set(obs)
        SEEN["ticks"] += 1
        SEEN["proprio_shape"] = list(obs["proprio"].shape)
        return None


register("probe")(Probe)
ARGS = sys.argv[1:]
sys.argv = ["scripts/evaluate.py", "--policy", "probe", *sys.argv[1:]]
try:
    runpy.run_path("scripts/evaluate.py", run_name="__main__")
finally:
    orders = SEEN["work_orders"]
    print("== probe saw")
    print("  catalogue offers:", SEEN.get("catalogue_channels"))
    print("  channels handed:", sorted(SEEN["channels"]), "proprio shape", SEEN.get("proprio_shape"),
          "ticks", SEEN["ticks"])
    print("  work orders: per env", {e: len(v) for e, v in orders.items()},
          "all non-empty:", all(w for v in orders.values() for w in v))
    first = next(iter(orders.values()))[0] if orders else ""
    print("  first work order:", first[:300].replace("\n", " "), "...")
    out = Path(ARGS[ARGS.index("--out_dir") + 1]) if "--out_dir" in ARGS else None
    if out:
        for f in out.rglob("probe-proprio_*.json"):
            print(f"  result {f}: privileged =", json.loads(f.read_text())["privileged"])
