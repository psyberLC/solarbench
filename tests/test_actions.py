"""Command records and the R2 pose queue (solarbench.tasks.actions), without a simulator."""

import numpy as np
import pytest
import torch

from solarbench import wire
from solarbench.tasks.actions import (
    PoseLimits,
    PoseQueue,
    pose_records,
    quat_conj,
    quat_from_rotvec,
    quat_mul,
    r1_target,
    rotvec,
    unpack,
)

LIMITS = PoseLimits(max_step=0.006, max_rot_step=0.05, timeout=300, pos_tol=0.001, rot_tol=0.01, stall_ticks=15,
                    stall_pos=0.0002, stall_rot=0.002)
DOWN = torch.tensor([[1.0, 0.0, 0.0, 0.0]])  # quaternion xyzw used throughout; any unit quaternion would do
TICK = torch.tensor([0])


def queue(n=1):
    return PoseQueue(n, "cpu", LIMITS)


def record(opcode=wire.TOOL_POSE, flags=0, cid=7, args=(0.4, 0.0, 0.5, 1.0, 0.0, 0.0, 0.0), timeout=0):
    r = np.zeros((1, 1), wire.COMMAND)
    r["opcode"], r["flags"], r["id"], r["timeout"] = opcode, flags, cid, timeout
    r["args"][0, 0, : len(args)] = args
    return torch.from_numpy(r.view("<i4").reshape(1, 1, 16).copy())


def completions(q, env=0):
    return q.completions[env].numpy().view(wire.COMPLETION)[:, 0]


@pytest.mark.unit
def test_quaternion_helpers_agree_with_each_other():
    torch.manual_seed(1)
    r = torch.randn(256, 3)
    r = r / r.norm(dim=-1, keepdim=True) * torch.rand(256, 1) * 3.1  # angles below pi, so the short way is r itself
    q = quat_from_rotvec(r)
    assert torch.allclose(q.norm(dim=-1), torch.ones(256), atol=1e-6)
    assert torch.allclose(rotvec(q), r, atol=1e-4) and torch.allclose(rotvec(-q), r, atol=1e-4)
    assert torch.allclose(quat_mul(q, quat_conj(q)), torch.tensor([0.0, 0.0, 0.0, 1.0]).expand(256, 4), atol=1e-6)
    x90, y90 = quat_from_rotvec(torch.tensor([[1.5707963, 0, 0]])), quat_from_rotvec(torch.tensor([[0, 1.5707963, 0]]))
    # a turn about x, then one about y (both in the fixed frame): z ends up along x
    assert torch.allclose(rotvec(quat_mul(y90, x90)), torch.tensor([[1.2092, 1.2092, -1.2092]]), atol=1e-3)


@pytest.mark.unit
def test_records_written_here_read_back_through_the_wire_layout():
    r = pose_records(torch.tensor([[0.4, 0.1, 0.5]]), DOWN, torch.tensor([3]), torch.tensor([12]), timeout=9)
    opcode, flags, cid, based_on, timeout, args = (f[0, 0] for f in unpack(r))
    assert (opcode, flags, cid, based_on, timeout) == (wire.TOOL_POSE, 0, 3, 12, 9)
    assert args[:7].tolist() == pytest.approx([0.4, 0.1, 0.5, 1.0, 0.0, 0.0, 0.0])
    on_the_wire = r.numpy().view(wire.COMMAND)[0, 0]
    assert on_the_wire["opcode"] == wire.TOOL_POSE and on_the_wire["id"] == 3


@pytest.mark.unit
def test_a_pose_is_reached_in_steps_no_larger_than_the_r1_limits():
    q, pos, quat = queue(), torch.tensor([[0.4, 0.0, 0.6]]), DOWN.clone()
    target_quat = quat_mul(quat_from_rotvec(torch.tensor([[0.0, 0.0, 0.3]])), DOWN)
    q.submit(record(args=(0.4, 0.05, 0.55, *target_quat[0].tolist())), TICK)
    for tick in range(1, 60):
        a = q.step(pos, quat)
        assert a.abs().max() <= 1.0
        pos = pos + a[:, :3] * LIMITS.max_step  # a kinematic arm that follows the command exactly
        quat = quat_mul(quat_from_rotvec(a[:, 3:] * LIMITS.max_rot_step), quat)
        q.update(torch.tensor([tick]), pos, quat)
        if not q.active[0]:
            break
    done = completions(q)[-1]
    assert done["status"] == wire.OK and done["id"] == 7 and done["opcode"] == wire.TOOL_POSE
    assert tick >= 0.3 / LIMITS.max_rot_step  # the turn sets the pace: 0.3 rad at 0.05 rad per tick
    assert done["result"][0] <= LIMITS.pos_tol and done["result"][1] <= LIMITS.rot_tol
    assert done["result"][2:].tolist() == [0.0, 0.0]  # no wrench given, none reported
    assert q.step(pos, quat).abs().max() == 0  # nothing runs: the robot holds


@pytest.mark.unit
def test_an_arm_that_cannot_move_stalls_and_a_slow_one_times_out():
    q, pos = queue(), torch.tensor([[0.4, 0.0, 0.6]])
    q.submit(record(), TICK)
    for tick in range(1, 40):
        q.update(torch.tensor([tick]), pos, DOWN, torch.tensor([30.0]), torch.tensor([2.5]))
        if not q.active[0]:
            break
    stalled = completions(q)[-1]
    assert stalled["status"] == wire.STALLED and tick == LIMITS.stall_ticks + 1
    assert stalled["result"].tolist() == pytest.approx([0.1, 0.0, 30.0, 2.5])
    q.submit(record(cid=8, timeout=5), torch.tensor([50]))
    for tick in range(51, 60):
        pos = pos - torch.tensor([[0.0, 0.0, 0.001]])  # creeping toward the target, never there
        q.update(torch.tensor([tick]), pos, DOWN)
    assert completions(q)[-1]["status"] == wire.TIMED_OUT and completions(q)[-1]["ended"] == 55


@pytest.mark.unit
def test_a_buffer_that_cannot_be_read_is_refused_and_nothing_starts():
    for bad, status in ((record(opcode=1), wire.UNKNOWN), (record(opcode=99), wire.UNKNOWN),
                        (record(args=(0.4, float("nan"), 0.5, 1.0, 0, 0, 0)), wire.INVALID),
                        (record(args=(0.4, 0.0, 0.5, 0.0, 0, 0, 0)), wire.INVALID)):
        q = queue()
        q.submit(bad, TICK)
        assert not q.active[0] and completions(q)[-1]["status"] == status


@pytest.mark.unit
def test_a_second_command_needs_replace_and_done_ends_the_episode():
    q = queue()
    q.submit(record(cid=1), TICK)
    q.submit(record(cid=2), TICK + 1)  # the queue holds one: refused, the first keeps running
    assert q.active[0] and q.cmd_id[0] == 1 and completions(q)[-1]["status"] == wire.FULL
    q.submit(record(cid=3, flags=wire.REPLACE), TICK + 2)
    assert q.cmd_id[0] == 3
    assert [(c["id"], c["status"]) for c in completions(q)[-2:]] == [(2, wire.FULL), (1, wire.PREEMPTED)]
    q.submit(record(opcode=wire.DONE, cid=4, args=()), TICK + 3)
    assert completions(q)[-1]["status"] == wire.FULL and not q.done[0]  # DONE waits its turn like any command
    q.submit(record(opcode=wire.DONE, cid=5, flags=wire.REPLACE, args=()), TICK + 4)
    assert q.done[0] and not q.active[0]
    assert [(c["id"], c["status"]) for c in completions(q)[-2:]] == [(3, wire.PREEMPTED), (5, wire.OK)]
    q.reset(torch.tensor([0]))
    assert not q.done[0] and q.completions.abs().sum() == 0


@pytest.mark.unit
def test_queues_of_different_environments_do_not_mix():
    q = queue(2)
    two = torch.cat([record(cid=1), record(opcode=wire.NOP)])
    q.submit(two, torch.tensor([0, 0]))
    assert q.active.tolist() == [True, False] and q.completions[1].abs().sum() == 0
    a = q.step(torch.tensor([[0.4, 0.0, 0.6]] * 2), DOWN.repeat(2, 1))
    assert a[0, 2] == -1.0 and a[1].abs().sum() == 0


@pytest.mark.unit
def test_an_r1_step_sent_as_a_one_tick_pose_is_the_same_step():
    torch.manual_seed(0)
    n = 64
    pos = torch.rand(n, 3)
    quat = torch.nn.functional.normalize(torch.randn(n, 4), dim=-1)
    action = torch.rand(n, 6) * 2.4 - 1.2  # some components beyond the limits: clipped the same way both times
    target = r1_target(pos, quat, action, LIMITS.max_step, LIMITS.max_rot_step)
    q = PoseQueue(n, "cpu", LIMITS)
    q.submit(pose_records(*target, torch.arange(n), torch.zeros(n), timeout=1), torch.zeros(n))
    assert torch.allclose(q.step(pos, quat), action.clamp(-1, 1), atol=1e-4)
    q.update(torch.ones(n), *target)  # the tick after: every one has ended, here by arriving
    assert not q.active.any() and (q.completions[:, -1, 1] >> 16 == wire.OK).all()
