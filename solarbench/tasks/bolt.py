"""Torque-angle model of an M8 clamp bolt (ASSUMPTIONS P7).

The environment uses :func:`bolt_friction`: the bolt joint's dry friction is scheduled to the installed-torque
requirement, so resistance is solved implicitly by the physics engine. (An earlier constraint-projection variant,
:func:`bolt_step`, teleported the light bolt link and let the socket turn through it; kept for unit tests only.)


theta is the tightening angle [rad] (0 = snug, < 0 = loose). Installed torque:
    tau_req(theta) = tau_run                      theta < 0   (running down)
                   = tau_run + k * theta          theta >= 0  (clamp-up; k from snug-to-spec angle)
Each physics step the *measured* torque applied through the socket (tightening positive) decides the
admissible angle interval, exactly like the MC4 latch: the bolt can only turn in the direction of the applied
torque and only as far as that torque can drive it. Preloaded bolts must first break away
(|tau| >= breakaway_ratio * tau_req). Exceeding the module manual's maximum torque is a damage event.
Preload is reported as F = T / (K d).
"""

from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass
class BoltParams:
    """Scalars, or per-env tensors (the environment resamples them every episode)."""

    tau_run: float | torch.Tensor
    stiffness: float | torch.Tensor  # N*m/rad past snug
    breakaway_ratio: float | torch.Tensor
    tau_max_spec: float  # module manual maximum (over-torque threshold)
    nut_factor: float | torch.Tensor
    diameter: float

    def tau_req(self, theta: torch.Tensor) -> torch.Tensor:
        return self.tau_run + self.stiffness * theta.clamp(min=0.0)

    def preload(self, theta: torch.Tensor) -> torch.Tensor:
        return torch.where(theta > 0, self.tau_req(theta) / (self.nut_factor * self.diameter), torch.zeros_like(theta))


def bolt_step(p: BoltParams, theta: torch.Tensor, tau: torch.Tensor, engaged: torch.Tensor
              ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Admissible (theta_min, theta_max) for this step and the over-torque flag.

    Args:
        theta: tightening angle [rad]. tau: applied torque through the socket, tightening positive [N*m].
        engaged: socket seated on the head (no torque is transmitted otherwise).
    """
    tau = torch.where(engaged, tau, torch.zeros_like(tau))
    inf = torch.full_like(theta, float("inf"))
    # tightening: may advance up to where the installed torque equals the applied torque
    can_tighten = tau >= p.tau_run
    theta_max = torch.where(can_tighten, torch.maximum((tau - p.tau_run) / p.stiffness, theta), theta)
    # loosening: preloaded bolts need breakaway torque, then only the running torque resists
    tau_l = -tau
    need = torch.where(theta > 0, p.breakaway_ratio * p.tau_req(theta), torch.full_like(theta, p.tau_run))
    theta_min = torch.where(tau_l >= need, -inf, theta)
    over = p.tau_req(theta) > p.tau_max_spec
    return theta_min, theta_max, over


def bolt_friction(p: BoltParams, theta: torch.Tensor, loosening: bool) -> torch.Tensor:
    """Dry-friction torque [N*m] for the bolt joint (solved implicitly by the physics engine).

    The joint resists rotation up to this torque and slips beyond it, so the bolt turns only when the socket really
    applies more than the installed-torque requirement; the reaction is felt at the robot's wrist. Loosening a
    preloaded bolt needs the breakaway torque instead.
    """
    tau = p.tau_req(theta)
    if loosening:
        tau = torch.where(theta > 0, p.breakaway_ratio * tau, tau)
    return tau
