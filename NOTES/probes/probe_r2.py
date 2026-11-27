"""GPU probe for sim-pose-action: free-space TOOL_POSE waypoints on the R2 bolt task, and how each one ended.

Sends, from the starting tool pose p0/q0: up 5 cm; across 5 cm in x and y; a 0.5 rad turn about the tool axis; back
to p0/q0; then DONE. Prints every completion record. Selects proprio and completions only (not privileged).
Usage: .venv/bin/python NOTES/probes/probe_r2.py --split dev --episodes 2 --num_envs 2 --viz none --out_dir <dir>
"""

import runpy
import sys

import numpy as np
import torch

from solarbench import wire
from solarbench.agents import register, select
from solarbench.tasks.actions import pose_records, quat_from_rotvec, quat_mul

NAMES = {1: "done", 2: "stalled", 3: "timed out", 4: "preempted", 5: "unknown", 6: "invalid", 7: "full"}


class Probe:
    name = "probe-r2"

    def __init__(self, arg, catalogue):
        self.selection = {**select(catalogue, "proprio", "completions"), "wake": "idle"}

    def reset(self, env_ids, work_orders):
        for e in env_ids.tolist():
            self.plan = getattr(self, "plan", {})
            self.plan[e] = None

    def act(self, obs):
        clock, proprio = obs["clock"], obs["proprio"]
        n = len(clock)
        ended = obs["completions"].cpu().numpy().view(wire.COMPLETION)[..., 0]
        records = torch.zeros(n, 1, 16, dtype=torch.int32, device=clock.device)
        for e in range(n):
            if not clock[e, 1] & wire.AWAKE:
                continue
            p, q = proprio[e:e + 1, 12:15], proprio[e:e + 1, 15:19]
            if self.plan[e] is None:
                turned = quat_mul(q, quat_from_rotvec(torch.tensor([[0.0, 0.0, 0.5]], device=q.device)))
                up = p + torch.tensor([[0.0, 0.0, 0.05]], device=p.device)
                across = up + torch.tensor([[0.05, 0.05, 0.0]], device=p.device)
                self.plan[e] = [(up, q), (across, q), (across, turned), (p, q)]
            else:
                c = ended[e, -1]
                print(f"env {e} cmd {c['id']} {NAMES.get(int(c['status']))} after {c['ended'] - c['started']} ticks, "
                      f"pos err {1e3 * c['result'][0]:.2f} mm, rot err {c['result'][1]:.4f} rad", flush=True)
            k = int(clock[e, 0])
            if self.plan[e]:
                pos, quat = self.plan[e].pop(0)
                records[e] = pose_records(pos, quat, torch.tensor([5 - len(self.plan[e])]), torch.tensor([k]))[0]
            else:
                records[e, 0, 0], records[e, 0, 1] = wire.DONE, 9
        return records


register("probe")(Probe)
sys.argv = ["scripts/evaluate.py", "--task", "SolarBench-T3-ClampTighten-UR16e-R2-v0", "--policy", "probe",
            *sys.argv[1:]]
np.set_printoptions(precision=4)
runpy.run_path("scripts/evaluate.py", run_name="__main__")
