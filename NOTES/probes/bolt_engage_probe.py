"""Probe: where the socket is while the bolt turns, against the evaluator's geometric "engaged" condition.

Runs scripts/evaluate.py with the oracle wrapped in a policy "oracleprobe" that, every tick, records for each
environment the bolt angle and the socket's depth over the head, lateral offset from the bolt's axis and tilt,
as the environment computes them for its engaged stage (depth > engage_depth, lateral < engage_lateral, tilt <
engage_angle_deg). One line per episode goes to LOG: the ticks on which the bolt turned, and those quantities on them.
  LOG=/tmp/engage.jsonl .venv/bin/python NOTES/probes/bolt_engage_probe.py --task SolarBench-T3-ClampTighten-UR16e-R2-v0 \
      --episodes 32 --num_envs 16 --viz none --split dev --out_dir /tmp/engage
"""

import json
import os
import runpy
import sys

import torch

from solarbench.agents import OraclePolicy, register

LOG = os.environ["LOG"]


class Probe(OraclePolicy):
    name = "oracleprobe"

    def attach(self, env):
        super().attach(env)
        self._rows, self._last = {}, None

    def reset(self, env_ids, work_orders):
        e = self._env
        for env in torch.as_tensor(env_ids).tolist():
            if self._rows.get(env):
                with open(LOG, "a") as f:
                    f.write(json.dumps({"episode": self._rows[env][0], "rows": self._rows[env][1]}) + "\n")
            self._rows[env] = None
        super().reset(env_ids, work_orders)
        self._last = e.theta.clone()

    def act(self, obs):
        e = self._env
        turned = (e.theta - self._last).abs() > 1e-4
        self._last = e.theta.clone()
        for env in range(e.num_envs):
            if self._rows.get(env) is None:
                self._rows[env] = (int(e.episode_index[env]), [])
            if turned[env]:
                self._rows[env][1].append([round(float(e.episode_length_buf[env]) * e.step_dt, 3),
                                           round(float(e.theta[env]), 4), round(float(e.depth[env]) * 1e3, 2),
                                           round(float(e.lateral[env]) * 1e3, 2),
                                           round(float(e.axis_err_deg[env]), 2), int(bool(e.engaged[env]))])
        return super().act(obs)


register("oracleprobe")(lambda arg, catalogue: Probe(catalogue))
sys.argv = ["scripts/evaluate.py", "--policy", "oracleprobe", *sys.argv[1:]]
runpy.run_path("scripts/evaluate.py", run_name="__main__")
