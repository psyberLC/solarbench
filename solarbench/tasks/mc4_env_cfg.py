"""T2: disconnect and reconnect an MC4 pair under a low-mount module (single robot, Unitree G1 + Dex3)."""

from __future__ import annotations

import isaaclab.sim as sim_utils
from isaaclab.assets import ArticulationCfg, AssetBaseCfg, RigidObjectCfg
from isaaclab.envs import DirectRLEnvCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sensors import ContactSensorCfg
from isaaclab.sim import RigidBodyMaterialCfg, SimulationCfg
from isaaclab.utils import configclass
from isaaclab.visualizers import VisualizerCfg
from isaaclab_newton.physics import MJWarpSolverCfg, NewtonCfg, NewtonCollisionPipelineCfg
from isaaclab_newton.sim.schemas import MujocoCollisionCfg
from isaaclab_ov.physics import OvPhysxCfg
from isaaclab_tasks.utils import PresetCfg

from solarbench.specs import FRICTION, LONGI_LR7_72HVD, MC4, TABLE_DEFAULT
from solarbench.tasks.layout import ASSET_ROOT, LowMountLayout, asset_usd
from solarbench.tasks.robots import g1_fixed_base_cfg

LAYOUT = LowMountLayout(TABLE_DEFAULT, LONGI_LR7_72HVD)
_robot_pose = LAYOUT.robot_pose()
_kinematic = sim_utils.UsdPhysicsRigidBodyCfg(kinematic_enabled=True)
# Stiffer contact for the 30 g connector halves: default solref 0.02 s let the nose sink ~1 mm into a
# 0.3 mm-clearance bore. 0.004 s is >= 2 physics steps at 600 Hz (MuJoCo stability rule). ASSUMPTIONS P15.
_connector_contact = [sim_utils.UsdPhysicsCollisionCfg(), MujocoCollisionCfg(solref=(0.004, 1.0), priority=1)]


@configclass
class MC4SceneCfg(InteractiveSceneCfg):
    ground = AssetBaseCfg(
        prim_path="/World/ground",
        spawn=sim_utils.GroundPlaneCfg(
            physics_material=RigidBodyMaterialCfg(
                static_friction=float(FRICTION.ground_gravel), dynamic_friction=float(FRICTION.ground_gravel)
            )
        ),
    )
    light = AssetBaseCfg(prim_path="/World/light", spawn=sim_utils.DomeLightCfg(intensity=2500.0))
    table = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/Table",
        spawn=sim_utils.UsdFileCfg(usd_path=asset_usd("fixed_tilt_table_1p"), rigid_props=_kinematic),
    )
    module = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/Module",
        spawn=sim_utils.UsdFileCfg(usd_path=asset_usd(LONGI_LR7_72HVD.name), rigid_props=_kinematic),
        init_state=RigidObjectCfg.InitialStateCfg(pos=LAYOUT.module_pose().pos, rot=LAYOUT.module_pose().rot),
    )
    # neighbouring modules on the same table: physically present (kinematic), so the robot can collide with them
    module_left = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/ModuleLeft",
        spawn=sim_utils.UsdFileCfg(usd_path=asset_usd(LONGI_LR7_72HVD.name), rigid_props=_kinematic),
        init_state=RigidObjectCfg.InitialStateCfg(pos=LAYOUT.module_pose(0).pos, rot=LAYOUT.module_pose(0).rot),
    )
    module_right = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/ModuleRight",
        spawn=sim_utils.UsdFileCfg(usd_path=asset_usd(LONGI_LR7_72HVD.name), rigid_props=_kinematic),
        init_state=RigidObjectCfg.InitialStateCfg(pos=LAYOUT.module_pose(2).pos, rot=LAYOUT.module_pose(2).rot),
    )
    # optional visual-only site context for demo renders (single env only); see MC4EnvCfg.enable_scenery()
    scenery: AssetBaseCfg | None = None
    male = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/MC4Male",
        spawn=sim_utils.UsdFileCfg(
            usd_path=asset_usd("mc4_male"), rigid_props=_kinematic, collision_props=_connector_contact
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=LAYOUT.male_pose().pos, rot=LAYOUT.male_pose().rot),
    )
    female = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/MC4Female",
        spawn=sim_utils.UsdFileCfg(
            usd_path=asset_usd("mc4_female"), activate_contact_sensors=True, collision_props=_connector_contact
        ),
        init_state=RigidObjectCfg.InitialStateCfg(
            pos=LAYOUT.female_pose(LAYOUT.seated_depth()).pos, rot=LAYOUT.female_pose(0.0).rot
        ),
    )
    robot: ArticulationCfg = g1_fixed_base_cfg(pos=_robot_pose.pos)
    # Three filtered sensors on the housing: grasped = fingers opposed by thumb or palm. Filters list one prim per
    # pattern: OvPhysX rejects patterns that match several prims (Newton accepts both).
    contact_thumb = ContactSensorCfg(prim_path="{ENV_REGEX_NS}/MC4Female", filter_prim_paths_expr=[
        f"{{ENV_REGEX_NS}}/Robot/right_hand/right_hand_thumb_{i}_link" for i in range(3)])
    contact_fingers = ContactSensorCfg(prim_path="{ENV_REGEX_NS}/MC4Female", filter_prim_paths_expr=[
        f"{{ENV_REGEX_NS}}/Robot/right_hand/right_hand_{f}_{i}_link" for f in ("index", "middle") for i in range(2)])
    contact_palm = ContactSensorCfg(prim_path="{ENV_REGEX_NS}/MC4Female",
                                    filter_prim_paths_expr=["{ENV_REGEX_NS}/Robot/right_hand/right_hand_palm_link"])

    def __post_init__(self):
        self.robot.init_state.rot = _robot_pose.rot


@configclass
class MC4SimCfg(PresetCfg):
    """600 Hz physics on both backends: the connector is a 30 g body in tight-clearance contact."""

    newton_mjwarp: SimulationCfg = SimulationCfg(
        dt=1 / 600,
        render_interval=20,
        # The latch projection and cable tether run in _apply_action and must execute every physics substep.
        # Newton's native-actuator fast path folds the whole decimation loop into one graphed step, which would
        # apply them once per policy step (found by the unlock-timer audit), so it is disabled for this task.
        use_newton_actuators=False,
        default_visualizer_cfg=VisualizerCfg(eye=(-0.62, 2.45, 1.22), lookat=(-0.12, 1.93, 1.08)),
        physics=NewtonCfg(
            solver_cfg=MJWarpSolverCfg(
                solver="newton",
                integrator="implicitfast",
                cone="elliptic",
                impratio=10.0,
                iterations=100,
                ls_iterations=50,
                njmax=600,
                nconmax=300,
                use_mujoco_contacts=False,
            ),
            collision_cfg=NewtonCollisionPipelineCfg(rigid_contact_max=20000),
            num_substeps=1,
        ),
    )
    ovphysx: SimulationCfg = SimulationCfg(
        dt=1 / 600, render_interval=20, use_newton_actuators=False, physics=OvPhysxCfg()
    )
    default = newton_mjwarp


@configclass
class MC4EnvCfg(DirectRLEnvCfg):
    """Single-robot T2 on the reference module (LONGi LR7-72HVD) and 1P table."""

    episode_length_s = 24.0
    decimation = 20  # 30 Hz policy
    # R1 action: [d_pos(3), d_rot(3) axis-angle, grip, unlock] in [-1, 1]
    action_space = 8
    observation_space = 58
    state_space = 0
    sim: MC4SimCfg = MC4SimCfg()
    scene: MC4SceneCfg = MC4SceneCfg(num_envs=16, env_spacing=6.0, replicate_physics=True)

    # action scaling
    max_ee_step: float = 0.008  # m per policy step (0.24 m/s)
    max_rot_step: float = 0.05  # rad per policy step
    ik_damping: float = 0.05
    ik_windup: float = 0.25  # rad, max joint-target lead over measured joints
    ee_body: str = "right_hand_palm_link"
    # Calibrated by scripts/dev/g1_grasp_synthesis.py: where the housing settles in the closed hand (palm frame);
    # that grasp holds 30 N axial pull with 2.8 mm slip under the URDF finger torque limits.
    grasp_offset: tuple[float, float, float] = (0.066, 0.028, 0.006)
    grasp_site_local_x: float = 0.052  # m from the housing tip (36 mm outside the mouth when seated)
    arm_joints: tuple[str, ...] = (
        "right_shoulder_pitch_joint",
        "right_shoulder_roll_joint",
        "right_shoulder_yaw_joint",
        "right_elbow_joint",
        "right_wrist_roll_joint",
        "right_wrist_pitch_joint",
        "right_wrist_yaw_joint",
    )
    hand_open: dict = None
    hand_closed: dict = None

    # connector model (ASSUMPTIONS P4/P5)
    gate_depth: float = float(MC4.latch_depth) - 0.003
    latch_depth: float = float(MC4.latch_depth)
    seated_depth: float = float(MC4.insertion_travel)
    # The lead (portrait long-lead option) is cable-tied along the purlin; the tether is the free tail from the
    # last tie to the housing, minus the rigid cable stub (ASSUMPTIONS P6/P20).
    tether_length: float = float(MC4.lead_free_tail) - float(MC4.cable_stub_length)
    show_cables: bool = False  # render-only cable drawing (enabled by enable_scenery)
    tether_stiffness: float = 1000.0  # N/m, explicit-stability bounded (ASSUMPTIONS P6)
    tether_damping: float = 1.5
    grasp_force_threshold: float = 1.0  # N per side to count as grasped
    grasp_filter_tau: float = 0.05  # s, low-pass on the opposed-contact signal

    # randomization (training seeds); evaluation uses the held-out ranges in solarbench.eval.splits
    insertion_force_range: tuple[float, float] = (
        float(MC4.insertion_force) - float(MC4.insertion_force_tol),
        float(MC4.insertion_force) + float(MC4.insertion_force_tol),
    )
    withdrawal_force_range: tuple[float, float] = (200.0, 300.0)  # Phoenix 250 +/- 50 N stand-in
    robot_standoff_noise: float = 0.03  # m, start-pose randomization (applied to arm targets via IK goal)
    female_friction_range: tuple[float, float] = (0.25, 0.45)

    # success / stage thresholds
    separated_distance: float = 0.010  # tip 10 mm outside the mouth
    released_distance: float = 0.05  # hand moved away after reconnect

    # reward scales (PPO baseline only; benchmark scoring uses solarbench.eval.stats, not rewards)
    rew_reach: float = 1.0
    rew_grasp: float = 2.0
    rew_unlock: float = 3.0
    rew_separate: float = 5.0
    rew_align: float = 2.0
    rew_insert: float = 5.0
    rew_latch: float = 10.0
    rew_action_rate: float = -0.01
    rew_damage: float = -20.0

    def enable_scenery(self) -> None:
        """Demo rendering: textured terrain + neighbouring rows (visual only), hide the debug checkerboard."""
        self.scene.scenery = AssetBaseCfg(
            prim_path="/World/Scenery",
            spawn=sim_utils.UsdFileCfg(usd_path=str(ASSET_ROOT / "scenes/low_mount_site/low_mount_site.usda")))
        self.scene.ground.spawn.visible = False
        self.show_cables = True

    def __post_init__(self):
        self.hand_open = {"right_hand_.*_joint": 0.0}
        self.hand_closed = {
            "right_hand_index_[01]_joint": 1.6,
            "right_hand_middle_[01]_joint": 1.6,
            "right_hand_thumb_0_joint": 0.3,
            "right_hand_thumb_1_joint": -1.0,
            "right_hand_thumb_2_joint": -0.8,
        }
