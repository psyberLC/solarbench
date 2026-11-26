"""Calibrate the Dex3 grasp centre for the MC4 housing.

A gravity-free housing is placed at the estimated grasp offset (palm frame, axis along palm z), the right
hand closes with its real 1.4 N*m finger limits, and we report where the housing settles in the palm frame,
the contact forces, and whether it is still held when gravity is switched on (by pulling with 0.3 N).

Usage: .venv/bin/python scripts/dev/g1_grasp_calibration.py --offset 0.075 0.035 0.0 --viz none
"""

import argparse

from isaaclab.app import add_launcher_args, launch_simulation

parser = argparse.ArgumentParser()
parser.add_argument("--offset", type=float, nargs=3, default=[0.075, 0.035, 0.0])
parser.add_argument("--site_x", type=float, default=0.052, help="grasp site along the housing from its tip [m]")
add_launcher_args(parser)
args = parser.parse_args()

import isaaclab.sim as sim_utils  # noqa: E402
import torch  # noqa: E402
from isaaclab.assets import AssetBaseCfg, RigidObjectCfg  # noqa: E402
from isaaclab.scene import InteractiveSceneCfg  # noqa: E402
from isaaclab.sensors import ContactSensorCfg  # noqa: E402
from isaaclab.sim import SimulationContext  # noqa: E402
from isaaclab.utils import configclass, instantiate  # noqa: E402
from isaaclab.utils.math import combine_frame_transforms, quat_apply, subtract_frame_transforms  # noqa: E402
from isaaclab_newton.physics import MJWarpSolverCfg, NewtonCfg  # noqa: E402
from isaaclab_newton.sim.schemas import MujocoCollisionCfg  # noqa: E402

from solarbench.tasks.layout import asset_usd  # noqa: E402
from solarbench.tasks.mc4_env_cfg import MC4EnvCfg  # noqa: E402
from solarbench.tasks.robots import g1_fixed_base_cfg  # noqa: E402

CLOSED = MC4EnvCfg().hand_closed


@configclass
class SceneCfg(InteractiveSceneCfg):
    ground = AssetBaseCfg(prim_path="/World/ground", spawn=sim_utils.GroundPlaneCfg())
    robot = g1_fixed_base_cfg(pos=(0.0, 0.0, 0.75), yaw_deg=0.0)
    housing = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/Housing",
        spawn=sim_utils.UsdFileCfg(
            usd_path=asset_usd("mc4_female"),
            activate_contact_sensors=True,
            rigid_props=sim_utils.UsdPhysicsRigidBodyCfg(),
            collision_props=[sim_utils.UsdPhysicsCollisionCfg(), MujocoCollisionCfg(solref=(0.004, 1.0), priority=1)],
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=(2.0, 0.0, 0.1)),
    )
    c_thumb = ContactSensorCfg(
        prim_path="{ENV_REGEX_NS}/Housing",
        filter_prim_paths_expr=["{ENV_REGEX_NS}/Robot/right_hand/right_hand_thumb_.*"],
    )
    c_fingers = ContactSensorCfg(
        prim_path="{ENV_REGEX_NS}/Housing",
        filter_prim_paths_expr=["{ENV_REGEX_NS}/Robot/right_hand/right_hand_(index|middle)_.*"],
    )


sim_cfg = sim_utils.SimulationCfg(
    dt=1 / 600,
    device=args.device,
    physics=NewtonCfg(
        solver_cfg=MJWarpSolverCfg(integrator="implicitfast", cone="elliptic", impratio=10.0, njmax=600, nconmax=300)
    ),
)
with launch_simulation(sim_cfg, args):
    sim = SimulationContext(sim_cfg)
    scene = instantiate(SceneCfg(num_envs=1, env_spacing=3.0))
    sim.reset()
    robot, housing = scene["robot"], scene["housing"]
    palm = robot.body_names.index("right_hand_palm_link")
    hand_ids = [i for i, n in enumerate(robot.joint_names) if n.startswith("right_hand_")]
    import re

    closed = robot.data.default_joint_pos.torch.clone()
    for pat, v in CLOSED.items():
        for i in hand_ids:
            if re.fullmatch(pat, robot.joint_names[i]):
                closed[:, i] = v
    dev = robot.device
    off = torch.tensor([args.offset], device=dev)
    site_b = torch.tensor([[args.site_x, 0.0, 0.0]], device=dev)

    def step(n, target, hold_housing=False, pull=0.0):
        for _ in range(n):
            pp = robot.data.body_pose_w.torch[:, palm]
            if hold_housing:  # keep the housing at the grasp offset, axis = palm z, until the fingers close
                g_pos, _ = combine_frame_transforms(pp[:, :3], pp[:, 3:], off)
                # housing +X along palm +z: rotate palm frame by -90 deg about palm y
                q_rel = torch.tensor([[0.0, -0.7071068, 0.0, 0.7071068]], device=dev)
                from isaaclab.utils.math import quat_mul

                hq = quat_mul(pp[:, 3:], q_rel)
                hp = g_pos - quat_apply(hq, site_b)
                housing.write_root_pose_to_sim_index(root_pose=torch.cat([hp, hq], -1))
                housing.write_root_velocity_to_sim_index(root_velocity=torch.zeros(1, 6, device=dev))
            if pull:
                housing.instantaneous_wrench_composer.add_forces_and_torques_index(
                    forces=torch.tensor([[[0.0, 0.0, -pull]]], device=dev), body_ids=[0], is_global=True
                )
            robot.set_joint_position_target_index(target=target)
            scene.write_data_to_sim()
            sim.step()
            scene.update(sim.get_physics_dt())

    def report(tag):
        pp = robot.data.body_pose_w.torch[:, palm]
        hp, hq = housing.data.root_pos_w.torch, housing.data.root_quat_w.torch
        site_w = hp + quat_apply(hq, site_b)
        site_palm, _ = subtract_frame_transforms(pp[:, :3], pp[:, 3:], site_w)
        ft = scene["c_thumb"].data.force_matrix_w.torch.sum(dim=(1, 2)).norm(dim=-1)
        ff = scene["c_fingers"].data.force_matrix_w.torch.sum(dim=(1, 2)).norm(dim=-1)
        print(
            f"{tag:22s} site in palm frame = {[round(x, 4) for x in site_palm[0].tolist()]}  "
            f"|F_thumb|={float(ft):5.2f} N  |F_fingers|={float(ff):5.2f} N"
        )

    step(300, robot.data.default_joint_pos.torch.clone(), hold_housing=True)
    step(360, closed, hold_housing=True)
    report("closed, before release")
    step(400, closed)

    report("after closing")
    step(600, closed, pull=0.3)
    report("with 0.3 N weight")
    step(600, closed, pull=15.0)
    report("with 15 N pull")
