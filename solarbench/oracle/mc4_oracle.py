"""Scripted oracle for T2: privileged-state waypoint controller emitting R1 actions.

It uses the same 8-D action interface as learned policies, so it also validates that the task is solvable
through that interface within the robot's real torque limits. It never touches simulator state.
"""

from __future__ import annotations

import math

import torch
from isaaclab.utils.math import (
    axis_angle_from_quat,
    quat_apply,
    quat_apply_inverse,
    quat_inv,
    quat_mul,
    subtract_frame_transforms,
)

PHASES = ("pregrasp", "approach", "close", "unlock", "pull", "hold_out", "realign", "insert", "release", "retreat")


class MC4Oracle:
    def __init__(self, env, phi_deg: float = 0.0, pregrasp_clearance: float = 0.06, approach_dir: str = "palm"):
        self.env = env
        e = env
        n, dev = e.num_envs, e.device
        self.phase = torch.zeros(n, dtype=torch.long, device=dev)
        self.timer = torch.zeros(n, device=dev)
        self.clearance = pregrasp_clearance
        self.slow_scale = 0.3  # of max_ee_step per policy step (~7 cm/s)
        self.contact_stop = 3.0  # N, guarded-move contact threshold
        rq = e.robot.data.root_quat_w.torch
        self.axis_b = quat_apply_inverse(rq, e.axis_w)  # connector axis (out of the mouth) in base frame
        self.quat_b = self._grasp_quat(math.radians(phi_deg))
        # Approach along the palm normal: the open hand presents its palm to the housing (power grasp), so the
        # straight fingers never sweep across it. "below"/"above" kept for ablations.
        palm_normal_b = quat_apply(self.quat_b, torch.tensor([0.0, 1.0, 0.0], device=dev).repeat(n, 1))
        up_b = quat_apply_inverse(rq, torch.tensor([0.0, 0.0, 1.0], device=dev).repeat(n, 1))
        self.approach_b = {"palm": -palm_normal_b, "below": -up_b, "above": up_b}[approach_dir]
        self.tip_to_site = float(e.grasp_site_b[0, 0])

    def _grasp_quat(self, phi: float) -> torch.Tensor:
        """Palm orientation with palm z along the connector axis (pointing into the mouth), rolled by ``phi``."""
        z = -self.axis_b
        ref = torch.tensor([0.0, 0.0, 1.0], device=z.device).expand_as(z)
        x0 = ref - torch.sum(ref * z, -1, keepdim=True) * z
        x0 = x0 / x0.norm(dim=-1, keepdim=True)
        y0 = torch.cross(z, x0, dim=-1)
        x = math.cos(phi) * x0 + math.sin(phi) * y0
        y = torch.cross(z, x, dim=-1)
        rot = torch.stack([x, y, z], dim=-1)
        from isaaclab.utils.math import quat_from_matrix

        return quat_from_matrix(rot)

    def reset(self, env_ids=None) -> None:
        ids = slice(None) if env_ids is None else env_ids
        self.phase[ids] = 0
        self.timer[ids] = 0.0

    def _site_goal_b(self, tip_depth: float) -> torch.Tensor:
        """Grasp-site position (base frame) when the tip is at ``tip_depth`` inside the sleeve."""
        e = self.env
        rp, rq = e.robot.data.root_pos_w.torch, e.robot.data.root_quat_w.torch
        tip_w = e.mouth_w - tip_depth * e.axis_w
        site_w = tip_w + self.tip_to_site * e.axis_w
        return quat_apply_inverse(rq, site_w - rp)

    def act(self) -> torch.Tensor:
        e = self.env
        dt = e.step_dt
        self.timer += dt
        rp, rq = e.robot.data.root_pos_w.torch, e.robot.data.root_quat_w.torch
        f_site_w, _ = e.female_site_w()
        site_b = quat_apply_inverse(rq, f_site_w - rp)
        g_pos_b, _ = e.grasp_pose_b()
        n = e.num_envs
        goal = site_b.clone()
        grip = torch.full((n,), -1.0, device=e.device)
        unlock = torch.full((n,), -1.0, device=e.device)
        p = self.phase
        err = (g_pos_b - site_b).norm(dim=-1)

        def advance(mask, cond):
            go = mask & cond
            self.phase[go] += 1
            self.timer[go] = 0.0

        m = p == 0  # pregrasp: site offset along the approach direction
        goal[m] = site_b[m] + self.clearance * self.approach_b[m]
        advance(m, ((g_pos_b - goal).norm(dim=-1) < 0.01) | (self.timer > 4.0))
        m = p == 1  # guarded approach: stop at the grasp pose or at first hand contact
        advance(m, (err < 0.006) | (e.f_hand_w.norm(dim=-1) > self.contact_stop) | (self.timer > 3.0))
        m = p == 2  # close: stop driving the arm once the fingers start closing, let the grasp settle
        grip[m] = 1.0
        goal[m] = g_pos_b[m]
        advance(m, (self.timer > 0.6) & e.grasped | (self.timer > 1.5))
        m = p == 3  # unlock (hold the tool action) without pushing the arm
        grip[m], unlock[m] = 1.0, 1.0
        goal[m] = g_pos_b[m]
        advance(m, ~e.latch.latched | (self.timer > 3.0))
        # In-hand phases are object-centric in full pose: with the measured hand->housing transform T_ho
        # (rigid while grasped), command T_hand* = T_obj* . T_ho^-1 so the *housing* reaches its target pose.
        # Driving the grasp centre onto the ideal axis instead levers an off-centre or tilted housing into the
        # sleeve wall and jams it (measured: effective friction > 1 with a 15 N side load).
        o_pos_b, o_quat_b = subtract_frame_transforms(
            rp, rq, e.female.data.root_pos_w.torch, e.female.data.root_quat_w.torch
        )
        _, g_quat_b = e.grasp_pose_b()
        rel_p, rel_q = subtract_frame_transforms(g_pos_b, g_quat_b, o_pos_b, o_quat_b)
        conn_quat_b = quat_mul(quat_inv(rq), e.conn_quat_w)
        quat_goal = self.quat_b.clone()

        def carry(tip_depth, axial_only=False):
            tip_goal = quat_apply_inverse(rq, e.mouth_w - tip_depth * e.axis_w - rp)
            if axial_only:  # keep current lateral/tilt, only advance along the axis
                d = torch.sum((tip_goal - o_pos_b) * self.axis_b, -1, keepdim=True) * self.axis_b
                return g_pos_b + d, g_quat_b
            q_h = quat_mul(conn_quat_b, quat_inv(rel_q))
            return tip_goal - quat_apply(q_h, rel_p), q_h

        def set_goal(m, tip_depth, axial_only=False):
            gp, gq = carry(tip_depth, axial_only)
            goal[m] = gp[m]
            quat_goal[m] = gq[m]

        m = p == 4  # pull straight out along the axis, keep the latch arms held open
        grip[m], unlock[m] = 1.0, 1.0
        set_goal(m, -0.035, axial_only=True)
        advance(m, (e.depth < -0.025) | (self.timer > 4.0))
        m = p == 5  # hold out (disconnected), square the housing up to the axis
        grip[m] = 1.0
        set_goal(m, -0.035)
        advance(m, self.timer > 0.8)
        m = p == 6  # realign in front of the mouth
        grip[m] = 1.0
        set_goal(m, -0.004)
        advance(m, (e._lateral < 0.0008) & (e.depth > -0.006) | (self.timer > 3.0))
        m = p == 7  # insert: command past the back stop so the arm pushes through the detent
        grip[m] = 1.0
        set_goal(m, e.cfg.seated_depth + 0.010)
        advance(m, e.latch.latched | (self.timer > 4.0))
        m = p == 8  # release
        goal[m] = g_pos_b[m]
        advance(m, self.timer > 0.6)
        m = p == 9  # retreat
        goal[m] = self._site_goal_b(-0.10)[m] + 0.06 * self.approach_b[m]

        # R1 actions in target space: the env's integral IK removes steady-state tracking error, so adding a
        # second integrator here (closing on the measured pose) makes the loop oscillate.
        a = torch.zeros(n, 8, device=e.device)
        a[:, :3] = ((goal - e.tgt_pos_b) / e.cfg.max_ee_step).clamp(-1.0, 1.0)
        # Careful speed while the connector is in hand: fast pulls slip a 1.4 N*m-finger grasp.
        slow = (p >= 4) & (p <= 7)
        a[slow, :3] = a[slow, :3].clamp(-self.slow_scale, self.slow_scale)
        dq = quat_mul(quat_goal, quat_inv(e.tgt_quat_b))
        a[:, 3:6] = (axis_angle_from_quat(dq) / e.cfg.max_rot_step).clamp(-1.0, 1.0)
        a[:, 6], a[:, 7] = grip, unlock
        return a
