"""Policies ("brains") and the one contract all of them implement.

A policy maps the observation the environment returns to an action tensor. Everything that drives a robot
in SolarBench goes through this interface: the scripted oracle, a zero-action floor, an exported network,
and (via adapters added here) vision-language-action models and language models behind an HTTP endpoint.

Contract
--------
``act(obs)`` receives the dict returned by ``env.step`` / ``env.reset`` and returns a float tensor of shape
``(num_envs, action_dim)`` on the environment's device. ``reset(env_ids)`` is called with the indices of the
environments that just finished an episode. A policy must not touch the simulator through any other path,
unless it declares ``privileged = True``; privileged results are reported as a hardware ceiling, never
ranked against sensor-only policies.

Adding a policy: create ``solarbench/agents/<name>.py`` containing a factory ``f(arg, task, env) -> Policy``
decorated with ``@register("<name>")``. The module is imported on first use, so no shared file needs editing.
It is then selectable as ``--policy <name>`` or ``--policy <name>:<arg>``.
"""

from __future__ import annotations

import contextlib
import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

import torch


@runtime_checkable
class Policy(Protocol):
    name: str  # label written to result files
    privileged: bool  # True if it reads simulator state beyond the observation

    def reset(self, env_ids: torch.Tensor) -> None: ...

    def act(self, obs: dict[str, torch.Tensor]) -> torch.Tensor: ...


Factory = Callable[[str, str, object], Policy]
_REGISTRY: dict[str, Factory] = {}


def register(name: str) -> Callable[[Factory], Factory]:
    def deco(factory: Factory) -> Factory:
        if name in _REGISTRY:
            raise KeyError(f"policy {name!r} is already registered")
        _REGISTRY[name] = factory
        return factory

    return deco


def available() -> list[str]:
    return sorted(_REGISTRY)


def make_policy(spec: str, task: str, env) -> Policy:
    """Build a policy from ``name`` or ``name:arg`` for the unwrapped environment ``env``."""
    name, _, arg = spec.partition(":")
    if name not in _REGISTRY and name.isidentifier():
        module = f"{__name__}.{name}"
        try:
            importlib.import_module(module)
        except ModuleNotFoundError as err:
            if err.name != module:  # the module exists but one of its own imports is missing
                raise
    if name not in _REGISTRY:
        raise KeyError(f"unknown policy {name!r}; available: {', '.join(available())}")
    return _REGISTRY[name](arg, task, env)


class ZeroPolicy:
    """Zero actions: the floor. A task on which this succeeds has a broken success check."""

    name, privileged = "zero", False

    def __init__(self, env):
        self._shape, self._device = (env.num_envs, env.cfg.action_space), env.device

    def reset(self, env_ids):
        pass

    def act(self, obs):
        return torch.zeros(self._shape, device=self._device)


class OraclePolicy:
    """Scripted controller that reads exact simulator state: the ceiling for a robot, not a contestant."""

    name, privileged = "oracle", True

    def __init__(self, task: str, env):
        from solarbench.oracle import make_oracle

        self._oracle = make_oracle(task, env)

    def reset(self, env_ids):
        self._oracle.reset(env_ids)

    def act(self, obs):
        return self._oracle.act()


class JitPolicy:
    """TorchScript network mapping the ``policy`` observation to actions (e.g. an RSL-RL export)."""

    privileged = False

    def __init__(self, path: str, env):
        self._net = torch.jit.load(path, map_location=env.device).eval()
        self.name = "jit-" + Path(path).parent.parent.name

    def reset(self, env_ids):
        if hasattr(self._net, "reset"):  # recurrent exports reset per env; stateless exports take no arguments
            with contextlib.suppress(RuntimeError):
                self._net.reset(env_ids)

    def act(self, obs):
        return self._net(obs["policy"])


register("zero")(lambda arg, task, env: ZeroPolicy(env))
register("oracle")(lambda arg, task, env: OraclePolicy(task, env))
register("jit")(lambda arg, task, env: JitPolicy(arg, env))
