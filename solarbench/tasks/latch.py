"""Constraint-projection model of an MC4 snap latch (ASSUMPTIONS P5).

Explicit spring forces on a 30 g housing are unstable at the 600 Hz physics rate for any stiffness that
could hold the latch, so the latch is modelled as a position-level constraint on the insertion depth
``d`` (metres, > 0 inside the sleeve), applied every physics step:

* **ramp**     unlatched and not held open: beyond ``gate_depth`` the latch arms deflect like a spring, so the
               admissible depth is ``gate_depth + (push / insertion_force) * (latch_depth - gate_depth)``. When
               the axial push the robot applies reaches the sampled insertion force the arms snap through and the
               housing latches at ``latch_depth``.
* **latched**  ``d`` is held at the seated depth (rigid latch). A pull larger than the sampled locked
               withdrawal force breaks the latch, which is a damage event.
* **open**     the latch arms are held open (grasped + unlock action, a stand-in for the unlocking tool):
               the housing moves freely, resisted only by contact geometry.

Forces are not invented here: ``push`` and ``pull`` are the measured contact forces between the robot and
the housing, projected on the connector axis. The model only decides which constraint is active.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass
class LatchParams:
    gate_depth: float  # m, start of the snap ramp
    latch_depth: float  # m, depth at which hooks engage
    seated_depth: float  # m, back stop
    unlock_hold_time: float = 0.2  # s, unlock action must be held this long while grasped


class LatchState:
    """Batched latch state for ``n`` environments."""

    def __init__(self, n: int, device: str):
        self.latched = torch.zeros(n, dtype=torch.bool, device=device)
        self.open = torch.zeros(n, dtype=torch.bool, device=device)
        self.broken = torch.zeros(n, dtype=torch.bool, device=device)
        self.unlock_timer = torch.zeros(n, device=device)
        self.insertion_force = torch.full((n,), 45.0, device=device)  # sampled per episode
        self.withdrawal_force = torch.full((n,), 250.0, device=device)  # sampled per episode

    def reset(
        self,
        env_ids: torch.Tensor,
        latched: torch.Tensor,
        insertion_force: torch.Tensor,
        withdrawal_force: torch.Tensor,
    ) -> None:
        self.latched[env_ids] = latched
        self.open[env_ids] = False
        self.broken[env_ids] = False
        self.unlock_timer[env_ids] = 0.0
        self.insertion_force[env_ids] = insertion_force
        self.withdrawal_force[env_ids] = withdrawal_force


def latch_step(
    state: LatchState,
    p: LatchParams,
    depth: torch.Tensor,
    push: torch.Tensor,
    pull: torch.Tensor,
    grasped: torch.Tensor,
    unlock_cmd: torch.Tensor,
    dt: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Advance the latch state machine one physics step.

    Args:
        depth: insertion depth [m], shape (n,).
        push: measured axial force pushing the housing *into* the sleeve [N] (>= 0).
        pull: measured axial force pulling the housing *out* [N] (>= 0).
        grasped: housing is held by the robot (contact-sensor based).
        unlock_cmd: unlock action active.
        dt: physics step [s].

    Returns:
        (depth_max, depth_min) per env: the admissible depth interval for this step. ``inf``/``-inf`` mean
        unconstrained. The caller projects the housing pose into this interval along the connector axis.
    """
    inf = torch.full_like(depth, float("inf"))
    # Unlocking: grasp + unlock action accumulated for unlock_hold_time opens the latch arms. The accumulator
    # leaks at the same rate when not holding, so momentary contact chatter does not reset it but letting go does.
    holding = grasped & unlock_cmd
    state.unlock_timer = torch.clamp(state.unlock_timer + torch.where(holding, dt, -dt), 0.0, p.unlock_hold_time)
    state.open = state.unlock_timer >= p.unlock_hold_time
    # Latched housing pulled harder than its locked withdrawal force breaks (damage event).
    snapped = state.latched & ~state.open & (pull > state.withdrawal_force)
    state.broken |= snapped
    state.latched &= ~(state.open | snapped)
    # Snap-in: reaching the latch depth while not held open engages the hooks.
    state.latched |= (depth >= p.latch_depth) & ~state.open & ~state.broken

    depth_max = inf.clone()
    depth_min = -inf
    # Snap ramp: the latch arms deflect elastically between gate_depth and latch_depth, so the admissible depth
    # grows with the applied push (quasi-static linear ramp reaching latch_depth at the insertion force); at or
    # above the insertion force the arms snap through. A binary gate would chatter as the push fluctuates.
    gated = ~state.latched & ~state.open & ~state.broken & (push < state.insertion_force)
    ramp = (push / state.insertion_force).clamp(0.0, 1.0) * (p.latch_depth - p.gate_depth)
    depth_max = torch.where(gated, p.gate_depth + ramp, depth_max)
    # Latched: held seated.
    depth_min = torch.where(state.latched, torch.full_like(depth, p.latch_depth), depth_min)
    return depth_max, depth_min
