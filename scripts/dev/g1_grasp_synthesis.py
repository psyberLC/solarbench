"""Grid-search a Dex3 power grasp for the MC4 housing with the real 1.4 / 2.45 N*m finger limits.

Each env gets one (thumb_0, thumb_1, thumb_2, offset_x, offset_y) combination. The housing is held at the grasp
offset while the hand closes, then released under gravity and finally pulled with ``--pull`` N along the
connector axis. A grasp passes if, after settling on release, the housing moves < 3 mm under the pull. The settled
position (palm frame) is the calibrated grasp centre used by the T2 oracle.

Usage: .venv/bin/python scripts/dev/g1_grasp_synthesis.py --viz none
"""

import argparse
import itertools

from isaaclab.app import add_launcher_args, launch_simulation

parser = argparse.ArgumentParser()
parser.add_argument("--pull", type=float, default=15.0)
add_launcher_args(parser)
args = parser.parse_args()

import isaaclab.sim as sim_utils  # noqa: E402
import torch  # noqa: E402
from isaaclab.assets import AssetBaseCfg, RigidObjectCfg  # noqa: E402
from isaaclab.scene import InteractiveSceneCfg  # noqa: E402
from isaaclab.sensors import ContactSensorCfg  # noqa: E402
from isaaclab.sim import SimulationContext  # noqa: E402
from isaaclab.utils import configclass, instantiate  # noqa: E402
from isaaclab.utils.math import combine_frame_transforms, quat_apply, quat_mul, subtract_frame_transforms  # noqa: E402
from isaaclab_newton.physics import MJWarpSolverCfg, NewtonCfg  # noqa: E402
from isaaclab_newton.sim.schemas import MujocoCollisionCfg  # noqa: E402

from solarbench.tasks.layout import asset_usd  # noqa: E402
from solarbench.tasks.robots import g1_fixed_base_cfg  # noqa: E402

T0 = [-0.3, 0.0, 0.3]
T1 = [-1.0, -0.9, -0.75]
T2 = [-0.8, -0.6, -0.4]
OX = [0.060, 0.070]
OY = [0.040, 0.048]
GRID = list(itertools.product(T0, T1, T2, OX, OY))
FINGERS = 1.6
SITE_X = 0.052


@configclass
class SceneCfg(InteractiveSceneCfg):
    ground = AssetBaseCfg(prim_path="/World/ground", spawn=sim_utils.GroundPlaneCfg())
    robot = g1_fixed_base_cfg(pos=(0.0, 0.0, 0.75), yaw_deg=0.0)
    housing = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/Housing",
        spawn=sim_utils.UsdFileCfg(
            usd_path=asset_usd("mc4_female"),
            activate_contact_sensors=True,
            collision_props=[sim_utils.UsdPhysicsCollisionCfg(), MujocoCollisionCfg(solref=(0.004, 1.0), priority=1)],
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=(0.3, -0.15, 0.85)),
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
    scene = instantiate(SceneCfg(num_envs=len(GRID), env_spacing=1.5))
    sim.reset()
    robot, housing = scene["robot"], scene["housing"]
    dev, n = robot.device, len(GRID)
    palm = robot.body_names.index("right_hand_palm_link")
    jn = robot.joint_names
    idx = {
        k: jn.index(f"right_hand_{k}_joint")
        for k in ("thumb_0", "thumb_1", "thumb_2", "index_0", "index_1", "middle_0", "middle_1")
    }
    g = torch.tensor(GRID, device=dev)
    closed = robot.data.default_joint_pos.torch.clone()
    for k in ("index_0", "index_1", "middle_0", "middle_1"):
        closed[:, idx[k]] = FINGERS
    closed[:, idx["thumb_0"]], closed[:, idx["thumb_1"]], closed[:, idx["thumb_2"]] = g[:, 0], g[:, 1], g[:, 2]
    off = torch.stack([g[:, 3], g[:, 4], torch.zeros(n, device=dev)], dim=-1)
    site_b = torch.tensor([SITE_X, 0.0, 0.0], device=dev).repeat(n, 1)
    q_rel = torch.tensor([0.0, -0.7071068, 0.0, 0.7071068], device=dev).repeat(n, 1)  # housing +X -> palm +z
    axis_pull = None

    def run(steps, target, hold=False, pull=0.0):
        global axis_pull
        for _ in range(steps):
            pp = robot.data.body_pose_w.torch[:, palm]
            if hold:
                g_pos, _ = combine_frame_transforms(pp[:, :3], pp[:, 3:], off)
                hq = quat_mul(pp[:, 3:], q_rel)
                housing.write_root_pose_to_sim_index(root_pose=torch.cat([g_pos - quat_apply(hq, site_b), hq], -1))
                housing.write_root_velocity_to_sim_index(root_velocity=torch.zeros(n, 6, device=dev))
            if pull:
                axis = quat_apply(housing.data.root_quat_w.torch, torch.tensor([1.0, 0, 0], device=dev).repeat(n, 1))
                housing.instantaneous_wrench_composer.add_forces_and_torques_index(
                    forces=(pull * axis)[:, None, :], body_ids=[0], is_global=True
                )
            robot.set_joint_position_target_index(target=target)
            scene.write_data_to_sim()
            sim.step()
            scene.update(sim.get_physics_dt())

    def site_in_palm():
        pp = robot.data.body_pose_w.torch[:, palm]
        hp, hq = housing.data.root_pos_w.torch, housing.data.root_quat_w.torch
        return subtract_frame_transforms(pp[:, :3], pp[:, 3:], hp + quat_apply(hq, site_b))[0]

    run(300, robot.data.default_joint_pos.torch.clone(), hold=True)
    run(360, closed, hold=True)
    ref = site_in_palm()
    run(400, closed)
    settled = site_in_palm()
    drift_g = (settled - ref).norm(dim=-1)
    run(600, closed, pull=args.pull)
    drift_p = (site_in_palm() - settled).norm(dim=-1)
    ft = scene["c_thumb"].data.force_matrix_w.torch.sum(dim=(1, 2)).norm(dim=-1)
    ff = scene["c_fingers"].data.force_matrix_w.torch.sum(dim=(1, 2)).norm(dim=-1)
    ok = (drift_g < 0.03) & (drift_p < 0.003)
    order = torch.argsort(drift_p + 10 * (~ok).float())
    print(f"\n{int(ok.sum())}/{n} grasps hold under gravity + {args.pull} N pull")
    for i in order[:12].tolist():
        t0, t1, t2, ox, oy = GRID[i]
        print(
            f"  thumb=({t0:+.1f},{t1:+.1f},{t2:+.1f}) offset=({ox:.3f},{oy:.3f})  "
            f"drift_g={1e3 * float(drift_g[i]):6.1f}mm "
            f"pull_slip={1e3 * float(drift_p[i]):5.2f}mm  F_thumb={float(ft[i]):5.1f}N "
            f"F_fingers={float(ff[i]):5.1f}N "
            f"settled_at={[round(x, 4) for x in settled[i].tolist()]}"
        )
