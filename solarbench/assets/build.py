"""Procedural builders for the SolarBench prop set.

Frames (all assets):
    pv module   origin at the module centre; +X along the long edge towards the *top* (junction-box) edge,
                +Y along the short edge, +Z out of the front (glass) face.
    table       origin on the ground below the middle of the lower (front) edge; +X along the row,
                +Y horizontal up-slope (front -> rear), +Z up.
    mc4 male    origin at the centre of the sleeve mouth; +X points out of the mouth.
    mc4 female  origin at the nose tip; +X points from the tip back along the body. When mated at depth d
                the female frame equals the male frame translated by -d along male +X.
"""

from __future__ import annotations

import math
from pathlib import Path

from solarbench.specs import FRICTION, MC4, ModuleSpec, TableSpec
from solarbench.specs.params import MC4Spec

from . import textures, visuals
from . import usd_author as ua
from .visuals import BLACK_PLASTIC

# Coulomb friction per material. Newton/MuJoCo combine pair friction with max(); PhysX averages by default.
# The grasp-relevant pair (rubber pad on aluminium/glass) is carried by the module side.
MAT_FRAME = ua.PhysMat(
    "aluminium_frame", float(FRICTION.rubber_on_glass_or_al), float(FRICTION.rubber_on_glass_or_al), "aluminium"
)
MAT_GLASS = ua.PhysMat("glass", float(FRICTION.rubber_on_glass_or_al), float(FRICTION.rubber_on_glass_or_al), "glass")
MAT_STEEL = ua.PhysMat(
    "galvanized_steel", float(FRICTION.al_on_steel_static), float(FRICTION.al_on_steel_dynamic), "steel"
)
MAT_PLASTIC = ua.PhysMat(
    "connector_plastic", float(FRICTION.plastic_on_plastic), float(FRICTION.plastic_on_plastic), "plastic"
)

QCODE_PV_MODULE = "Q217941"  # "solar cell panel" (verified via wikidata.org API, 2026-10-26)
QCODE_MOUNT = "Q7187941"  # "photovoltaic mounting system" (verified)
QCODE_CONNECTOR = "Q17103376"  # "MC4 connector" (verified)
QCODE_CLAMP = "Q846600"  # "clamp", fastening tool (verified)


def build_pv_module(spec: ModuleSpec, out_dir: Path) -> Path:
    path = ua.asset_path(out_dir, spec.name)
    stage, root = ua.new_stage(path, spec.name, "solar", QCODE_PV_MODULE, "pv_module")
    L, W, D = float(spec.length), float(spec.width), float(spec.depth)
    fw, lip, lt = float(spec.frame_width), float(spec.frame_lip), float(spec.laminate_thickness)
    p_frame, p_glass = ua.physics_material(stage, MAT_FRAME), ua.physics_material(stage, MAT_GLASS)
    front_tex, back_tex = visuals.module_textures(spec, path.parent / "textures")
    visuals.module_visuals(stage, "/RootNode/Visuals", spec, front_tex, back_tex)

    col = "/RootNode/Colliders"
    bars = {
        "frame_left": ((L, fw, D), (0, -(W - fw) / 2, 0)),
        "frame_right": ((L, fw, D), (0, (W - fw) / 2, 0)),
        "frame_bottom": ((fw, W - 2 * fw, D), (-(L - fw) / 2, 0, 0)),
        "frame_top": ((fw, W - 2 * fw, D), ((L - fw) / 2, 0, 0)),
    }
    for name, (size, c) in bars.items():
        ua.box_collider(stage, f"{col}/{name}", size, c, material=p_frame)
    # Laminate sits in the frame groove, top surface 2 mm below the frame top, overlapping the frame by `lip`.
    lam_size = (L - 2 * fw + 2 * lip, W - 2 * fw + 2 * lip, lt)
    lam_c = (0, 0, D / 2 - 0.002 - lt / 2)
    ua.box_collider(stage, f"{col}/laminate", lam_size, lam_c, material=p_glass)
    jb_size = (0.08, 0.12, 0.02)
    jb_c = (L / 2 - float(spec.jbox_from_top_edge), 0, lam_c[2] - lt / 2 - jb_size[2] / 2)
    ua.box_collider(stage, f"{col}/junction_box", jb_size, jb_c, material=p_frame)

    ua.rigid_body(root, float(spec.mass), inertia=spec.box_inertia())
    _attach_frame(stage, "/RootNode/Frames/junction_box", (jb_c[0], jb_c[1], jb_c[2] - jb_size[2] / 2))
    ua.finalize(stage, root, float(spec.mass))
    return path


def table_geometry(table: TableSpec, module: ModuleSpec) -> dict:
    """Derived table geometry (table frame). Returned dict is also used by the task code."""
    t = table.tilt
    up = (0.0, math.cos(t), math.sin(t))  # up-slope unit vector
    nrm = (0.0, -math.sin(t), math.cos(t))  # module-plane normal (front face)
    slope_len = table.rows * float(module.length) + (table.rows - 1) * float(table.module_gap)
    row_len = table.modules_per_row * float(module.width) + (table.modules_per_row + 1) * float(table.module_gap)
    h0 = float(table.lower_edge_height)
    purlin_s = []
    for r in range(table.rows):
        base = r * (float(module.length) + float(table.module_gap))
        purlin_s += [base + module.clamp_zone_nominal, base + float(module.length) - module.clamp_zone_nominal]
    module_centres = []  # (x, s) of each module centre: x along row, s along slope from lower edge
    for r in range(table.rows):
        for c in range(table.modules_per_row):
            x = -row_len / 2 + float(table.module_gap) * (c + 1) + float(module.width) * (c + 0.5)
            s = r * (float(module.length) + float(table.module_gap)) + float(module.length) / 2
            module_centres.append((x, s))

    def plane_point(x: float, s: float, n: float = 0.0) -> tuple[float, float, float]:
        """Point at row coordinate x, slope distance s, normal offset n from the module back plane."""
        return (x, s * up[1] + n * nrm[1], h0 + s * up[2] + n * nrm[2])

    return dict(
        tilt=t,
        up=up,
        normal=nrm,
        slope_len=slope_len,
        row_len=row_len,
        purlin_s=purlin_s,
        module_centres=module_centres,
        plane_point=plane_point,
    )


def build_table(table: TableSpec, module: ModuleSpec, out_dir: Path, name: str = "fixed_tilt_table_1p") -> Path:
    """Static steel substructure: posts, rafters and purlins (module back plane = purlin tops)."""
    path = ua.asset_path(out_dir, name)
    stage, root = ua.new_stage(path, name, "solar", QCODE_MOUNT, "mounting_structure")
    g = table_geometry(table, module)
    p_steel = ua.physics_material(stage, MAT_STEEL)
    tilt_deg = math.degrees(g["tilt"])
    ph, pw, ps = float(table.purlin_height), float(table.purlin_width), float(table.post_section)
    vis, col = "/RootNode/Visuals", "/RootNode/Colliders"

    steel_len = 0.0
    for i, s in enumerate(g["purlin_s"]):
        c = g["plane_point"](0.0, s, -ph / 2)
        size = (g["row_len"] + 0.2, pw, ph)
        steel_len += size[0]
        ua.box_collider(stage, f"{col}/purlin_{i}", size, c, (tilt_deg, 0, 0), p_steel)

    half = (g["row_len"] / 2) - 0.25
    n_st = max(2, int(math.ceil(g["row_len"] / float(table.station_spacing))) + 1)
    stations = [-half + k * (2 * half) / (n_st - 1) for k in range(n_st)]
    s0, s1 = g["purlin_s"][0] - 0.15, g["purlin_s"][-1] + 0.15
    for k, x in enumerate(stations):
        mid = 0.5 * (s0 + s1)
        c = g["plane_point"](x, mid, -ph - ps / 2)
        size = (ps, s1 - s0, ps)
        steel_len += size[1]
        ua.box_collider(stage, f"{col}/rafter_{k}", size, c, (tilt_deg, 0, 0), p_steel)
        for j, s in enumerate((s0 + 0.1, s1 - 0.1)):
            top = g["plane_point"](x, s, -ph - ps)
            h = top[2]
            c = (x, top[1], h / 2)
            steel_len += h
            ua.box_collider(stage, f"{col}/post_{k}_{j}", (ps, ps, h), c, material=p_steel)

    visuals.table_visuals(stage, vis, table, module, g, stations, s0, s1)
    # Static structure: kinematic body so it is a single articulation-free rigid prop in every backend.
    mass = steel_len * float(table.steel_linear_density)
    ua.rigid_body(root, mass, kinematic=True)
    ua.finalize(stage, root, mass)
    return path


def build_mc4_male(out_dir: Path, spec: MC4Spec = MC4, clearance: float | None = None, name: str = "mc4_male") -> Path:
    """Receptacle half with a 12-box coupling sleeve and a back stop. Static in T2 (clipped to a purlin)."""
    path = ua.asset_path(out_dir, name)
    stage, root = ua.new_stage(path, name, "electrical", QCODE_CONNECTOR, "mc4_connector_male")
    p_plastic = ua.physics_material(stage, MAT_PLASTIC)
    r_in, travel = float(spec.sleeve_inner_radius), float(spec.insertion_travel)
    r_out, body_len = float(spec.housing_radius), float(spec.housing_length)
    wall = r_out - r_in
    n = 12
    seg = 2 * (r_in + wall) * math.tan(math.pi / n) + 1e-4  # chord so adjacent boxes overlap
    vis, col = "/RootNode/Visuals", "/RootNode/Colliders"
    for k in range(n):
        a = 2 * math.pi * k / n
        c = (-travel / 2, (r_in + wall / 2) * math.cos(a), (r_in + wall / 2) * math.sin(a))
        ua.box_collider(stage, f"{col}/sleeve_{k:02d}", (travel, wall, seg), c, (math.degrees(a), 0, 0), p_plastic)
    back = body_len - travel
    visuals.mc4_male_visual(stage, vis, r_in, travel, r_out, body_len, float(spec.cable_od) / 2)
    ua.cylinder_collider(stage, f"{col}/body", r_out * 0.92, back, (-travel - back / 2, 0, 0), (0, 90, 0), p_plastic)
    ua.rigid_body(
        root,
        float(spec.housing_mass),
        com=(-body_len / 2, 0, 0),
        inertia=_x_cylinder_inertia(float(spec.housing_mass), r_out, body_len),
    )
    _attach_frame(stage, "/RootNode/Frames/mouth", (0, 0, 0))
    root.CreateAttribute("solarbench:radial_clearance", ua.Sdf.ValueTypeNames.Float).Set(
        float(spec.radial_clearance if clearance is None else clearance)
    )
    ua.finalize(stage, root, float(spec.housing_mass))
    return path


def build_mc4_female(
    out_dir: Path, spec: MC4Spec = MC4, clearance: float | None = None, name: str = "mc4_female"
) -> Path:
    """Insert half: cylindrical nose with a capsule lead-in chamfer at the tip, and a graspable body.

    The nose must be a cylinder over its full engagement length: a capsule of the bore radius would be almost
    all hemisphere and could tilt ~13 deg inside a 0.3 mm clearance (found by scripts/dev/mc4_insertion_probe.py).
    """
    path = ua.asset_path(out_dir, name)
    stage, root = ua.new_stage(path, name, "electrical", QCODE_CONNECTOR, "mc4_connector_female")
    _m_black, p_plastic = ua.look(stage, BLACK_PLASTIC), ua.physics_material(stage, MAT_PLASTIC)
    clr = float(spec.radial_clearance if clearance is None else clearance)
    r_nose = float(spec.sleeve_inner_radius) - clr
    ch = float(spec.nose_chamfer)
    travel, r_out, body_len = float(spec.insertion_travel), float(spec.housing_radius), float(spec.housing_length)
    vis, col = "/RootNode/Visuals", "/RootNode/Colliders"
    ua.cylinder_collider(
        stage, f"{col}/nose", r_nose, travel - ch, (ch + (travel - ch) / 2, 0, 0), (0, 90, 0), material=p_plastic
    )
    r_tip = r_nose - ch
    ua.capsule_collider(stage, f"{col}/nose_tip", r_tip, 1e-3, "X", (r_tip + 5e-4, 0, 0), material=p_plastic)
    grip = body_len - travel
    # Flat rear face + rigid cable stub: a finger past the housing wraps the cable and can push on the rear face
    # (form closure), as a technician does; a rounded rear forces friction-only pushing (~35-40 N with Dex3).
    ua.cylinder_collider(stage, f"{col}/body", r_out, grip, (travel + grip / 2, 0, 0), (0, 90, 0), material=p_plastic)
    r_cab, l_cab = float(spec.cable_od) / 2, float(spec.cable_stub_length)
    ua.capsule_collider(
        stage, f"{col}/cable_stub", r_cab, l_cab - 2 * r_cab, "X", (body_len + l_cab / 2, 0, 0), material=p_plastic
    )
    visuals.mc4_female_visual(stage, vis, r_nose, travel, r_out, body_len, r_cab, l_cab)
    mass = float(spec.housing_mass) + float(spec.cable_linear_density) * l_cab
    ua.rigid_body(root, mass, com=(body_len / 2, 0, 0), inertia=_x_cylinder_inertia(mass, r_out, body_len))
    _attach_frame(stage, "/RootNode/Frames/tip", (0, 0, 0))
    _attach_frame(stage, "/RootNode/Frames/grasp", (travel + grip / 2, 0, 0))
    _attach_frame(stage, "/RootNode/Frames/cable_exit", (body_len + float(spec.cable_stub_length), 0, 0))
    ua.finalize(stage, root, mass)
    return path


def _x_cylinder_inertia(m: float, r: float, h: float) -> tuple[float, float, float]:
    """Inertia of a solid cylinder whose axis is X."""
    ia, it = m * r * r / 2, m * (3 * r * r + h * h) / 12
    return (ia, it, it)


def _attach_frame(stage, path: str, pos) -> None:
    """A named reference frame (Xform) for task code: grasp points, connector tips, cable exits."""
    x = ua.UsdGeom.Xform.Define(stage, path)
    x.AddTranslateOp().Set(ua.Gf.Vec3d(*pos))


def _module_group(stage, path: str, g: dict, x: float, s: float, depth: float):
    """Xform placing module coordinates on the table (module +X up-slope, +Z normal, +Y -> -X world)."""
    ua.xform_group(stage, path, g["plane_point"](x, s, depth / 2), (math.degrees(g["tilt"]), 0, 0))
    return ua.xform_group(stage, f"{path}/o", (0, 0, 0), (0, 0, 90)).GetPath().pathString


def build_site_scenery(table: TableSpec, module: ModuleSpec, out_dir: Path, rows=(-1, 0, 1, 2),
                       tables=(-2, -1, 0, 1, 2),
                       row_pitch: float = 6.0, name: str = "low_mount_site", row_end: bool = False) -> Path:
    """Visual-only site context (no physics): textured ground and neighbouring populated tables.

    Row pitch 6.0 m = 2.38 m slope length / GCR 0.4 (DERIVED; docs/sources.md, section D). The simulated table at the
    environment origin is excluded so physics assets are not duplicated. ``row_end`` makes the simulated table the
    last one of its row (+X), as for end-clamp work approached from the row end (T3).
    """
    folder = out_dir / "scenes" / name
    tex = textures.ground(folder / "textures" / "ground_gravel_grass.png")
    # one visual-only table + modules, referenced for every neighbour
    unit = folder / "table_unit_visual.usda"
    st = ua.Usd.Stage.CreateNew(str(unit))
    ua.UsdGeom.SetStageUpAxis(st, ua.UsdGeom.Tokens.z)
    ua.UsdGeom.SetStageMetersPerUnit(st, 1.0)
    root = ua.UsdGeom.Xform.Define(st, "/RootNode").GetPrim()
    st.SetDefaultPrim(root)
    g = table_geometry(table, module)
    half = (g["row_len"] / 2) - 0.25
    n_st = max(2, int(math.ceil(g["row_len"] / float(table.station_spacing))) + 1)
    stations = [-half + k * (2 * half) / (n_st - 1) for k in range(n_st)]
    s0, s1 = g["purlin_s"][0] - 0.15, g["purlin_s"][-1] + 0.15
    visuals.table_visuals(st, "/RootNode/Structure", table, module, g, stations, s0, s1)
    rel = f"../../{module.name}/simready_usd/textures/{module.name}"
    back = f"{rel}_back.png" if module.glass_glass else None
    for i, (x, s) in enumerate(g["module_centres"]):
        visuals.module_visuals(st, _module_group(st, f"/RootNode/Modules/m{i}", g, x, s, float(module.depth)),
                               module, f"{rel}_front.png", back)
    st.GetRootLayer().Save()

    path = folder / f"{name}.usda"
    st = ua.Usd.Stage.CreateNew(str(path))
    ua.UsdGeom.SetStageUpAxis(st, ua.UsdGeom.Tokens.z)
    ua.UsdGeom.SetStageMetersPerUnit(st, 1.0)
    root = ua.UsdGeom.Xform.Define(st, "/RootNode").GetPrim()
    st.SetDefaultPrim(root)
    ground = ua.textured_look(st, "ground", f"./textures/{tex.name}", "gravel", roughness=0.95)
    ua.quad_mesh(st, "/RootNode/Ground", (300.0, 300.0), (0, 0, 0.002), material=ground, uv_repeat=(150.0, 150.0))
    pitch_x = g["row_len"] + 0.6
    for r in rows:
        for t in tables:
            if r == 0 and (t == 0 or (row_end and t > 0)):
                continue
            prim = ua.UsdGeom.Xform.Define(st, f"/RootNode/Tables/r{r + 5}_t{t + 5}")
            prim.AddTranslateOp().Set(ua.Gf.Vec3d(t * pitch_x, r * row_pitch, 0.0))
            prim.GetPrim().GetReferences().AddReference(f"./{unit.name}")
    # same-row neighbours of the simulated table share its structure line
    st.GetRootLayer().Save()
    return path


QCODE_ROBOT_BASE = "Q11012"  # "robot" (verified via wikidata.org API)


def build_end_clamp(module: ModuleSpec, out_dir: Path, name: str = "end_clamp_m8") -> Path:
    """K2-style end clamp as a 1-DoF articulation: fixed clamp body + M8 hex bolt on a revolute joint (+Z).

    Layout follows the Isaac robot-asset convention (and PhysX's rules): ``Base`` and ``Bolt`` are sibling rigid
    bodies (no nested rigid bodies) and the articulation root is a world fixed joint on ``Base``.

    Clamp frame: origin on the purlin top at the clamp centre, X along the module edge, +Y towards the module,
    Z along the bolt axis (module normal). Tightening = rotation about -Z (right-hand thread).
    """
    from solarbench.specs.params import BOLT

    path = ua.asset_path(out_dir, name)
    stage, root = ua.new_stage(path, name, "solar", QCODE_CLAMP, "pv_end_clamp")
    p_al, p_steel = ua.physics_material(stage, MAT_FRAME), ua.physics_material(stage, MAT_STEEL)
    D = float(module.depth)
    top = D + 0.003
    base = ua.UsdGeom.Xform.Define(stage, "/RootNode/Base").GetPrim()
    col = "/RootNode/Base/Colliders"
    ua.box_collider(stage, f"{col}/cap", (0.05, 0.026, 0.006), (0, 0.004, top), material=p_al)
    ua.box_collider(stage, f"{col}/web", (0.05, 0.006, D + 0.003), (0, -0.006, D / 2), material=p_al)
    ua.box_collider(stage, f"{col}/foot", (0.05, 0.03, 0.006), (0, -0.02, 0.003), material=p_al)
    m_al = ua.look(stage, visuals.ALUMINIUM)
    ua.box_mesh(stage, "/RootNode/Base/Visuals/cap", (0.05, 0.026, 0.006), (0, 0.004, top), material=m_al)
    ua.box_mesh(stage, "/RootNode/Base/Visuals/web", (0.05, 0.006, D + 0.003), (0, -0.006, D / 2), material=m_al)
    ua.box_mesh(stage, "/RootNode/Base/Visuals/foot", (0.05, 0.03, 0.006), (0, -0.02, 0.003), material=m_al)
    ua.rigid_body(base, 0.06, inertia=(2e-5, 2e-5, 2e-5))
    UsdPhysics = ua.UsdPhysics
    # fixed-base articulation as in Isaac robot assets: the root is a world fixed joint on the clamp base
    rj = UsdPhysics.FixedJoint.Define(stage, "/RootNode/Joints/root_joint")
    rj.CreateBody1Rel().SetTargets(["/RootNode/Base"])
    UsdPhysics.ArticulationRootAPI.Apply(rj.GetPrim())

    # bolt link: washer + DIN 933 hex head, origin at the washer bottom on the cap top
    z_b = top + 0.003
    bolt = ua.UsdGeom.Xform.Define(stage, "/RootNode/Bolt")
    bolt.AddTranslateOp().Set(ua.Gf.Vec3d(0, 0, z_b))
    m_bolt = ua.look(stage, visuals.STAINLESS)
    af, hh = float(BOLT.across_flats), float(BOLT.head_height)
    ua.cylinder_mesh(stage, "/RootNode/Bolt/washer", 0.008, 0.0016, (0, 0, 0.0008), material=m_bolt, segments=16)
    ua.cylinder_collider(stage, "/RootNode/Bolt/washer_col", 0.008, 0.0016, (0, 0, 0.0008), material=p_steel)
    # DIN 933 head: parallel 13 mm flats with a 0.6 mm top chamfer to ~11.8 AF (convex hull of 18 points)
    ua.hex_prism_mesh(stage, "/RootNode/Bolt/head", af, hh, 0.0016, material=m_bolt, collider=True,
                      phys_material=p_steel, top_scale=11.8 / 13.0)
    m = float(BOLT.head_mass)
    ua.rigid_body(bolt.GetPrim(), m, com=(0, 0, 0.004), inertia=(1e-6, 1e-6, 1e-6))
    j = UsdPhysics.RevoluteJoint.Define(stage, "/RootNode/Joints/bolt_joint")
    j.CreateBody0Rel().SetTargets(["/RootNode/Base"])
    j.CreateBody1Rel().SetTargets(["/RootNode/Bolt"])
    j.CreateAxisAttr("Z")
    j.CreateLocalPos0Attr(ua.Gf.Vec3f(0, 0, z_b))
    j.CreateLocalPos1Attr(ua.Gf.Vec3f(0, 0, 0))
    # MuJoCo regularises dry joint friction with a softness ~ 1/inertia; a near-rigid friction constraint keeps the
    # scheduled thread friction (task code) effective on this light DOF (ASSUMPTIONS P21).
    jp = j.GetPrim()
    jp.CreateAttribute("mjc:solreffriction", ua.Sdf.ValueTypeNames.Float2).Set(ua.Gf.Vec2f(0.004, 1.0))
    jp.CreateAttribute("mjc:solimpfriction", ua.Sdf.ValueTypeNames.FloatArray).Set([0.9999, 0.9999, 0.001, 0.5, 2.0])
    _attach_frame(stage, "/RootNode/Frames/head_top", (0, 0, z_b + 0.0016 + hh))
    ua.finalize(stage, root, 0.06 + m)
    return path


def build_husky_a300(out_dir: Path, name: str = "husky_a300_parked") -> Path:
    """Clearpath Husky A300 chassis as a parked (kinematic) base with an arm mount plate on the deck.

    Frame: origin on the ground under the chassis centre, +X forward. Dimensions from the A300 spec sheet.
    """
    from solarbench.specs import robots as R

    path = ua.asset_path(out_dir, name)
    stage, root = ua.new_stage(path, name, "robot", QCODE_ROBOT_BASE, "mobile_robot_base")
    L, W, H = float(R.HUSKY_A300_LENGTH), float(R.HUSKY_A300_WIDTH), float(R.HUSKY_A300_HEIGHT)
    clr, rw = float(R.HUSKY_A300_CLEARANCE), float(R.HUSKY_A300_WHEEL_DIAMETER) / 2
    dark = ua.look(stage, ua.Look("husky_body", (0.10, 0.10, 0.11), "plastic", roughness=0.55))
    accent = ua.look(stage, ua.Look("husky_accent", (0.85, 0.66, 0.08), "plastic", roughness=0.5))
    tyre = ua.look(stage, ua.Look("husky_tyre", (0.03, 0.03, 0.03), "rubber", roughness=0.9))
    plate = ua.look(stage, visuals.ALUMINIUM)
    p_steel = ua.physics_material(stage, MAT_STEEL)
    body_h = H - clr - 0.02
    ua.box_mesh(stage, "/RootNode/Visuals/chassis", (L * 0.84, W - 0.16, body_h), (0, 0, clr + body_h / 2),
                material=dark)
    ua.box_mesh(stage, "/RootNode/Visuals/bumper_front", (0.06, W - 0.1, 0.08), (L / 2 - 0.03, 0, clr + 0.10),
                material=accent)
    ua.box_mesh(stage, "/RootNode/Visuals/bumper_rear", (0.06, W - 0.1, 0.08), (-L / 2 + 0.03, 0, clr + 0.10),
                material=accent)
    ua.box_mesh(stage, "/RootNode/Visuals/deck", (L * 0.8, W - 0.18, 0.02), (0, 0, H - 0.01), material=plate)
    ua.box_collider(stage, "/RootNode/Colliders/chassis", (L * 0.84, W - 0.16, H - clr), (0, 0, clr + (H - clr) / 2),
                    material=p_steel)
    wb = 0.512  # ASSUMED wheelbase
    for i, (sx, sy) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
        c = (sx * wb / 2, sy * (W / 2 - 0.05), rw)
        ua.cylinder_mesh(stage, f"/RootNode/Visuals/wheel_{i}", rw, 0.1, c, (90, 0, 0), tyre, segments=28)
        ua.cylinder_collider(stage, f"/RootNode/Colliders/wheel_{i}", rw, 0.1, c, (90, 0, 0), material=p_steel)
    _attach_frame(stage, "/RootNode/Frames/arm_mount", (L / 2 - 0.20, 0, H))
    ua.rigid_body(root, float(R.HUSKY_A300_MASS), kinematic=True)
    ua.finalize(stage, root, float(R.HUSKY_A300_MASS))
    return path
