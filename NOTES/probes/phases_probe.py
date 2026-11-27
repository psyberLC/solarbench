"""Probe: the connector's phase skills in-process, with a fixed plan and no model, logging the insertion tick by tick.

Runs scripts/evaluate.py with a policy "phasesplan": PhasesPolicy with _ask replaced by the plan grasp, unplug,
plug_in, release, done. HOLD=on (default) runs the policy as it is. HOLD=off runs the oracle's own action every tick,
which is what the plan would do with no boundary between skills. Each episode's trace from phase 5 to 8 (time, phase,
lateral mm, depth mm, grasped, latched) goes to LOG.
  HOLD=off LOG=/tmp/probe.jsonl .venv/bin/python NOTES/probes/phases_probe.py --episodes 64 --num_envs 16 \
      --viz none --split dev --out_dir /tmp/probe
"""

import json
import os
import runpy
import sys

import torch

from solarbench.agents import phases, register

PLAN = ["grasp", "unplug", "plug_in", "release", "done"]
HOLD, LOG = os.environ.get("HOLD", "on") == "on", os.environ.get("LOG", "")


class PlanPolicy(phases.PhasesPolicy):
    def __init__(self, arg, catalogue):
        super().__init__("plan,url=http://unused/v1,notes=NOTES/probes/job_mc4.md", catalogue)
        self.name = "phasesplan-" + ("hold" if HOLD else "nohold")
        self._trace = {}

    def _ask(self, env, text):
        self.calls[env].append({"retry": False, "skill": None})
        name = PLAN[min(len(self.calls[env]) - 1, len(PLAN) - 1)]
        self._call[env] = name
        return name

    def reset(self, env_ids, work_orders):
        for env in torch.as_tensor(env_ids).tolist():
            if LOG and self._trace.get(env):
                with open(LOG, "a") as f:
                    f.write(json.dumps({"trace": self._trace[env]}) + "\n")
            self._trace[env] = []
        super().reset(env_ids, work_orders)

    def act(self, obs):
        e = self._env
        action = super().act(obs) if HOLD else self._oracle.act()
        for env in range(e.num_envs):
            phase = int(self._oracle.phase[env])
            if 5 <= phase <= 8:
                self._trace[env].append([round(float(e.episode_length_buf[env]) * e.step_dt, 3), phase,
                                         round(float(e._lateral[env]) * 1e3, 2), round(float(e.depth[env]) * 1e3, 2),
                                         int(bool(e.grasped[env])), int(bool(e.latch.latched[env]))])
        return action


register("phasesplan")(PlanPolicy)
sys.argv = ["scripts/evaluate.py", "--task", "SolarBench-T2-MC4-G1-v0", "--policy", "phasesplan", *sys.argv[1:]]
runpy.run_path("scripts/evaluate.py", run_name="__main__")
