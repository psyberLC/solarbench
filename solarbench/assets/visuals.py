"""Render geometry for SolarBench assets (visual only: colliders and mass properties live in build.py).

Detail goes here — extrusion profiles, cell textures, split junction boxes, clamps — while collision stays
analytic so physics cost and cross-backend behaviour are unaffected by visual fidelity.
Materials are satin/matte PBR values (roughness >= 0.4 for structural metal) rather than mirror finishes.
"""

from __future__ import annotations

import math

from solarbench.specs import ModuleSpec, TableSpec

from . import textures
from . import usd_author as ua

# Satin anodised aluminium, dull hot-dip galvanised steel, matte plastics.
ALUMINIUM = ua.Look("anodized_aluminium", (0.72, 0.73, 0.75), "aluminium", roughness=0.5, metallic=0.6)
GALV_STEEL = ua.Look("galvanized_steel", (0.56, 0.58, 0.59), "steel", roughness=0.65, metallic=0.45)
BLACK_PLASTIC = ua.Look("black_plastic", (0.035, 0.035, 0.04), "plastic", roughness=0.7)
STAINLESS = ua.Look("stainless_bolt", (0.62, 0.62, 0.64), "steel", roughness=0.4, metallic=0.8)
GLASS_EDGE = ua.Look("glass_edge", (0.12, 0.16, 0.17), "glass", roughness=0.2)
BACKSHEET = ua.Look("backsheet", (0.88, 0.88, 0.86), "plastic", roughness=0.75)

T = 0.002  # visual sheet thickness of extrusions / cold-formed profiles [m]


def module_textures(spec: ModuleSpec, tex_dir) -> tuple[str, str | None]:
    """Generate front/back laminate textures; returns paths relative to the asset's USD folder."""
    inset = float(spec.frame_width) - float(spec.frame_lip)
    hpbc = spec.cell_tech == "hpbc"
    front = textures.module_cells(tex_dir / f"{spec.name}_front.png", float(spec.length), float(spec.width), inset,
                                  back_contact=hpbc)
    back = None
    if spec.glass_glass:
        back = textures.module_cells(tex_dir / f"{spec.name}_back.png", float(spec.length), float(spec.width),
                                     inset, back_contact=hpbc, backside=True, seed=7)
    rel = lambda p: f"./textures/{p.name}" if p is not None else None  # noqa: E731
    return rel(front), rel(back)


def module_visuals(stage, prefix: str, spec: ModuleSpec, front_tex: str, back_tex: str | None) -> None:
    """Module render geometry in module coordinates (centre origin, +X to the junction-box edge, +Z front)."""
    L, W, D = float(spec.length), float(spec.width), float(spec.depth)
    fw, lip, lt = float(spec.frame_width), float(spec.frame_lip), float(spec.laminate_thickness)
    m_al, m_black, m_edge = (ua.look(stage, x) for x in (ALUMINIUM, BLACK_PLASTIC, GLASS_EDGE))
    m_front = ua.textured_look(stage, f"{spec.name}_glass_front", front_tex, "glass", roughness=0.08)
    m_back = (ua.textured_look(stage, f"{spec.name}_glass_back", back_tex, "glass", roughness=0.25)
              if back_tex else ua.look(stage, BACKSHEET))
    lam_top = D / 2 - 0.002
    lam_bot = lam_top - lt
    vis_x, vis_y = L - 2 * (fw - lip), W - 2 * (fw - lip)
    ua.quad_mesh(stage, f"{prefix}/laminate_front", (vis_x, vis_y), (0, 0, lam_top), material=m_front, uv_swap=True)
    ua.quad_mesh(stage, f"{prefix}/laminate_back", (vis_x, vis_y), (0, 0, lam_bot), material=m_back, flip=True,
                 uv_swap=True)
    ua.box_mesh(stage, f"{prefix}/laminate_edge", (vis_x - 0.002, vis_y - 0.002, lt * 0.9), (0, 0, lam_top - lt / 2),
                material=m_edge)
    # Frame: box-section extrusion = outer wall + top lip over the glass + inner wall + bottom flange.
    sides = {  # name: (length, along_x, sign)
        "frame_long_pos": (L, True, 1), "frame_long_neg": (L, True, -1),
        "frame_short_pos": (W, False, 1), "frame_short_neg": (W, False, -1),
    }
    for name, (length, along_x, sgn) in sides.items():
        half = (W if along_x else L) / 2
        g = ua.xform_group(stage, f"{prefix}/{name}", rot_deg=(0, 0, 0 if along_x else 90))
        p = g.GetPath().pathString
        # local Y points outward for sgn=+1
        oy = sgn * half
        ua.box_mesh(stage, f"{p}/outer_wall", (length, T, D), (0, oy - sgn * T / 2, 0), material=m_al)
        ua.box_mesh(stage, f"{p}/top_lip", (length, lip + T, T), (0, oy - sgn * (lip + T) / 2, D / 2 - T / 2),
                    material=m_al)
        ua.box_mesh(stage, f"{p}/inner_wall", (length - 2 * fw, T, D / 2 + lam_bot),
                    (0, oy - sgn * (fw - T / 2), (lam_bot - D / 2) / 2), material=m_al)
        ua.box_mesh(stage, f"{p}/bottom_flange", (length, fw, T), (0, oy - sgn * fw / 2, -D / 2 + T / 2),
                    material=m_al)
    # Split junction boxes (half-cut modules) with cable glands.
    xj = L / 2 - float(spec.jbox_from_top_edge)
    for k, yj in enumerate((-0.32, 0.0, 0.32)):
        zc = lam_bot - 0.009
        ua.box_mesh(stage, f"{prefix}/jbox_{k}", (0.055, 0.105, 0.016), (xj, yj, zc), material=m_black)
        ua.cylinder_mesh(stage, f"{prefix}/jbox_{k}_gland", 0.006, 0.02, (xj, yj + 0.06, zc), (90, 0, 0), m_black,
                         segments=12)


def clamp_visual(stage, path: str, kind: str, center, rot_deg, frame_depth: float) -> None:
    """K2-style aluminium mid/end clamp with an M8 hex bolt (13 mm AF), in clamp coordinates:
    local X along the module edge, local Y across the gap (end clamp: +Y towards the module), local Z normal;
    origin on the purlin top at the clamp centre."""
    # rotateXYZ applies X before Z, so yaw about the module normal goes in a nested group under the tilt
    ua.xform_group(stage, path, center, (rot_deg[0], 0, 0))
    p = ua.xform_group(stage, f"{path}/yaw", (0, 0, 0), (0, 0, rot_deg[2])).GetPath().pathString
    m_al, m_bolt = ua.look(stage, ALUMINIUM), ua.look(stage, STAINLESS)
    top = frame_depth + 0.003
    if kind == "mid":
        ua.box_mesh(stage, f"{p}/cap", (0.05, 0.044, 0.006), (0, 0, top), material=m_al)
        ua.box_mesh(stage, f"{p}/web", (0.05, 0.016, frame_depth), (0, 0, frame_depth / 2), material=m_al)
    else:
        ua.box_mesh(stage, f"{p}/cap", (0.05, 0.026, 0.006), (0, 0.004, top), material=m_al)
        ua.box_mesh(stage, f"{p}/web", (0.05, 0.006, frame_depth + 0.003), (0, -0.006, frame_depth / 2), material=m_al)
        ua.box_mesh(stage, f"{p}/foot", (0.05, 0.03, 0.006), (0, -0.02, 0.003), material=m_al)
    ua.cylinder_mesh(stage, f"{p}/washer", 0.008, 0.0016, (0, 0, top + 0.0038), material=m_bolt, segments=16)
    ua.cylinder_mesh(stage, f"{p}/bolt_head", 0.0075, 0.0053, (0, 0, top + 0.0073), material=m_bolt, segments=6)


def table_visuals(stage, prefix: str, table: TableSpec, module: ModuleSpec, g: dict, stations, s0: float, s1: float,
                  with_clamps: bool = True) -> None:
    """Cold-formed galvanised substructure: C purlins, C rafters, sigma ram posts, diagonal braces, clamps."""
    m_steel = ua.look(stage, GALV_STEEL)
    tilt = math.degrees(g["tilt"])
    ph, pw, ps = float(table.purlin_height), float(table.purlin_width), float(table.post_section)
    for i, s in enumerate(g["purlin_s"]):
        grp = ua.xform_group(stage, f"{prefix}/purlin_{i}", g["plane_point"](0.0, s, -ph / 2), (tilt, 0, 0))
        ua.c_profile(stage, grp.GetPath().pathString, g["row_len"] + 0.2, ph, pw, 0.02, T, m_steel)
    mid = 0.5 * (s0 + s1)
    for k, x in enumerate(stations):
        grp = ua.xform_group(stage, f"{prefix}/rafter_{k}", g["plane_point"](x, mid, -ph - ps / 2), (0, -tilt, 90))
        ua.c_profile(stage, grp.GetPath().pathString, s1 - s0, ps, 0.04, 0.015, T, m_steel)
        tops = []
        for j, s in enumerate((s0 + 0.1, s1 - 0.1)):
            top = g["plane_point"](x, s, -ph - ps)
            tops.append(top)
            h = top[2] + 0.4  # ram posts continue ~0.4 m below grade (hidden)
            grp = ua.xform_group(stage, f"{prefix}/post_{k}_{j}", (x, top[1], top[2] - h / 2), (0, -90, 0))
            ua.c_profile(stage, grp.GetPath().pathString, h, 0.12, 0.06, 0.02, 0.0025, m_steel)
        # diagonal brace from the rear post to the rafter
        p0 = (x, tops[1][1], 0.45 * tops[1][2])
        p1 = g["plane_point"](x, mid - 0.25, -ph - ps)
        dy, dz = p1[1] - p0[1], p1[2] - p0[2]
        ln, phi = math.hypot(dy, dz), math.degrees(math.atan2(dz, dy))
        c = (x + 0.05, (p0[1] + p1[1]) / 2, (p0[2] + p1[2]) / 2)
        grp = ua.xform_group(stage, f"{prefix}/brace_{k}", c, (0, -phi, 90))
        ua.c_profile(stage, grp.GetPath().pathString, ln, 0.06, 0.03, 0.01, T, m_steel)
    if not with_clamps:
        return
    D, gap = float(module.depth), float(table.module_gap)
    edges = [g["module_centres"][0][0] - float(module.width) / 2 - gap / 2]
    edges += [xc + float(module.width) / 2 + gap / 2 for xc, _ in g["module_centres"][: table.modules_per_row]]
    for i, s in enumerate(g["purlin_s"]):
        for k, xe in enumerate(edges):
            kind = "end" if k in (0, len(edges) - 1) else "mid"
            yaw = 0 if k != 0 else 180  # end clamps face the module
            clamp_visual(stage, f"{prefix}/clamp_{i}_{k}", kind, g["plane_point"](xe, s, 0.0), (tilt, 0, 90 + yaw), D)


# MC4-Evo 2 style connector details (visual only; collision is the validated cylinder/sleeve model).
CONNECTOR = ua.Look("connector_ppo", (0.028, 0.028, 0.03), "plastic", roughness=0.45)
CABLE = ua.Look("pv_cable_jacket", (0.02, 0.02, 0.022), "rubber", roughness=0.6)
RECESS = ua.Look("connector_recess", (0.11, 0.11, 0.12), "plastic", roughness=0.6)
POL_POS = ua.Look("polarity_red", (0.62, 0.06, 0.05), "plastic", roughness=0.5)
POL_NEG = ua.Look("polarity_blue", (0.06, 0.18, 0.55), "plastic", roughness=0.5)


def _x_cyl(stage, path, r, x0, x1, look, segments=24):
    ua.cylinder_mesh(stage, path, r, x1 - x0, ((x0 + x1) / 2, 0, 0), (0, 90, 0), look, segments=segments)


def _ribs(stage, prefix, r, x0, x1, n, look, h=0.0009, w=0.0016):
    for k in range(n):
        a = 2 * math.pi * k / n
        ua.box_mesh(stage, f"{prefix}_{k:02d}", (x1 - x0, h, w), ((x0 + x1) / 2, (r + h / 2) * math.cos(a),
                    (r + h / 2) * math.sin(a)), (math.degrees(a), 0, 0), look)


def mc4_female_visual(stage, prefix: str, r_nose: float, travel: float, r_out: float, body_len: float,
                      r_cable: float, stub: float) -> None:
    """Insert half seen from outside: nose, two snap-latch arms, ribbed grip, gland nut, strain relief, + lead."""
    c, rec, cab, red = (ua.look(stage, x) for x in (CONNECTOR, RECESS, CABLE, POL_POS))
    _x_cyl(stage, f"{prefix}/nose", r_nose, 0.0, travel, c)
    for s in (1, -1):  # latch arms ride over the male sleeve and hook into its windows
        ua.box_mesh(stage, f"{prefix}/latch_{'l' if s > 0 else 'r'}", (0.018, 0.0016, 0.0062),
                    (0.017, s * (r_out + 0.0010), 0), material=c)
        ua.box_mesh(stage, f"{prefix}/latch_hook_{'l' if s > 0 else 'r'}", (0.003, 0.0025, 0.0062),
                    (0.0095, s * (r_out + 0.0004), 0), material=c)
    grip_end = body_len - 0.017
    _x_cyl(stage, f"{prefix}/grip", r_out, travel, grip_end, c)
    _ribs(stage, f"{prefix}/grip_rib", r_out, travel + 0.004, grip_end - 0.002, 10, c)
    _x_cyl(stage, f"{prefix}/nut", r_out + 0.0006, grip_end, body_len, c, segments=16)
    _ribs(stage, f"{prefix}/nut_rib", r_out + 0.0006, grip_end + 0.001, body_len - 0.001, 16, c, h=0.0012, w=0.0022)
    _x_cyl(stage, f"{prefix}/gland", 0.0062, body_len, body_len + 0.008, c)
    _x_cyl(stage, f"{prefix}/relief", 0.0042, body_len + 0.008, body_len + 0.016, c)
    _x_cyl(stage, f"{prefix}/cable", r_cable, body_len + 0.016, body_len + stub, cab, segments=12)
    _x_cyl(stage, f"{prefix}/polarity", r_cable + 0.0004, body_len + 0.022, body_len + 0.032, red, segments=12)
    _x_cyl(stage, f"{prefix}/nose_face", r_nose * 0.55, -0.0003, 0.0002, rec)  # socket contact opening


def mc4_male_visual(stage, prefix: str, r_in: float, travel: float, r_out: float, body_len: float,
                    r_cable: float) -> None:
    """Receptacle half: coupling sleeve with latch windows, ribbed body, gland nut, strain relief, - lead."""
    c, rec, cab, blue = (ua.look(stage, x) for x in (CONNECTOR, RECESS, CABLE, POL_NEG))
    _x_cyl(stage, f"{prefix}/sleeve", r_out, -travel, 0.0, c)
    _x_cyl(stage, f"{prefix}/mouth", r_in, -0.0006, 0.0003, rec)
    for s in (1, -1):
        ua.box_mesh(stage, f"{prefix}/window_{'l' if s > 0 else 'r'}", (0.006, 0.0006, 0.0058),
                    (-0.010, s * (r_out + 0.0001), 0), material=rec)
    nut0 = -(body_len - 0.017)
    _x_cyl(stage, f"{prefix}/body", r_out * 0.95, nut0, -travel, c)
    _ribs(stage, f"{prefix}/body_rib", r_out * 0.95, nut0 + 0.002, -travel - 0.003, 10, c)
    _x_cyl(stage, f"{prefix}/nut", r_out + 0.0006, -body_len, nut0, c, segments=16)
    _ribs(stage, f"{prefix}/nut_rib", r_out + 0.0006, -body_len + 0.001, nut0 - 0.001, 16, c, h=0.0012, w=0.0022)
    _x_cyl(stage, f"{prefix}/gland", 0.0062, -body_len - 0.008, -body_len, c)
    _x_cyl(stage, f"{prefix}/relief", 0.0042, -body_len - 0.016, -body_len - 0.008, c)
    _x_cyl(stage, f"{prefix}/cable", r_cable, -body_len - 0.06, -body_len - 0.016, cab, segments=12)
    _x_cyl(stage, f"{prefix}/polarity", r_cable + 0.0004, -body_len - 0.032, -body_len - 0.022, blue, segments=12)
