"""SolarBench robot configurations with datasheet actuator limits (see :mod:`solarbench.specs.robots`)."""

from __future__ import annotations

import math
import re

from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.utils import clone
from isaaclab_assets.robots.unitree import G1_29DOF_CFG

from solarbench import REPO_ROOT
from solarbench.specs.robots import G1_EFFORT, G1_VELOCITY

ARM_JOINTS = [
    ".*_shoulder_pitch_joint",
    ".*_shoulder_roll_joint",
    ".*_shoulder_yaw_joint",
    ".*_elbow_joint",
    ".*_wrist_roll_joint",
    ".*_wrist_pitch_joint",
    ".*_wrist_yaw_joint",
]
HAND_JOINTS = [".*_hand_.*_joint"]


def _subset(limits: dict, hand: bool) -> dict[str, float]:
    """Limit entries for the hand group (``hand=True``) or the arm group."""
    return {k: float(v) for k, v in limits.items() if ("hand" in k) == hand}


def _g1_satin_layer(usd_path: str) -> str:
    """Write (once) a USD layer that references the G1 asset and overrides its OmniPBR material inputs."""
    from pathlib import Path

    from isaaclab.utils.assets import retrieve_file_path
    from pxr import Gf, Sdf, Usd, UsdShade

    cache = REPO_ROOT / "data" / "cache" / "g1"
    local = Path(retrieve_file_path(usd_path, download_dir=str(cache)))
    out = local.parent / "g1_satin.usda"
    if out.exists():
        return str(out)
    src = Usd.Stage.Open(str(local))
    root = src.GetDefaultPrim().GetPath()
    st = Usd.Stage.CreateNew(str(out))
    prim = st.DefinePrim(root)
    prim.GetReferences().AddReference(f"./{local.name}")
    st.SetDefaultPrim(prim)
    for p in src.Traverse():
        if not p.IsA(UsdShade.Material):
            continue
        for child in p.GetChildren():
            sh = UsdShade.Shader(child)
            if not sh or not sh.GetInput("diffuse_color_constant"):
                continue
            o = st.OverridePrim(child.GetPath())
            dark = sh.GetInput("metallic_constant") is not None and sh.GetInput("metallic_constant").Get() == 1.0
            o.CreateAttribute("inputs:metallic_constant", Sdf.ValueTypeNames.Float).Set(0.3 if dark else 0.0)
            o.CreateAttribute("inputs:reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(0.55)
            o.CreateAttribute("inputs:diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(
                Gf.Vec3f(0.32, 0.33, 0.35) if dark else Gf.Vec3f(0.62, 0.63, 0.64))
    st.GetRootLayer().Save()
    return str(out)


def g1_fixed_base_cfg(
    pos=(0.0, 0.0, 0.75), yaw_deg: float = 0.0, prim_path: str = "{ENV_REGEX_NS}/Robot"
) -> ArticulationCfg:
    """G1 29-DoF + Dex3 hands with the pelvis pinned (ASSUMPTIONS M1: perfect stance controller).

    Arm and hand effort/velocity limits are the Unitree URDF values (25 / 5 / 1.4 N*m), not the 300 N*m
    overrides of the stock Isaac Lab config. Legs and waist keep the stock actuator models.
    """
    cfg = clone(G1_29DOF_CFG)
    cfg.prim_path = prim_path
    cfg.spawn.fix_root_link = True
    cfg.spawn.activate_contact_sensors = True
    # Render-only: the stock materials are OmniPBR metallic=1.0 / roughness=0.34 (chrome); the real G1 shells
    # are satin grey. A local override layer sets the material inputs; physics is unaffected.
    cfg.spawn.usd_path = _g1_satin_layer(cfg.spawn.usd_path)
    half = math.radians(yaw_deg) / 2
    cfg.init_state.pos = pos
    cfg.init_state.rot = (0.0, 0.0, math.sin(half), math.cos(half))  # xyzw
    cfg.actuators["arms"] = ImplicitActuatorCfg(
        joint_names_expr=ARM_JOINTS,
        joint_effort_limit=_subset(G1_EFFORT, hand=False),
        joint_velocity_limit=_subset(G1_VELOCITY, hand=False),
        stiffness=150.0,  # PD gains are controller choices, not hardware limits (ASSUMPTIONS M2)
        damping=6.0,
        armature=0.01,
    )
    cfg.actuators["hands"] = ImplicitActuatorCfg(
        joint_names_expr=HAND_JOINTS,
        joint_effort_limit=_subset(G1_EFFORT, hand=True),
        joint_velocity_limit=_subset(G1_VELOCITY, hand=True),
        stiffness=10.0,
        damping=0.2,
        armature=0.005,
    )
    return cfg


def _ur16e_socket_layer(usd_path: str) -> str:
    """Write (once) a layer referencing the UR16e and adding a 13 mm socket tool on a fixed joint at the flange.

    Tool frame = wrist_3_link frame (flange face, +Z out of the flange). The socket's internal hex is six boxes
    (13.3 mm across flats) so engagement needs real rotational alignment, as with a real socket.
    """
    from pathlib import Path

    from isaaclab.utils.assets import retrieve_file_path
    from pxr import Gf, Usd, UsdGeom, UsdPhysics

    from solarbench.assets import usd_author as ua
    from solarbench.specs import robots as R

    cache = REPO_ROOT / "data" / "cache" / "ur16e"
    local = Path(retrieve_file_path(usd_path, download_dir=str(cache)))
    out = local.parent / "ur16e_socket_tool.usda"
    if out.exists():
        return str(out)
    src = Usd.Stage.Open(str(local))
    root = src.GetDefaultPrim().GetPath()
    w3 = UsdGeom.XformCache().GetLocalToWorldTransform(src.GetPrimAtPath(root.AppendChild("wrist_3_link")))
    st = Usd.Stage.CreateNew(str(out))
    UsdGeom.SetStageUpAxis(st, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(st, 1.0)
    prim = st.DefinePrim(root)
    prim.GetReferences().AddReference(f"./{local.name}")
    st.SetDefaultPrim(prim)
    tool = UsdGeom.Xform.Define(st, root.AppendChild("socket_tool"))
    tool.AddTransformOp().Set(w3)
    t = tool.GetPath().pathString
    L, af = float(R.SOCKET_TOOL_LENGTH), float(R.SOCKET_ACROSS_FLATS)
    dark = ua.UsdShade.Material.Define(st, f"{t}/Looks/driver")
    sh = ua.UsdShade.Shader.Define(st, f"{t}/Looks/driver/s")
    sh.CreateIdAttr("UsdPreviewSurface")
    sh.CreateInput("diffuseColor", ua.Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.12, 0.12, 0.13))
    sh.CreateInput("roughness", ua.Sdf.ValueTypeNames.Float).Set(0.5)
    dark.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
    steel = ua.UsdShade.Material.Define(st, f"{t}/Looks/socket")
    sh2 = ua.UsdShade.Shader.Define(st, f"{t}/Looks/socket/s")
    sh2.CreateIdAttr("UsdPreviewSurface")
    sh2.CreateInput("diffuseColor", ua.Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.55, 0.56, 0.58))
    sh2.CreateInput("roughness", ua.Sdf.ValueTypeNames.Float).Set(0.4)
    sh2.CreateInput("metallic", ua.Sdf.ValueTypeNames.Float).Set(0.7)
    steel.CreateSurfaceOutput().ConnectToSource(sh2.ConnectableAPI(), "surface")
    for nm, r, z0, z1, mat in (("driver", 0.032, 0.0, 0.11, dark), ("adapter", 0.012, 0.11, L - 0.015, steel),
                               ("socket_body", 0.0115, L - 0.015, L - 0.0105, steel)):
        ua.cylinder_mesh(st, f"{t}/{nm}", r, z1 - z0, (0, 0, (z0 + z1) / 2), material=mat)
        ua.cylinder_collider(st, f"{t}/{nm}_col", r, z1 - z0, (0, 0, (z0 + z1) / 2))
    a, wall, depth = af / 2, 0.0032, 0.0105
    seg = 2 * (a + wall) * math.tan(math.pi / 6) + 2e-4
    for k in range(6):
        ang = k * math.pi / 3
        c = ((a + wall / 2) * math.cos(ang), (a + wall / 2) * math.sin(ang), L - depth / 2)
        ua.box_mesh(st, f"{t}/hex_wall_{k}", (wall, seg, depth), c, (0, 0, math.degrees(ang)), steel)
        ua.box_collider(st, f"{t}/hex_wall_{k}_col", (wall, seg, depth), c, (0, 0, math.degrees(ang)))
    UsdPhysics.RigidBodyAPI.Apply(tool.GetPrim())
    m = UsdPhysics.MassAPI.Apply(tool.GetPrim())
    m.CreateMassAttr(float(R.SOCKET_TOOL_MASS))
    m.CreateCenterOfMassAttr(Gf.Vec3f(0, 0, 0.06))
    m.CreateDiagonalInertiaAttr(Gf.Vec3f(2.9e-3, 2.9e-3, 6.1e-4))
    j = UsdPhysics.FixedJoint.Define(st, root.AppendChild("socket_tool_joint"))
    j.CreateBody0Rel().SetTargets([root.AppendChild("wrist_3_link")])
    j.CreateBody1Rel().SetTargets([tool.GetPath()])
    for attr in (j.CreateLocalPos0Attr, j.CreateLocalPos1Attr):
        attr(Gf.Vec3f(0, 0, 0))
    for attr in (j.CreateLocalRot0Attr, j.CreateLocalRot1Attr):
        attr(Gf.Quatf(1, 0, 0, 0))
    st.GetRootLayer().Save()
    return str(out)


def ur16e_socket_cfg(pos=(0.0, 0.0, 0.0), yaw_deg: float = 0.0, prim_path: str = "{ENV_REGEX_NS}/Robot"
                     ) -> ArticulationCfg:
    """UR16e with a 13 mm socket tool; UR joint torque limits; gravity ON (the stock Isaac Lab UR configs disable
    arm gravity, which SolarBench does not). PD gains are the stock UR10e values (controller choice, M2)."""
    from isaaclab_assets.robots.universal_robots import UR10e_CFG

    from solarbench.specs.robots import UR16E_EFFORT, UR16E_VELOCITY

    cfg = clone(UR10e_CFG)
    cfg.prim_path = prim_path
    cfg.spawn.usd_path = _ur16e_socket_layer(cfg.spawn.usd_path.replace("ur10e/ur10e.usd", "ur16e/ur16e.usd"))
    cfg.spawn.rigid_props.disable_gravity = False
    cfg.spawn.fix_root_link = True
    half = math.radians(yaw_deg) / 2
    cfg.init_state.pos = pos
    cfg.init_state.rot = (0.0, 0.0, math.sin(half), math.cos(half))
    # folded "ready" pose: elbow up, tool pointing down ~0.36 m above the base and ~0.13 m ahead of it, so it starts
    # clear of the modules and the purlin overhang (wrist_1 = -(lift + elbow) - pi/2 keeps the tool vertical)
    cfg.init_state.joint_pos = {"shoulder_pan_joint": 0.0, "shoulder_lift_joint": -2.0, "elbow_joint": 1.6,
                                "wrist_1_joint": -1.1708, "wrist_2_joint": -1.5708, "wrist_3_joint": 0.0}
    eff = {k: float(v) for k, v in UR16E_EFFORT.items()}
    vel = {k: float(v) for k, v in UR16E_VELOCITY.items()}
    groups = {"shoulder": ("shoulder_.*", 1320.0, 72.66), "elbow": ("elbow_joint", 600.0, 34.64),
              "wrist": ("wrist_.*", 216.0, 29.39)}
    cfg.actuators = {}
    for name, (expr, kp, kd) in groups.items():
        cfg.actuators[name] = ImplicitActuatorCfg(
            joint_names_expr=[expr],
            joint_effort_limit={k: v for k, v in eff.items() if re.fullmatch(expr, k)},
            joint_velocity_limit={k: v for k, v in vel.items() if any(re.fullmatch(k, j) for j in eff
                                                                      if re.fullmatch(expr, j))},
            stiffness=kp, damping=kd, armature=0.01)
    return cfg
