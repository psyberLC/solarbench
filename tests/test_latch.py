import pytest
import torch

from solarbench.tasks.latch import LatchParams, LatchState, latch_step

P = LatchParams(gate_depth=0.010, latch_depth=0.013, seated_depth=0.016, unlock_hold_time=0.2)
DT = 1 / 600


def _state(latched: bool) -> LatchState:
    s = LatchState(1, "cpu")
    s.reset(torch.tensor([0]), torch.tensor([latched]), torch.tensor([45.0]), torch.tensor([250.0]))
    return s


def _step(s, depth, push=0.0, pull=0.0, grasped=False, unlock=False):
    t = lambda v: torch.tensor([v])  # noqa: E731
    return latch_step(s, P, t(depth), t(push), t(pull), t(grasped), t(unlock), DT)


@pytest.mark.unit
def test_ramp_admits_depth_in_proportion_to_push_and_snaps_through():
    s = _state(False)
    dmax, _ = _step(s, 0.009, push=0.0)
    assert dmax.item() == pytest.approx(P.gate_depth)
    dmax, _ = _step(s, 0.011, push=22.5)  # half the insertion force -> half way up the ramp
    assert dmax.item() == pytest.approx(P.gate_depth + 0.5 * (P.latch_depth - P.gate_depth))
    dmax, _ = _step(s, 0.011, push=50.0)
    assert torch.isinf(dmax).item()


@pytest.mark.unit
def test_snap_in_latches_and_holds():
    s = _state(False)
    _step(s, 0.0135, push=50.0)
    assert s.latched.item()
    _, dmin = _step(s, 0.012, pull=100.0)
    assert dmin.item() == pytest.approx(P.latch_depth)
    assert not s.broken.item()


@pytest.mark.unit
def test_overpull_breaks_latch():
    s = _state(True)
    _step(s, 0.014, pull=300.0)
    assert s.broken.item() and not s.latched.item()


@pytest.mark.unit
def test_unlock_requires_grasp_and_hold_time():
    s = _state(True)
    for _ in range(int(0.1 / DT)):
        _step(s, 0.016, unlock=True, grasped=False)
    assert s.latched.item()
    for _ in range(int(0.25 / DT)):
        _step(s, 0.016, unlock=True, grasped=True)
    assert s.open.item() and not s.latched.item()
    _, dmin = _step(s, 0.010, unlock=True, grasped=True)
    assert torch.isinf(dmin).item()


@pytest.mark.unit
def test_unlock_tolerates_brief_grasp_chatter_but_not_letting_go():
    s = _state(True)
    for k in range(int(0.4 / DT)):
        _step(s, 0.016, unlock=True, grasped=(k % 10 != 0))  # 10 % chatter
    assert s.open.item()
    s = _state(True)
    for k in range(int(0.4 / DT)):
        _step(s, 0.016, unlock=True, grasped=(k % 2 == 0))  # holding only half the time
    assert not s.open.item()
