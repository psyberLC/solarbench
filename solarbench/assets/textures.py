"""Procedural textures (PNG) for SolarBench assets. Deterministic (fixed seeds), no external downloads.

Cell layouts follow the datasheets: 144 half-cut cells in 6 columns x 24 rows (2 x 72), cell pitch from the
module dimensions. Back-contact (HPBC) modules have no front busbars; TOPCon modules show 16 busbars.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

PX_PER_M = 900  # ~1.1 mm per pixel


def _save(img: np.ndarray, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(path, optimize=True)
    return path


def module_cells(
    path: Path,
    length: float,
    width: float,
    frame_inset: float,
    back_contact: bool,
    backside: bool = False,
    cols: int = 6,
    rows: int = 24,
    seed: int = 0,
) -> Path:
    """Laminate texture; image x = module width (Y), image y = module length (X, top edge first)."""
    rng = np.random.default_rng(seed)
    W, H = int(width * PX_PER_M), int(length * PX_PER_M)
    if backside:  # seen through rear glass: metallised cell backs, translucent gaps
        cell_rgb, gap_rgb = np.array([62, 64, 70]), np.array([150, 152, 155])
    elif back_contact:  # HPBC: uniform black front, dark grey gaps (glass-glass)
        cell_rgb, gap_rgb = np.array([14, 16, 22]), np.array([70, 72, 78])
    else:  # TOPCon: dark blue cells on white backsheet
        cell_rgb, gap_rgb = np.array([22, 30, 52]), np.array([225, 226, 228])
    img = np.empty((H, W, 3), dtype=np.float32)
    img[:] = gap_rgb
    m = int(frame_inset * PX_PER_M) + 6  # cell-free margin inside the frame
    gap = 3  # ~2.5 mm inter-cell gap
    mid_gap = 9  # wider gap between the two half-module strings
    cw = (W - 2 * m - (cols - 1) * gap) / cols
    ch = (H - 2 * m - (rows - 2) * gap - mid_gap) / rows
    yy, xx = np.mgrid[0:H, 0:W]
    for r in range(rows):
        y0 = m + r * (ch + gap) + (mid_gap - gap if r >= rows // 2 else 0)
        for c in range(cols):
            x0 = m + c * (cw + gap)
            sl = (slice(int(y0), int(y0 + ch)), slice(int(x0), int(x0 + cw)))
            shade = cell_rgb * (0.92 + 0.12 * rng.random())  # per-cell variation
            img[sl] = shade
            if not back_contact and not backside:  # 16 busbars along the cell's long axis (module X)
                for k in range(16):
                    bx = int(x0 + (k + 0.5) * cw / 16)
                    img[sl[0], bx : bx + 1] = [150, 152, 158]
    # subtle large-scale tint so glass does not look perfectly uniform
    tint = 1.0 + 0.04 * np.sin(xx / 97.0) * np.cos(yy / 131.0)
    img *= tint[..., None]
    return _save(img, path)


def ground(path: Path, size_px: int = 1024, seed: int = 1) -> Path:
    """Tileable gravel with sparse dry-grass patches (typical utility-site ground cover)."""
    rng = np.random.default_rng(seed)

    def noise(scale: int) -> np.ndarray:
        n = rng.random((size_px // scale + 2, size_px // scale + 2))
        img = Image.fromarray((n * 255).astype(np.uint8)).resize((size_px + 2 * scale, size_px + 2 * scale),
                                                                  Image.BICUBIC)
        return np.asarray(img, dtype=np.float32)[scale : scale + size_px, scale : scale + size_px] / 255.0

    fine, mid, coarse = noise(2), noise(8), noise(64)
    gravel = np.stack([150 + 50 * fine + 25 * mid, 142 + 48 * fine + 22 * mid, 128 + 44 * fine + 18 * mid], -1)
    stones = (noise(3) > 0.82)[..., None]
    gravel = np.where(stones, gravel * 0.72, gravel)
    grass_mask = np.clip((coarse - 0.68) * 3.0, 0, 1)[..., None] * (0.3 + 0.4 * noise(4))[..., None]
    grass = np.stack([118 + 30 * fine, 116 + 28 * fine, 84 + 16 * fine], -1)  # dry, desaturated
    img = gravel * (1 - grass_mask) + grass * grass_mask
    return _save(img, path)
