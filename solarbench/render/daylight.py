"""Daylight rig for Newton's OVRTX viewer: procedural sky dome (equirectangular) + sun.

Render-only. Replaces ViewerRTX's default grey dome/distant light for demo videos.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from solarbench import ASSET_ROOT

SKY = ASSET_ROOT / "scenes" / "low_mount_site" / "textures" / "sky_latlong.png"


def sky_texture(path: Path = SKY, w: int = 2048, h: int = 1024) -> Path:
    """Clear-sky gradient: deep blue zenith, pale hazy horizon, dull earth below the horizon."""
    v = np.linspace(0.0, 1.0, h)[:, None]  # 0 = zenith, 0.5 = horizon, 1 = nadir
    elev = np.clip(1.0 - 2.0 * v, -1.0, 1.0)
    zen, hor, gnd = np.array([0.20, 0.38, 0.72]), np.array([0.78, 0.85, 0.92]), np.array([0.60, 0.57, 0.51])
    t = np.clip(elev, 0, 1) ** 0.45
    sky = hor * (1 - t)[..., None] + zen * t[..., None]
    img = np.where((elev > 0)[..., None], sky, gnd * np.ones_like(sky))
    img = np.repeat(img, w, axis=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(path)
    return path


def install(sun_elevation_deg: float = 42.0, sun_azimuth_deg: float = 215.0) -> None:
    """Patch ViewerRTX so its default lights are the daylight rig (call before the viewer is created)."""
    from newton._src.viewer import viewer_rtx
    from pxr import Gf, Sdf, UsdGeom, UsdLux

    tex = str(sky_texture())

    def _daylight(self):
        dome = UsdLux.DomeLight.Define(self.stage, "/root/_RTXDomeLight")
        dome.CreateTextureFileAttr().Set(Sdf.AssetPath(tex))
        dome.CreateTextureFormatAttr().Set(UsdLux.Tokens.latlong)
        dome.GetIntensityAttr().Set(420.0)
        sun = UsdLux.DistantLight.Define(self.stage, "/root/_RTXDistantLight")
        sun.GetIntensityAttr().Set(1500.0)
        sun.GetAngleAttr().Set(0.53)
        sun.GetColorAttr().Set(Gf.Vec3f(1.0, 0.95, 0.86))
        xf = UsdGeom.Xform(sun.GetPrim())
        xf.ClearXformOpOrder()
        # distant light shines along its local -Z: tilt away from zenith, then turn to the sun azimuth
        xf.AddRotateXYZOp().Set(Gf.Vec3f(90.0 - sun_elevation_deg, 0.0, sun_azimuth_deg))

    viewer_rtx.ViewerRTX._add_default_lights = _daylight
