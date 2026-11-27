"""Command records run by a task's fixed controller: profile R2 (docs/interface.md, sections 4 and 5).

An R2 task takes a buffer of 64-byte command records each control tick instead of an R1 argument tensor. A
``PoseQueue`` holds at most one running ``TOOL_POSE`` per environment (depth 1). Each tick it turns the running
command into the R1 step the task already executes: the commanded tool pose moves toward the target by at most the
R1 limits per tick, and the task's IK and joint limits do the rest, exactly as for an R1 policy. When the measured
tool pose arrives, stops making progress (stalls) or the command's time runs out, the queue writes a completion
record. Nothing here reads the simulator: the task hands in the poses it holds. Quaternions are ``xyzw``.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from solarbench import wire

COMPLETIONS = 4  # completion records kept per environment, newest last (the shape of the `completions` channel)
WORDS = wire.COMPLETION.itemsize // 4  # a completion record as 32-bit words


def quat_mul(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    ax, ay, az, aw = a.unbind(-1)
    bx, by, bz, bw = b.unbind(-1)
    return torch.stack([aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
                        aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz], dim=-1)


def quat_conj(q: torch.Tensor) -> torch.Tensor:
    return q * torch.tensor([-1.0, -1.0, -1.0, 1.0], device=q.device)


def rotvec(q: torch.Tensor) -> torch.Tensor:
    """The rotation of unit quaternion ``q`` as axis times angle (rad), the short way round."""
    q = q * torch.where(q[..., 3:] < 0, -1.0, 1.0)
    v, w = q[..., :3], q[..., 3]
    s = v.norm(dim=-1)
    scale = torch.where(s > 1e-6, 2 * torch.atan2(s, w) / s.clamp(min=1e-6), 2 / w.clamp(min=1e-6))
    return v * scale[..., None]


def quat_from_rotvec(r: torch.Tensor) -> torch.Tensor:
    angle = r.norm(dim=-1, keepdim=True)
    scale = torch.where(angle > 1e-6, torch.sin(angle / 2) / angle.clamp(min=1e-6), 0.5 - angle**2 / 48)
    return torch.cat([r * scale, torch.cos(angle / 2)], dim=-1)


def completions_channel() -> dict:
    return {"id": 4, "name": "completions", "dtype": "completion", "shape": [COMPLETIONS]}


@dataclass
class PoseLimits:
    """How the fixed controller runs a pose and judges how it ended. Steps are the task's R1 limits per tick."""

    max_step: float  # m per tick
    max_rot_step: float  # rad per tick
    timeout: int  # ticks a command may run when its record says 0
    pos_tol: float  # m: arrived when the measured tool position is this close...
    rot_tol: float  # rad: ...and its orientation this close
    stall_ticks: int  # stalled after this many ticks without progress...
    stall_pos: float  # m: ...where progress is the position error falling by this much below its best so far
    stall_rot: float  # rad: ...or the rotation error by this much


def unpack(records: torch.Tensor):
    """Fields of ``(N, depth, 16)`` int32 records: opcode, flags, id, based_on, timeout (as integers) and args."""
    word0 = records[..., 0]
    args = records[..., 4:16].contiguous().view(torch.float32)
    return word0 & 0xFFFF, (word0 >> 16) & 0xFFFF, records[..., 1], records[..., 2], records[..., 3], args


def pose_records(position: torch.Tensor, quat: torch.Tensor, ids: torch.Tensor, based_on: torch.Tensor,
                 timeout: int = 0) -> torch.Tensor:
    """One ``TOOL_POSE`` record per environment, as the ``(N, 1, 16)`` int32 buffer a policy returns."""
    n = len(position)
    records = torch.zeros(n, 1, 16, dtype=torch.int32, device=position.device)
    records[:, 0, 0] = wire.TOOL_POSE
    records[:, 0, 1], records[:, 0, 2], records[:, 0, 3] = ids.int(), based_on.int(), timeout
    records[:, 0, 4:11] = torch.cat([position, quat], dim=-1).float().view(torch.int32)
    return records


def r1_target(pos: torch.Tensor, quat: torch.Tensor, action: torch.Tensor, max_step: float, max_rot_step: float):
    """Where one R1 step ``action`` moves the commanded tool pose ``(pos, quat)``, as an R1 task applies it. Sent as
    a ``TOOL_POSE`` record with a one-tick timeout, this target replays the R1 step exactly."""
    a = action.clamp(-1.0, 1.0)
    return pos + a[:, :3] * max_step, quat_mul(quat_from_rotvec(a[:, 3:] * max_rot_step), quat)


class PoseQueue:
    def __init__(self, n: int, device, limits: PoseLimits):
        self.limits, self.n, self.device = limits, n, device
        self.active = torch.zeros(n, dtype=torch.bool, device=device)
        self.done = torch.zeros(n, dtype=torch.bool, device=device)  # DONE received: the episode ends
        self.cmd_id = torch.zeros(n, dtype=torch.int32, device=device)
        self.started = torch.zeros(n, dtype=torch.int32, device=device)
        self.deadline = torch.zeros(n, dtype=torch.int32, device=device)
        self.target_pos = torch.zeros(n, 3, device=device)
        self.target_quat = torch.zeros(n, 4, device=device)
        self.best = torch.zeros(n, 2, device=device)  # lowest position and rotation error of the running command
        self.idle_ticks = torch.zeros(n, dtype=torch.int32, device=device)
        self.completions = torch.zeros(n, COMPLETIONS, WORDS, dtype=torch.int32, device=device)

    def reset(self, env_ids: torch.Tensor) -> None:
        self.active[env_ids], self.done[env_ids], self.completions[env_ids] = False, False, 0

    def _complete(self, mask, cmd_id, opcode, status, started, ended, result=None) -> None:
        """Append one completion record to each environment in ``mask``."""
        if not mask.any():
            return
        record = torch.zeros(self.n, WORDS, dtype=torch.int32, device=self.device)
        record[:, 0] = cmd_id
        record[:, 1] = (torch.as_tensor(opcode, device=self.device) | (status << 16)).int()
        record[:, 2], record[:, 3] = started, ended
        if result is not None:
            record[:, 4:8] = result.float().view(torch.int32)
        rolled = torch.cat([self.completions[:, 1:], record[:, None]], dim=1)
        self.completions[mask] = rolled[mask]

    def submit(self, records: torch.Tensor, tick: torch.Tensor) -> None:
        """Take one buffer of ``(N, 1, 16)`` records, given the tick each environment is at."""
        opcode, flags, ids, _, timeout, args = (field[:, 0] for field in unpack(records.to(self.device)))
        tick = tick.int()
        command = opcode != wire.NOP
        known = (opcode == wire.TOOL_POSE) | (opcode == wire.DONE)
        quat = args[:, 3:7]
        norm = quat.norm(dim=-1)
        pose = opcode == wire.TOOL_POSE
        readable = torch.isfinite(args).all(dim=-1) & (~pose | (norm > 1e-6))
        # a buffer that cannot be read is refused whole (the whole buffer is one record at depth 1)
        status = torch.where(~known, wire.UNKNOWN, wire.INVALID)
        refused = command & ~(known & readable)
        self._complete(refused, ids, opcode, status, tick, tick)
        accepted = command & ~refused
        replace = (flags & wire.REPLACE) != 0
        full = accepted & self.active & ~replace
        self._complete(full, ids, opcode, wire.FULL, tick, tick)
        go = accepted & ~full
        self._complete(go & self.active, self.cmd_id, wire.TOOL_POSE, wire.PREEMPTED, self.started, tick)
        self.active &= ~go
        end = go & (opcode == wire.DONE)
        self._complete(end, ids, wire.DONE, wire.OK, tick, tick)
        self.done |= end
        start = go & pose
        self.active |= start
        self.cmd_id = torch.where(start, ids, self.cmd_id)
        self.started = torch.where(start, tick, self.started)
        self.deadline = torch.where(start, tick + torch.where(timeout > 0, timeout, self.limits.timeout), self.deadline)
        self.target_pos[start] = args[start, :3]
        self.target_quat[start] = quat[start] / norm[start, None]
        self.best[start] = float("inf")
        self.idle_ticks[start] = 0

    def step(self, commanded_pos: torch.Tensor, commanded_quat: torch.Tensor) -> torch.Tensor:
        """The R1 action that moves the commanded tool pose toward each running target: zero where none runs."""
        lim = self.limits
        action = torch.zeros(self.n, 6, device=self.device)
        action[:, :3] = ((self.target_pos - commanded_pos) / lim.max_step).clamp(-1.0, 1.0)
        action[:, 3:] = (rotvec(quat_mul(self.target_quat, quat_conj(commanded_quat))) / lim.max_rot_step).clamp(-1, 1)
        return torch.where(self.active[:, None], action, torch.zeros_like(action))

    def update(self, tick: torch.Tensor, pos: torch.Tensor, quat: torch.Tensor, force: torch.Tensor | None = None,
               torque_z: torch.Tensor | None = None) -> None:
        """Judge each running command against the measured tool pose after a tick, and complete those that ended.

        ``force`` (N) and ``torque_z`` (N*m), from the wrist sensor, go into the result only when given: they are
        reported to a policy that selected the wrench channel, and are zero otherwise.
        """
        lim, tick = self.limits, tick.int()
        turn = rotvec(quat_mul(self.target_quat, quat_conj(quat))).norm(dim=-1)
        err = torch.stack([(self.target_pos - pos).norm(dim=-1), turn], -1)
        progress = (err[:, 0] < self.best[:, 0] - lim.stall_pos) | (err[:, 1] < self.best[:, 1] - lim.stall_rot)
        self.best = torch.where(progress[:, None], err, torch.minimum(self.best, err))
        self.idle_ticks = torch.where(progress, 0, self.idle_ticks + 1)
        arrived = (err[:, 0] <= lim.pos_tol) & (err[:, 1] <= lim.rot_tol)
        status = torch.where(arrived, wire.OK, torch.where(tick >= self.deadline, wire.TIMED_OUT, wire.STALLED))
        ended = self.active & (arrived | (tick >= self.deadline) | (self.idle_ticks >= lim.stall_ticks))
        zero = torch.zeros(self.n, device=self.device)
        sensed = [zero, zero] if force is None else [force, torque_z]
        result = torch.stack([*err.T, *sensed], -1)
        self._complete(ended, self.cmd_id, wire.TOOL_POSE, status, self.started, tick, result)
        self.active &= ~ended

    @property
    def idle(self) -> torch.Tensor:
        """Environments whose queue is empty: an R2 policy is woken for these."""
        return ~self.active
