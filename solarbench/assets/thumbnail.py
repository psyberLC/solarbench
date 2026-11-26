"""Render a 256x256 SimReady thumbnail (SR.002) from an asset's render meshes, without RTX.

Writes ``.thumbs/256x256/<file>.png`` next to the asset, as the SimReady thumbnail rule requires.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402
from pxr import Usd, UsdGeom, UsdShade  # noqa: E402


def _mesh_color(prim: Usd.Prim) -> tuple[float, float, float]:
    mat, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
    if mat:
        for child in mat.GetPrim().GetChildren():
            inp = UsdShade.Shader(child).GetInput("diffuseColor")
            if inp and inp.Get() is not None:
                return tuple(inp.Get())
    return (0.6, 0.6, 0.6)


def render_thumbnail(
    usd_path: Path, size_px: int = 256, elev: float = 28.0, azim: float = -55.0, out_path: Path | None = None
) -> Path:
    stage = Usd.Stage.Open(str(usd_path))
    cache = UsdGeom.XformCache()
    polys, colors = [], []
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh) or UsdGeom.Imageable(prim).ComputePurpose() == UsdGeom.Tokens.guide:
            continue
        mesh = UsdGeom.Mesh(prim)
        pts = np.array(mesh.GetPointsAttr().Get(), dtype=float)
        xf = np.array(cache.GetLocalToWorldTransform(prim), dtype=float)
        pts = (np.c_[pts, np.ones(len(pts))] @ xf)[:, :3]
        counts, idx = mesh.GetFaceVertexCountsAttr().Get(), mesh.GetFaceVertexIndicesAttr().Get()
        col = _mesh_color(prim)
        k = 0
        for c in counts:
            polys.append(pts[list(idx[k : k + c])])
            colors.append(col)
            k += c
    allp = np.concatenate(polys)
    lo, hi = allp.min(0), allp.max(0)
    ctr, rad = (lo + hi) / 2, (hi - lo).max() / 2
    fig = plt.figure(figsize=(size_px / 100, size_px / 100), dpi=100)
    ax = fig.add_subplot(projection="3d", computed_zorder=False)
    ax.add_collection3d(Poly3DCollection(polys, facecolors=colors, edgecolors=(0, 0, 0, 0.15), linewidths=0.2))
    for set_lim, c in zip((ax.set_xlim, ax.set_ylim, ax.set_zlim), ctr, strict=True):
        set_lim(c - rad, c + rad)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    fig.subplots_adjust(0, 0, 1, 1)
    if out_path is None:
        out_path = usd_path.parent / ".thumbs" / "256x256" / f"{usd_path.name}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)
    return out_path
