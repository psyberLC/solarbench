"""Scene layout for low-mount tasks, derived from the same table geometry the assets are built from.

All poses are in the environment frame (= table frame): +X along the row, +Y up-slope (front -> rear),
+Z up. Quaternions are ``(x, y, z, w)`` (Isaac Lab 3.0 convention).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.spatial.transform import Rotation

from solarbench import ASSET_ROOT  # noqa: F401  (re-exported for task configs)
from solarbench.assets.build import table_geometry
from solarbench.specs import MC4, ModuleSpec, TableSpec


def asset_usd(name: str) -> str:
    path = ASSET_ROOT / name / "simready_usd" / f"{name}.usda"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing: run `.venv/bin/python scripts/build_assets.py`")
    return str(path)


def _quat(matrix: np.ndarray) -> tuple[float, float, float, float]:
    return tuple(float(x) for x in Rotation.from_matrix(matrix).as_quat())  # scipy is xyzw


@dataclass(frozen=True)
class Pose:
    pos: tuple[float, float, float]
    rot: tuple[float, float, float, float]


@dataclass(frozen=True)
class ConnectorSiteCfg:
    """Where the clipped (male) half sits, relative to the target module.

    ``dx``: offset along the row from the module centre line (negative = robot's right when the robot
    faces the table from the rear); ``s``: slope distance of the mouth from the module's lower edge;
    ``n``: offset below the module back plane (negative = below).
    """

    dx: float = -0.10
    s: float = 1.95
    n: float = -0.20


class LowMountLayout:
    def __init__(
        self, table: TableSpec, module: ModuleSpec, target_index: int = 1, site: ConnectorSiteCfg | None = None
    ):
        self.table, self.module, self.site = table, module, site or ConnectorSiteCfg()
        self.g = table_geometry(table, module)
        self.x_c, self.s_c = self.g["module_centres"][target_index]
        self.up = np.array(self.g["up"])
        self.normal = np.array(self.g["normal"])

    # --- module -------------------------------------------------------------------------------------
    def module_pose(self, index: int | None = None) -> Pose:
        x, s = (self.x_c, self.s_c) if index is None else self.g["module_centres"][index]
        pos = self.g["plane_point"](x, s, float(self.module.depth) / 2)
        # module +X -> up-slope, +Z -> front normal, +Y = Z x X = -world X
        rot = np.column_stack([self.up, np.cross(self.normal, self.up), self.normal])
        return Pose(tuple(float(x) for x in pos), _quat(rot))

    def junction_box_exit(self) -> np.ndarray:
        """Cable exit at the bottom of the junction box (world, env frame)."""
        s = float(self.module.length) - float(self.module.jbox_from_top_edge)
        return np.array(self.g["plane_point"](self.x_c, s, -0.005))

    # --- connector ----------------------------------------------------------------------------------
    def connector_axis(self) -> np.ndarray:
        """Mouth axis of the clipped male half: along the row (leads are run and clipped along the rail),
        pointing to -X, i.e. to the right of a robot standing behind the table facing -Y."""
        return np.array([-1.0, 0.0, 0.0])

    def male_pose(self) -> Pose:
        pos = self.g["plane_point"](self.x_c + self.site.dx, self.site.s, self.site.n)
        return Pose(tuple(float(x) for x in pos), (0.0, 0.0, 1.0, 0.0))  # yaw 180 deg: +X -> -X

    def female_pose(self, depth: float) -> Pose:
        """Female pose with its tip ``depth`` metres inside the sleeve (negative = outside)."""
        m = self.male_pose()
        pos = np.array(m.pos) - depth * self.connector_axis()
        return Pose(tuple(float(x) for x in pos), m.rot)

    def seated_depth(self) -> float:
        return float(MC4.insertion_travel)

    # --- cable routing (installers tie leads along the purlin; only the tail near the connector is free) -------
    def _p(self, x: float, s: float, n: float) -> np.ndarray:
        return np.array(self.g["plane_point"](x, s, n))

    def _purlin_run(self) -> tuple[float, float]:
        """(s, n) of the cable run just under the rear purlin."""
        return float(self.g["purlin_s"][-1]) + 0.016, -float(self.table.purlin_height) - 0.006

    def female_tie(self) -> np.ndarray:
        s, n = self._purlin_run()
        return self._p(self.x_c + self.site.dx - 0.30, s, n)

    def female_lead_static(self) -> list[np.ndarray]:
        """+ lead of the target module: junction box -> down the back -> around the purlin -> along it -> tie."""
        s, n = self._purlin_run()
        sj = float(self.module.length) - float(self.module.jbox_from_top_edge)
        xj = self.x_c - 0.32  # right-hand split junction box (module +Y = world -X)
        sb = s + 0.05
        return [self._p(xj, sj, -0.02), self._p(xj, sb, -0.02), self._p(xj, sb, n), self._p(xj, s, n),
                self.female_tie()]

    def male_lead_static(self) -> list[np.ndarray]:
        """- lead of the neighbouring module: clipped half -> tie -> along the purlin -> junction box."""
        s, n = self._purlin_run()
        mouth = np.array(self.male_pose().pos)
        exit_ = mouth - self.connector_axis() * 0.12  # end of the male visual cable stub
        x_n = self.g["module_centres"][2][0] + 0.32  # left split junction box of the right-hand module
        sj = float(self.module.length) - float(self.module.jbox_from_top_edge)
        sb = s + 0.05
        tie = self._p(float(exit_[0]) + 0.10, s, n)
        return [exit_, tie, self._p(x_n, s, n), self._p(x_n, sb, n), self._p(x_n, sb, -0.02), self._p(x_n, sj, -0.02)]

    # --- clamps (T3) ---------------------------------------------------------------------------------------------
    def end_clamp_pose(self) -> Pose:
        """End clamp at the +X end of the table on the lower purlin (reachable from beside the table).

        Clamp frame: X up-slope along the module edge, +Y towards the module (-X world), Z = module normal.
        """
        x_last = self.g["module_centres"][self.table.modules_per_row - 1][0]
        x_e = x_last + float(self.module.width) / 2 + float(self.table.module_gap) / 2
        pos = self.g["plane_point"](x_e, float(self.g["purlin_s"][0]), 0.0)
        rot = Rotation.from_euler("x", self.g["tilt"]).as_matrix() @ Rotation.from_euler("z", np.pi / 2).as_matrix()
        return Pose(tuple(float(v) for v in pos), _quat(rot))

    def husky_and_arm_pose(self, standoff: float = 0.42, lateral: float = 0.0) -> tuple[Pose, Pose]:
        """Husky A300 parked beyond the table end facing -X; UR16e base on its deck mount, also facing -X.

        ``standoff``: horizontal distance from the clamp to the arm base along X.
        """
        from solarbench.specs import robots as R

        c = np.array(self.end_clamp_pose().pos)
        L, H = float(R.HUSKY_A300_LENGTH), float(R.HUSKY_A300_HEIGHT)
        arm = (float(c[0] + standoff), float(c[1] + lateral), H)
        husky = (arm[0] + (L / 2 - 0.20), arm[1], 0.0)
        yaw180 = (0.0, 0.0, 1.0, 0.0)
        return Pose(husky, yaw180), Pose(arm, yaw180)

    # --- robot --------------------------------------------------------------------------------------
    def robot_pose(self, standoff: float = 0.26, lateral: float = 0.11, height: float = 0.75) -> Pose:
        """Pelvis pose behind the table facing -Y; ``standoff`` is horizontal distance from the mouth.

        Defaults from scripts/dev/reach_study.py: best reachable grasp of the connector for the G1 right arm.
        """
        m = np.array(self.male_pose().pos)
        pos = (float(m[0] + lateral), float(m[1] + standoff), float(height))
        return Pose(pos, (0.0, 0.0, -math.sin(math.pi / 4), math.cos(math.pi / 4)))  # yaw -90 deg
