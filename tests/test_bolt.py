import pytest
import torch

from solarbench.tasks.bolt import BoltParams, bolt_step

P = BoltParams(tau_run=0.8, stiffness=(16 - 0.8) / 0.52, breakaway_ratio=0.9, tau_max_spec=18.0, nut_factor=0.2,
               diameter=0.008)


def _step(theta, tau, engaged=True):
    t = lambda v: torch.tensor([v])  # noqa: E731
    return bolt_step(P, t(theta), t(tau), t(engaged))


@pytest.mark.unit
def test_runs_down_then_clamps_up_in_proportion_to_torque():
    lo, hi, _ = _step(-1.0, 0.5)  # below running torque: holds
    assert hi.item() == pytest.approx(-1.0)
    lo, hi, _ = _step(-1.0, 8.4)  # half-way torque: admissible up to half the clamp-up angle
    assert hi.item() == pytest.approx(0.26, abs=1e-3)


@pytest.mark.unit
def test_no_torque_without_engagement():
    lo, hi, _ = _step(-1.0, 10.0, engaged=False)
    assert hi.item() == pytest.approx(-1.0) and lo.item() == pytest.approx(-1.0)


@pytest.mark.unit
def test_breakaway_and_over_torque():
    th = 0.52  # installed at 16 N*m
    lo, _, _ = _step(th, -10.0)  # below 0.9 * 16 = 14.4: holds
    assert lo.item() == pytest.approx(th)
    lo, _, _ = _step(th, -15.0)
    assert torch.isinf(lo).item()
    _, _, over = _step(0.7, 0.0)  # installed torque 21.3 N*m > 18
    assert over.item()
    assert P.preload(torch.tensor([th])).item() == pytest.approx(10_000, rel=1e-3)  # 16 / (0.2 * 0.008)


@pytest.mark.unit
def test_unengaged_bolt_is_pinned_at_committed_angle():
    # bounds are evaluated at the committed angle; any measured drift must be projected back to it
    lo, hi, _ = _step(-1.0, 0.0, engaged=False)
    measured = torch.tensor([-1.3])
    assert torch.clamp(measured, lo, hi).item() == pytest.approx(-1.0)


@pytest.mark.unit
def test_friction_schedule():
    from solarbench.tasks.bolt import bolt_friction

    th = torch.tensor([-1.0, 0.52])
    assert bolt_friction(P, th, loosening=False).tolist() == pytest.approx([0.8, 16.0], abs=1e-3)
    assert bolt_friction(P, th, loosening=True).tolist() == pytest.approx([0.8, 14.4], abs=1e-3)
