"""Minimal OpenUSD authoring helpers for SolarBench props.

Assets are authored procedurally from :mod:`solarbench.specs.params` so that every dimension
and mass traces back to a datasheet. Conventions: metres, kilograms, Z-up, one ``.usda`` per asset
with ``/RootNode`` as the default prim (SimReady Foundation convention).

Collision geometry uses analytic primitives (``UsdGeom.Cube`` / ``Capsule`` / ``Cylinder``) on the
``guide`` purpose so they parse as exact boxes/capsules in Newton/MuJoCo and PhysX alike; render
geometry is a separate ``UsdGeom.Mesh`` with normals.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass
from pathlib import Path

from pxr import Gf, Kind, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, Vt

ASSET_LICENSE = "CC-BY 4.0"
AUTHOR = "Radiant Robotics (SolarBench)"


@dataclass(frozen=True)
class Look:
    """A UsdPreviewSurface look."""

    name: str
    color: tuple[float, float, float]
    material_label: str = "plastic"
    roughness: float = 0.5
    metallic: float = 0.0
    opacity: float = 1.0


@dataclass(frozen=True)
class PhysMat:
    """A physics material (Coulomb friction, restitution)."""

    name: str
    static_friction: float
    dynamic_friction: float
    material_label: str = "plastic"
    restitution: float = 0.0


def asset_path(out_dir: Path, name: str) -> Path:
    """SimReady layout (NP.005): ``<name>/simready_usd/<name>.usda`` with one USD in the intermediate folder."""
    return out_dir / name / "simready_usd" / f"{name}.usda"


def new_stage(
    path: Path,
    asset_name: str,
    category: str,
    qcode: str,
    semantic: str,
    source_file: str = "solarbench/assets/build.py",
) -> tuple[Usd.Stage, Usd.Prim]:
    """Create a Z-up, metre/kilogram stage with a ``/RootNode`` component prim."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdPhysics.SetStageKilogramsPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/RootNode").GetPrim()
    stage.SetDefaultPrim(root)
    Usd.ModelAPI(root).SetKind(Kind.Tokens.component)
    Usd.ModelAPI(root).SetAssetName(asset_name)
    Usd.ModelAPI(root).SetAssetIdentifier(Sdf.AssetPath(f"./{path.name}"))
    Usd.ModelAPI(root).SetAssetVersion("0.1.0")
    _label(root, semantic)
    stage.GetRootLayer().customLayerData = {
        "SimReady_Metadata": {
            "asset_name": asset_name,
            "asset_type": "prop",
            "asset_license": ASSET_LICENSE,
            "author": AUTHOR,
            "category": category,
            "qcode": qcode,
            "source_file": source_file,
            "usd_date_generated": datetime.date.today().isoformat(),
        }
    }
    return stage, root


def _label(prim: Usd.Prim, label: str, taxonomy: str = "class") -> None:
    """Attach a semantic label (UsdSemantics LabelsAPI multiple-apply instance ``taxonomy``)."""
    from pxr import UsdSemantics

    UsdSemantics.LabelsAPI.Apply(prim, taxonomy).CreateLabelsAttr(Vt.TokenArray([label]))


def finalize(stage: Usd.Stage, root: Usd.Prim, mass: float) -> None:
    """Write bounding-box extents and mass into metadata, then save."""
    bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
    rng = bbox.ComputeWorldBound(root).ComputeAlignedRange()
    size = rng.GetSize()
    data = dict(stage.GetRootLayer().customLayerData)
    meta = dict(data["SimReady_Metadata"])
    meta["asset_extents"] = Gf.Vec3f(*size)
    meta["mass"] = float(mass)
    meta["rigid_body_count"] = sum(1 for p in stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI))
    data["SimReady_Metadata"] = meta
    stage.GetRootLayer().customLayerData = data
    stage.GetRootLayer().Save()


def look(stage: Usd.Stage, spec: Look) -> UsdShade.Material:
    path = f"/RootNode/Looks/{spec.name}"
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*spec.color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(spec.roughness)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(spec.metallic)
    shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(spec.opacity)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    _label(mat.GetPrim(), spec.material_label, "material")
    return mat


def physics_material(stage: Usd.Stage, spec: PhysMat) -> UsdShade.Material:
    path = f"/RootNode/PhysicsMaterials/{spec.name}"
    mat = UsdShade.Material.Define(stage, path)
    api = UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
    api.CreateStaticFrictionAttr(spec.static_friction)
    api.CreateDynamicFrictionAttr(spec.dynamic_friction)
    api.CreateRestitutionAttr(spec.restitution)
    _label(mat.GetPrim(), spec.material_label, "material")
    return mat


def box_mesh(
    stage: Usd.Stage,
    path: str,
    size: tuple[float, float, float],
    center=(0, 0, 0),
    rot_deg=(0, 0, 0),
    material: UsdShade.Material | None = None,
) -> UsdGeom.Mesh:
    """An axis-aligned box render mesh with per-face normals."""
    hx, hy, hz = (s / 2 for s in size)
    v = [
        (-hx, -hy, -hz),
        (hx, -hy, -hz),
        (hx, hy, -hz),
        (-hx, hy, -hz),
        (-hx, -hy, hz),
        (hx, -hy, hz),
        (hx, hy, hz),
        (-hx, hy, hz),
    ]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)]
    normals = [(0, 0, -1), (0, 0, 1), (0, -1, 0), (0, 1, 0), (1, 0, 0), (-1, 0, 0)]
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr([Gf.Vec3f(*p) for p in v])
    mesh.CreateFaceVertexCountsAttr([4] * 6)
    mesh.CreateFaceVertexIndicesAttr([i for f in faces for i in f])
    mesh.CreateNormalsAttr([Gf.Vec3f(*n) for n in normals for _ in range(4)])
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    mesh.CreateExtentAttr([Gf.Vec3f(-hx, -hy, -hz), Gf.Vec3f(hx, hy, hz)])
    _xform(mesh, center, rot_deg)
    if material is not None:
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
    return mesh


def cylinder_mesh(
    stage: Usd.Stage,
    path: str,
    radius: float,
    height: float,
    center=(0, 0, 0),
    rot_deg=(0, 0, 0),
    material: UsdShade.Material | None = None,
    segments: int = 24,
) -> UsdGeom.Mesh:
    """A Z-axis cylinder render mesh with smooth side normals and flat caps."""
    pts, counts, idx, nrm = [], [], [], []
    h = height / 2
    for k in range(segments):
        a = 2 * math.pi * k / segments
        pts += [(radius * math.cos(a), radius * math.sin(a), -h), (radius * math.cos(a), radius * math.sin(a), h)]
    for k in range(segments):
        a0, a1 = 2 * math.pi * k / segments, 2 * math.pi * (k + 1) / segments
        i0, i1 = 2 * k, 2 * ((k + 1) % segments)
        counts.append(4)
        idx += [i0, i1, i1 + 1, i0 + 1]
        nrm += [
            (math.cos(a0), math.sin(a0), 0),
            (math.cos(a1), math.sin(a1), 0),
            (math.cos(a1), math.sin(a1), 0),
            (math.cos(a0), math.sin(a0), 0),
        ]
    counts += [segments, segments]
    idx += [2 * k for k in reversed(range(segments))] + [2 * k + 1 for k in range(segments)]
    nrm += [(0, 0, -1)] * segments + [(0, 0, 1)] * segments
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr([Gf.Vec3f(*p) for p in pts])
    mesh.CreateFaceVertexCountsAttr(counts)
    mesh.CreateFaceVertexIndicesAttr(idx)
    mesh.CreateNormalsAttr([Gf.Vec3f(*n) for n in nrm])
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    lo = [min(p[i] for p in pts) for i in range(3)]  # exact for any segment count (e.g. hex bolt heads)
    hi = [max(p[i] for p in pts) for i in range(3)]
    mesh.CreateExtentAttr([Gf.Vec3f(*lo), Gf.Vec3f(*hi)])
    _xform(mesh, center, rot_deg)
    if material is not None:
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
    return mesh


def box_collider(
    stage: Usd.Stage, path: str, size, center=(0, 0, 0), rot_deg=(0, 0, 0), material: UsdShade.Material | None = None
) -> UsdGeom.Cube:
    """An exact box collider (unit cube scaled), invisible (guide purpose)."""
    cube = UsdGeom.Cube.Define(stage, path)
    cube.CreateSizeAttr(1.0)
    cube.CreateExtentAttr([Gf.Vec3f(-0.5), Gf.Vec3f(0.5)])
    _xform(cube, center, rot_deg, scale=size)
    _collider(cube, material)
    return cube


def capsule_collider(
    stage: Usd.Stage,
    path: str,
    radius: float,
    height: float,
    axis: str = "Z",
    center=(0, 0, 0),
    rot_deg=(0, 0, 0),
    material: UsdShade.Material | None = None,
) -> UsdGeom.Capsule:
    """An exact capsule collider; ``height`` is the cylindrical section length."""
    cap = UsdGeom.Capsule.Define(stage, path)
    cap.CreateRadiusAttr(radius)
    cap.CreateHeightAttr(height)
    cap.CreateAxisAttr(axis)
    e = [radius, radius, radius]
    e["XYZ".index(axis)] += height / 2
    cap.CreateExtentAttr([Gf.Vec3f(*[-x for x in e]), Gf.Vec3f(*e)])
    _xform(cap, center, rot_deg)
    _collider(cap, material)
    return cap


def cylinder_collider(
    stage: Usd.Stage,
    path: str,
    radius: float,
    height: float,
    center=(0, 0, 0),
    rot_deg=(0, 0, 0),
    material: UsdShade.Material | None = None,
) -> UsdGeom.Cylinder:
    cyl = UsdGeom.Cylinder.Define(stage, path)
    cyl.CreateRadiusAttr(radius)
    cyl.CreateHeightAttr(height)
    cyl.CreateAxisAttr("Z")
    cyl.CreateExtentAttr([Gf.Vec3f(-radius, -radius, -height / 2), Gf.Vec3f(radius, radius, height / 2)])
    _xform(cyl, center, rot_deg)
    _collider(cyl, material)
    return cyl


def _collider(geom: UsdGeom.Gprim, material: UsdShade.Material | None) -> None:
    geom.CreatePurposeAttr(UsdGeom.Tokens.guide)
    UsdPhysics.CollisionAPI.Apply(geom.GetPrim())
    if material is not None:
        UsdShade.MaterialBindingAPI.Apply(geom.GetPrim()).Bind(
            material, UsdShade.Tokens.weakerThanDescendants, "physics"
        )


def _xform(geom: UsdGeom.Xformable, center, rot_deg, scale=None) -> None:
    geom.AddTranslateOp().Set(Gf.Vec3d(*center))
    if any(rot_deg):
        geom.AddRotateXYZOp().Set(Gf.Vec3f(*rot_deg))
    if scale is not None:
        geom.AddScaleOp().Set(Gf.Vec3f(*scale))


def rigid_body(prim: Usd.Prim, mass: float, com=(0, 0, 0), inertia=None, kinematic: bool = False) -> None:
    """Make ``prim`` a rigid body with explicit mass properties (never density-derived)."""
    rb = UsdPhysics.RigidBodyAPI.Apply(prim)
    if kinematic:
        rb.CreateKinematicEnabledAttr(True)
    m = UsdPhysics.MassAPI.Apply(prim)
    m.CreateMassAttr(mass)
    m.CreateCenterOfMassAttr(Gf.Vec3f(*com))
    if inertia is not None:
        m.CreateDiagonalInertiaAttr(Gf.Vec3f(*inertia))
        m.CreatePrincipalAxesAttr(Gf.Quatf(1, 0, 0, 0))


def box_inertia(m: float, sx: float, sy: float, sz: float) -> tuple[float, float, float]:
    return (m / 12 * (sy * sy + sz * sz), m / 12 * (sx * sx + sz * sz), m / 12 * (sx * sx + sy * sy))


def cylinder_inertia(m: float, r: float, h: float) -> tuple[float, float, float]:
    ixy = m * (3 * r * r + h * h) / 12
    return (ixy, ixy, m * r * r / 2)


def textured_look(stage: Usd.Stage, name: str, texture_rel: str, material_label: str, roughness: float = 0.5,
                  metallic: float = 0.0) -> UsdShade.Material:
    """UsdPreviewSurface with a diffuse UsdUVTexture read through the ``st`` primvar (anchored ./ path)."""
    path = f"/RootNode/Looks/{name}"
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, f"{path}/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(roughness)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(metallic)
    reader = UsdShade.Shader.Define(stage, f"{path}/st_reader")
    reader.CreateIdAttr("UsdPrimvarReader_float2")
    reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
    tex = UsdShade.Shader.Define(stage, f"{path}/diffuse_texture")
    tex.CreateIdAttr("UsdUVTexture")
    tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath(texture_rel))
    tex.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("sRGB")
    tex.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("repeat")
    tex.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("repeat")
    tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(), "result")
    tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(tex.ConnectableAPI(), "rgb")
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    _label(mat.GetPrim(), material_label, "material")
    return mat


def quad_mesh(stage: Usd.Stage, path: str, size_xy: tuple[float, float], center=(0, 0, 0), rot_deg=(0, 0, 0),
              material: UsdShade.Material | None = None, uv_repeat: tuple[float, float] = (1.0, 1.0),
              flip: bool = False, uv_swap: bool = False) -> UsdGeom.Mesh:
    """A +Z-facing (or -Z if ``flip``) rectangle in its local XY plane with UVs.

    ``uv_swap`` maps image u to local Y and image v to local X (used for the module laminate, whose image is
    laid out width x length).
    """
    hx, hy = size_xy[0] / 2, size_xy[1] / 2
    pts = [(-hx, -hy, 0), (hx, -hy, 0), (hx, hy, 0), (-hx, hy, 0)]
    ru, rv = uv_repeat
    if uv_swap:  # noqa: SIM108  image u along local +Y, image v (bottom->top) along local +X
        st = [(0.0, 0.0), (0.0, rv), (ru, rv), (ru, 0.0)]
    else:
        st = [(0, 0), (ru, 0), (ru, rv), (0, rv)]
    idx = [0, 1, 2, 3] if not flip else [0, 3, 2, 1]
    nz = -1.0 if flip else 1.0
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr([Gf.Vec3f(*p) for p in pts])
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr(idx)
    mesh.CreateNormalsAttr([Gf.Vec3f(0, 0, nz)] * 4)
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    mesh.CreateExtentAttr([Gf.Vec3f(-hx, -hy, 0), Gf.Vec3f(hx, hy, 0)])
    pv = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray,
                                                  UsdGeom.Tokens.faceVarying)
    pv.Set([Gf.Vec2f(*st[i]) for i in idx])
    _xform(mesh, center, rot_deg)
    if material is not None:
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
    return mesh


def xform_group(stage: Usd.Stage, path: str, center=(0, 0, 0), rot_deg=(0, 0, 0)) -> UsdGeom.Xform:
    """A transform group; children are authored in its local frame (e.g. a profile laid along +X)."""
    x = UsdGeom.Xform.Define(stage, path)
    _xform(x, center, rot_deg)
    return x


def c_profile(stage: Usd.Stage, group: str, length: float, depth: float, flange: float, lip: float, t: float,
              material: UsdShade.Material, open_dir: int = 1) -> None:
    """Cold-formed C (lipped channel) along local X as 5 plates: web in local -Y (or +Y), opening to ``open_dir``."""
    w = -open_dir * (flange / 2 - t / 2)
    box_mesh(stage, f"{group}/web", (length, t, depth), (0, w, 0), material=material)
    for s, nm in ((1, "top"), (-1, "bottom")):
        box_mesh(stage, f"{group}/flange_{nm}", (length, flange, t), (0, 0, s * (depth / 2 - t / 2)), material=material)
        box_mesh(stage, f"{group}/lip_{nm}", (length, t, lip),
                 (0, open_dir * (flange / 2 - t / 2), s * (depth / 2 - lip / 2)), material=material)


def hex_prism_points(across_flats: float, height: float, z0: float = 0.0, top_scale: float = 1.0,
                     chamfer_height: float = 0.0006) -> list[tuple[float, float, float]]:
    """Vertices of a hexagonal prism along +Z; ``top_scale`` < 1 gives a chamfered (frustum) top."""
    r = across_flats / 2 / math.cos(math.pi / 6)

    def ring(s):
        return [(s * r * math.cos(math.pi / 6 + k * math.pi / 3), s * r * math.sin(math.pi / 6 + k * math.pi / 3))
                for k in range(6)]

    if top_scale >= 1.0:
        return [(x, y, z0) for x, y in ring(1.0)] + [(x, y, z0 + height) for x, y in ring(1.0)]
    # parallel flats up to the chamfer, then a short chamfer to the reduced top (DIN 933 style)
    zc = z0 + height - chamfer_height
    return ([(x, y, z0) for x, y in ring(1.0)] + [(x, y, zc) for x, y in ring(1.0)]
            + [(x, y, z0 + height) for x, y in ring(top_scale)])


def hex_prism_mesh(stage: Usd.Stage, path: str, across_flats: float, height: float, z0: float = 0.0,
                   material: UsdShade.Material | None = None, collider: bool = False,
                   phys_material: UsdShade.Material | None = None, top_scale: float = 1.0) -> UsdGeom.Mesh:
    """Hex prism mesh; as a collider it uses a convex-hull approximation (exact for a convex prism/frustum)."""
    pts = hex_prism_points(across_flats, height, z0, top_scale)
    rings = len(pts) // 6
    faces = [[5, 4, 3, 2, 1, 0], [6 * (rings - 1) + k for k in range(6)]]
    for r in range(rings - 1):
        faces += [[6 * r + k, 6 * r + (k + 1) % 6, 6 * (r + 1) + (k + 1) % 6, 6 * (r + 1) + k] for k in range(6)]
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr([Gf.Vec3f(*p) for p in pts])
    mesh.CreateFaceVertexCountsAttr([len(f) for f in faces])
    mesh.CreateFaceVertexIndicesAttr([i for f in faces for i in f])
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    nrm = [(0, 0, -1)] * 6 + [(0, 0, 1)] * 6
    for r in range(rings - 1):
        tilt = 0.0 if r == 0 else 0.6  # chamfer faces lean inward
        for k in range(6):
            a = math.pi / 6 + (k + 0.5) * math.pi / 3
            nrm += [(math.cos(a) * math.cos(tilt), math.sin(a) * math.cos(tilt), math.sin(tilt))] * 4
    mesh.CreateNormalsAttr([Gf.Vec3f(*n) for n in nrm])
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    mesh.CreateExtentAttr([Gf.Vec3f(*lo), Gf.Vec3f(*hi)])
    if material is not None:
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
    if collider:  # the same mesh renders and collides (a duplicate collider mesh would violate VG.008)
        UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
        UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim()).CreateApproximationAttr(UsdPhysics.Tokens.convexHull)
        if phys_material is not None:
            UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(phys_material, UsdShade.Tokens.weakerThanDescendants,
                                                                   "physics")
    return mesh
