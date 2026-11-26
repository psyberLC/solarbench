"""Render-only cable geometry: a sagging cubic Bezier of fixed arc length, drawn as cylinder segments.

The *physics* of the lead is the tension-only tether (ASSUMPTIONS P6); this curve only visualises a cable of
the same free length so the image matches the model (it is not a cable simulation).
"""

from __future__ import annotations

import numpy as np


def _bezier(p0, c0, c1, p1, n):
    t = np.linspace(0.0, 1.0, n + 1)[:, None]
    return ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * c0 + 3 * (1 - t) * t * t * c1 + (t ** 3) * p1


def sagging_curve(p0, d0, p1, d1, length: float, n: int = 20) -> np.ndarray:
    """Points from p0 (leaving along d0) to p1 (arriving along -d1), sagging under gravity to ~``length``."""
    p0, p1, d0, d1 = (np.asarray(v, dtype=float) for v in (p0, p1, d0, d1))
    chord = np.linalg.norm(p1 - p0)
    a = 0.3 * max(chord, 0.05)
    down = np.array([0.0, 0.0, -1.0])
    lo, hi = 0.0, 2.0 * length
    pts = _bezier(p0, p0 + a * d0, p1 + a * d1, p1, n)
    for _ in range(30):  # bisection on the sag depth so the arc length matches the cable length
        sag = 0.5 * (lo + hi)
        pts = _bezier(p0, p0 + a * d0 + sag * down, p1 + a * d1 + sag * down, p1, n)
        if np.linalg.norm(np.diff(pts, axis=0), axis=1).sum() > length:
            hi = sag
        else:
            lo = sag
        if chord >= length:
            break
    return pts


def polyline_segments(pts: np.ndarray, overlap: float = 1.12):
    """Cylinder segments (centre, xyzw quaternion turning +Z onto the segment, length) along a polyline."""
    a, b = pts[:-1], pts[1:]
    d = b - a
    ln = np.linalg.norm(d, axis=1)
    keep = ln > 1e-6
    a, d, ln = a[keep], d[keep], ln[keep]
    u = d / ln[:, None]
    z = np.array([0.0, 0.0, 1.0])
    axis = np.cross(np.broadcast_to(z, u.shape), u)
    s = np.linalg.norm(axis, axis=1)
    c = u @ z
    ang = np.arctan2(s, c)
    axis = np.where(s[:, None] > 1e-9, axis / np.maximum(s, 1e-9)[:, None], np.array([1.0, 0.0, 0.0]))
    q = np.concatenate([axis * np.sin(ang / 2)[:, None], np.cos(ang / 2)[:, None]], axis=1)
    return a + d / 2, q, ln * overlap
