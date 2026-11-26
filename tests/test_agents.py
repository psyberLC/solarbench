"""The policy contract (solarbench.agents), exercised without a simulator."""

from types import SimpleNamespace

import pytest
import torch

from solarbench.agents import Policy, available, make_policy, register


def fake_env(num_envs=3, action_dim=6):
    return SimpleNamespace(num_envs=num_envs, device="cpu", cfg=SimpleNamespace(action_space=action_dim))


def test_builtins_are_registered():
    assert {"oracle", "zero", "jit"} <= set(available())


def test_zero_policy_meets_the_contract():
    policy = make_policy("zero", "any-task", fake_env())
    assert isinstance(policy, Policy) and not policy.privileged
    action = policy.act({"policy": torch.zeros(3, 35)})
    assert action.shape == (3, 6) and not action.any()
    policy.reset(torch.tensor([0, 2]))


def test_unknown_policy_names_the_alternatives():
    with pytest.raises(KeyError, match="available: .*zero"):
        make_policy("no-such-policy", "any-task", fake_env())


def test_a_name_cannot_be_registered_twice():
    with pytest.raises(KeyError, match="already registered"):
        register("zero")(lambda arg, task, env: None)
