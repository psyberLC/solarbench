"""Reachability study for T2: final IK error to the connector grasp pose vs grasp roll and robot standoff.

Each env gets a different grasp roll phi; the oracle orientation/position goal is held for 4 s.
Usage: .venv/bin/python scripts/dev/reach_study.py --standoff 0.34 --viz none
"""

import argparse
import sys

from isaaclab.app import add_launcher_args, launch_simulation

parser = argparse.ArgumentParser()
parser.add_argument("--standoff", type=float, nargs="+", default=[0.30, 0.36, 0.42])
parser.add_argument("--lateral", type=float, default=0.11)
parser.add_argument("--height", type=float, default=0.75)
add_launcher_args(parser)
args, rest = parser.parse_known_args()
sys.argv = [sys.argv[0], *rest]

import math  # noqa: E402

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402
from isaaclab.utils.math import quat_error_magnitude  # noqa: E402
from isaaclab_tasks.utils import resolve_task_config  # noqa: E402

import solarbench.tasks  # noqa: E402, F401
from solarbench.oracle.mc4_oracle import MC4Oracle  # noqa: E402
from solarbench.tasks import mc4_env_cfg  # noqa: E402

PHIS = [0, 45, 90, 135, 180, 225, 270, 315]
for standoff in args.standoff:
    pose = mc4_env_cfg.LAYOUT.robot_pose(standoff=standoff, lateral=args.lateral, height=args.height)
    cfg, _ = resolve_task_config("SolarBench-T2-MC4-G1-v0", "")
    cfg.scene.num_envs = len(PHIS)
    cfg.scene.robot.init_state.pos = pose.pos
    args.device = cfg.sim.device
    with launch_simulation(cfg, args):
        env = gym.make("SolarBench-T2-MC4-G1-v0", cfg=cfg)
        u = env.unwrapped
        env.reset()
        orc = MC4Oracle(u)
        quats = torch.cat([orc._grasp_quat(math.radians(p))[:1] for p in PHIS])
        orc.quat_b = quats
        # pregrasp -> approach as the oracle does, but never close the hand
        f_max = torch.zeros(len(PHIS), device=u.device)
        for _ in range(120):
            with torch.inference_mode():
                a = orc.act()
                a[:, 6:] = -1.0
                orc.phase.clamp_(max=1)
                env.step(a)
                f_max = torch.maximum(f_max, u.f_hand_w.norm(dim=-1))
        g_pos, g_quat = u.grasp_pose_b()
        rp, rq = u.robot.data.root_pos_w.torch, u.robot.data.root_quat_w.torch
        f_site_w, _ = u.female_site_w()
        from isaaclab.utils.math import quat_apply_inverse

        site_b = quat_apply_inverse(rq, f_site_w - rp)
        pos_err = (g_pos - site_b).norm(dim=-1) * 1e3
        rot_err = torch.rad2deg(quat_error_magnitude(g_quat, quats))
        print(f"\n== standoff {standoff:.2f} m (pelvis {tuple(round(x, 3) for x in pose.pos)})")
        for i, p in enumerate(PHIS):
            print(
                f"   phi={p:3d}  pos_err={float(pos_err[i]):6.1f} mm  rot_err={float(rot_err[i]):5.1f} deg  "
                f"peak_hand_contact={float(f_max[i]):5.1f} N"
            )
        env.close()
