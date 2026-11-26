"""Scripted oracle for T3 (UR16e + socket): align, seat with a rotational search, turn under torque control, retract.

Tightening stops on the *measured* drive torque (as a nutrunner's transducer would), so the installed torque it
reaches is a physics outcome, not a scripted value.
"""

from __future__ import annotations

import torch
from isaaclab.utils.math import (
    axis_angle_from_quat,
    quat_apply_inverse,
    quat_from_angle_axis,
    quat_from_matrix,
    quat_inv,
    quat_mul,
)

PHASES = ("align", "seat", "turn", "retract", "done")


class ClampOracle:
    def __init__(self, env, tau_target: float = 16.0, turn_rate: float = 1.0, final_rate: float = 0.05,
                 seek_rate: float = 0.25):
        # two-stage tightening like a nutrunner: fast run-down, then a slow final stage above 50 % of the target so the
        # drive's tracking lag does not carry the joint past the shut-off torque
        self.env, self.tau_target, self.turn_rate, self.final_rate = env, tau_target, turn_rate, final_rate
        n, dev = env.num_envs, env.device
        self.phase = torch.zeros(n, dtype=torch.long, device=dev)
        self.timer = torch.zeros(n, device=dev)
        self.spin = torch.zeros(n, device=dev)  # accumulated rotation about the tool axis [rad]
        self.bias = torch.zeros(n, 3, device=dev)  # slow integral of measured TCP error (seek correction)
        self.seek_rate = seek_rate  # rad/s; the +-2.3 deg alignment window lasts ~0.16 s
        self.seat_tau_limit = 2.0  # N*m felt before the socket is seated -> stop and unwind (guarded search)

    def reset(self, env_ids=None) -> None:
        ids = slice(None) if env_ids is None else env_ids
        self.phase[ids], self.timer[ids], self.spin[ids] = 0, 0.0, 0.0
        self.bias[ids] = 0.0

    def _aligned_quat(self, z_b_b: torch.Tensor) -> torch.Tensor:
        z = -z_b_b
        ref = torch.tensor([1.0, 0.0, 0.0], device=z.device).expand_as(z)
        x = ref - torch.sum(ref * z, -1, keepdim=True) * z
        x = x / x.norm(dim=-1, keepdim=True)
        y = torch.cross(z, x, dim=-1)
        return quat_from_matrix(torch.stack([x, y, z], dim=-1))

    def act(self) -> torch.Tensor:
        e = self.env
        dt = e.step_dt
        self.timer += dt
        rp, rq = e._root()
        head_w, z_b_w = e.head_top_w()
        head_b = quat_apply_inverse(rq, head_w - rp)
        z_b = quat_apply_inverse(rq, z_b_w)
        tcp_p, _ = e.tcp_pose_b()
        n = e.num_envs
        p = self.phase
        goal = head_b + 0.05 * z_b
        mode_sign = 1.0 if e.cfg.mode == "tighten" else -1.0

        def advance(m, cond):
            go = m & cond
            self.phase[go] += 1
            self.timer[go] = 0.0

        m = p == 0  # align 5 cm above the head on the bolt axis, pre-winding wrist 3 for the coming rotation
        # (UR wrist 3 has +-2 pi of travel; tightening needs room in +, loosening in -)
        w3 = e.robot.data.joint_pos.torch[:, e.arm_ids[5]]
        wind = -3.0 if e.cfg.mode == "tighten" else 3.0
        self.spin[m] += (0.5 * (wind - w3)).clamp(-0.04, 0.04)[m]
        wound = (w3 - wind).abs() < 0.15
        advance(m, ((tcp_p - goal).norm(dim=-1) < 0.004) & wound & (self.timer > 1.0) | (self.timer > 8.0))
        m = p == 1  # seat: rotate slowly one way under *light* pressure until the flats line up
        # (hex repeats every 60 deg). The target stays only 1.5 mm past the current insertion depth: pressing hard
        # wedges the chamfered corners against all six walls and friction then stops the socket turning (seen in
        # contact diagnostics). Guarded: if the drive torque rises before the socket counts as seated (corners caught
        # on the chamfer), stop and unwind instead of cranking a half-seated socket (seen on PhysX: 38 N*m).
        goal[m] = (head_b - (e.depth.clamp(min=0.0) + 0.0015)[:, None] * z_b)[m]
        caught = e.tau.abs() > self.seat_tau_limit
        seek = torch.where(caught, -torch.sign(e.tau) * 0.3, torch.full_like(e.tau, self.seek_rate))
        self.spin[m] += (seek * dt)[m]
        advance(m, e.engaged | (self.timer > 10.0))
        m = p == 2  # turn while pressing gently on the washer
        goal[m] = (head_b - 0.007 * z_b)[m]
        if e.cfg.mode == "tighten":
            done_turn = e.tau >= self.tau_target
        else:
            done_turn = e.theta <= e.theta0 - e.cfg.backoff_angle - 0.05
        turning = m & ~done_turn
        final = (e.tau > 0.5 * self.tau_target) if e.cfg.mode == "tighten" else torch.zeros_like(e.engaged)
        rate = torch.where(final, self.final_rate, self.turn_rate)
        self.spin[turning] += (mode_sign * rate * dt)[turning]
        advance(m, done_turn | (self.timer > 12.0))
        m = p >= 3  # relax the wound-up drive torque (the loaded flats wedge the socket on the head), then retract
        relaxing = m & (e.tau.abs() > 0.5) & (self.timer < 3.0)
        goal[relaxing] = (head_b - 0.007 * z_b)[relaxing]
        self.spin[relaxing] -= (torch.sign(e.tau) * 0.3 * dt)[relaxing]
        lifting = m & ~relaxing
        goal[lifting] = (head_b + 0.08 * z_b)[lifting]
        self.timer[relaxing] = 0.0
        advance(lifting & (p == 3), self.timer > 1.5)

        quat_goal = quat_mul(self._aligned_quat(z_b), quat_from_angle_axis(self.spin, torch.tensor(
            [0.0, 0.0, 1.0], device=e.device).expand(n, 3)))
        # Slow correction of the kinematic IK's steady-state error from the *measured* socket position. Lateral error
        # is always integrated; axial error only in free space, so in contact the press stays a small proportional
        # offset instead of winding up into a hard push (which wedges the head, see the seat phase).
        err = goal - tcp_p
        ax = torch.sum(err * z_b, -1, keepdim=True)
        free = (e.depth < -0.0005)[:, None].float()
        corr = (err - ax * z_b) + free * ax * z_b
        seek = (p >= 0) & (p <= 2)
        self.bias[seek] = (self.bias[seek] + 0.15 * corr[seek]).clamp(-0.015, 0.015)
        a = torch.zeros(n, 6, device=e.device)
        a[:, :3] = ((goal + self.bias - e.tgt_pos_b) / e.cfg.max_tcp_step).clamp(-1.0, 1.0)
        slow = (p == 1) | (p == 2)
        a[slow, :3] = a[slow, :3].clamp(-0.25, 0.25)
        dq = quat_mul(quat_goal, quat_inv(e.tgt_quat_b))
        a[:, 3:6] = (axis_angle_from_quat(dq) / e.cfg.max_rot_step).clamp(-1.0, 1.0)
        return a
