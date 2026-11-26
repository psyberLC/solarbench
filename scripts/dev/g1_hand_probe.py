"""Probe the G1 Dex3 right hand: palm frame, fingertip positions (palm frame) for candidate finger poses.

Usage: .venv/bin/python scripts/dev/g1_hand_probe.py
"""

import argparse

from isaaclab.app import add_launcher_args, launch_simulation

parser = argparse.ArgumentParser()
add_launcher_args(parser)
args = parser.parse_args()


import isaaclab.sim as sim_utils  # noqa: E402
from isaaclab.assets import AssetBaseCfg  # noqa: E402
from isaaclab.scene import InteractiveSceneCfg  # noqa: E402
from isaaclab.sim import SimulationContext  # noqa: E402
from isaaclab.utils import configclass, instantiate  # noqa: E402
from isaaclab.utils.math import subtract_frame_transforms  # noqa: E402
from isaaclab_newton.physics import MJWarpSolverCfg, NewtonCfg  # noqa: E402

from solarbench.tasks.robots import g1_fixed_base_cfg  # noqa: E402


@configclass
class SceneCfg(InteractiveSceneCfg):
    ground = AssetBaseCfg(prim_path="/World/ground", spawn=sim_utils.GroundPlaneCfg())
    robot = g1_fixed_base_cfg(pos=(0.0, 0.0, 0.75), yaw_deg=0.0)


CANDIDATES = {
    "open": {},
    "close_pos": {
        "right_hand_index_0_joint": 1.0,
        "right_hand_index_1_joint": 1.0,
        "right_hand_middle_0_joint": 1.0,
        "right_hand_middle_1_joint": 1.0,
        "right_hand_thumb_1_joint": 0.5,
        "right_hand_thumb_2_joint": -1.0,
    },
    "close_neg_thumb": {
        "right_hand_index_0_joint": 1.0,
        "right_hand_index_1_joint": 1.0,
        "right_hand_middle_0_joint": 1.0,
        "right_hand_middle_1_joint": 1.0,
        "right_hand_thumb_1_joint": -0.8,
        "right_hand_thumb_2_joint": -1.0,
    },
}

sim_cfg = sim_utils.SimulationCfg(
    dt=1 / 600, device=args.device, physics=NewtonCfg(solver_cfg=MJWarpSolverCfg(integrator="implicitfast"))
)
with launch_simulation(sim_cfg, args):
    sim = SimulationContext(sim_cfg)
    scene = instantiate(SceneCfg(num_envs=1, env_spacing=2.0))
    sim.reset()
    robot = scene["robot"]
    names = robot.body_names
    palm = names.index("right_hand_palm_link")
    tips = {n: names.index(n) for n in names if n.startswith("right_hand_") and n.endswith(("_1_link", "_2_link"))}
    print("joint names:", robot.joint_names)
    for label, q in CANDIDATES.items():
        target = robot.data.default_joint_pos.torch.clone()
        for jn, v in q.items():
            target[:, robot.joint_names.index(jn)] = v
        for _ in range(600):
            robot.set_joint_position_target_index(target=target)
            scene.write_data_to_sim()
            sim.step()
            scene.update(sim.get_physics_dt())
        pose = robot.data.body_pose_w.torch[0]
        print(f"\n== {label}: palm world pos {pose[palm, :3].tolist()} quat(xyzw) {pose[palm, 3:].tolist()}")
        for n, i in tips.items():
            p_b, _ = subtract_frame_transforms(
                pose[palm : palm + 1, :3], pose[palm : palm + 1, 3:], pose[i : i + 1, :3]
            )
            print(f"  {n:28s} in palm frame: {[round(x, 4) for x in p_b[0].tolist()]}")
        jp = robot.data.joint_pos.torch[0]
        print("  achieved:", {jn: round(float(jp[robot.joint_names.index(jn)]), 3) for jn in q})
