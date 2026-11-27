"""The phases policy (solarbench.agents.phases): its skill boundaries, against a stand-in environment and oracle."""

from types import SimpleNamespace

import pytest
import torch

from solarbench.agents import phases

CATALOGUE = {"task": "SolarBench-T2-MC4-G1-v0", "channels": [{"id": 1, "name": "policy"}]}


class Oracle:
    """Moves to ``phase_next`` on its next act, as the oracle's advance does (timer back to 0)."""

    def __init__(self, phase):
        self.phase, self.timer, self.phase_next, self.acts = torch.tensor([phase]), torch.tensor([0.4]), None, 0

    def act(self):
        self.acts += 1
        if self.phase_next is not None:
            self.phase[0], self.timer[0], self.phase_next = self.phase_next, 0.0, None
        return torch.full((1, 8), 0.5)


def policy(monkeypatch, phase, skill, answers, latched=True):
    p = phases.PhasesPolicy("m,url=http://unused/v1,notes=NOTES/probes/job_mc4.md", CATALOGUE)
    p._env = SimpleNamespace(num_envs=1, device="cpu", step_dt=1 / 30,
                             latch=SimpleNamespace(latched=torch.tensor([latched])))
    p._oracle, p._grip, p.calls, p._call = Oracle(phase), torch.tensor([1.0]), {0: []}, [None]
    p._skill = [skill]
    told = []

    def ask(env, text):
        told.append(text)
        p.calls[env].append({"retry": False})
        return answers.pop(0)

    monkeypatch.setattr(p, "_ask", ask)
    monkeypatch.setattr(p, "_state", lambda env: "state")
    return p, told


@pytest.mark.unit
def test_the_first_skill_is_chosen_before_the_oracle_acts_so_its_first_tick_is_the_oracles(monkeypatch):
    p, told = policy(monkeypatch, 0, None, ["grasp"])
    action = p.act({})
    assert told == [""] and p._oracle.acts == 1 and torch.equal(action[0], torch.full((8,), 0.5))


@pytest.mark.unit
def test_choosing_the_step_the_oracle_is_starting_runs_its_action_on_the_boundary_tick(monkeypatch):
    p, told = policy(monkeypatch, 5, ("unplug", 2.0), ["plug_in"])
    p._oracle.phase_next = 6
    action = p.act({})
    assert told == ["unplug finished\nstate"] and p._skill[0] == ("plug_in", 1 / 30)
    assert torch.equal(action[0], torch.full((8,), 0.5)) and int(p._oracle.phase[0]) == 6


@pytest.mark.unit
def test_any_other_choice_holds_the_robot_for_that_tick(monkeypatch):
    p, _ = policy(monkeypatch, 5, ("unplug", 2.0), ["grasp"])
    p._oracle.phase_next = 6
    action = p.act({})
    assert int(p._oracle.phase[0]) == 0 and p._skill[0] == ("grasp", 0.0)
    assert action[0, :6].abs().sum() == 0 and action[0, 6] == 1.0 and action[0, 7] == -1.0


@pytest.mark.unit
def test_a_plug_in_that_ends_unlatched_says_so(monkeypatch):
    p, told = policy(monkeypatch, 7, ("plug_in", 3.0), ["release"], latched=False)
    p._oracle.phase_next = 8
    p.act({})
    assert told == ["plug_in ended without the latch engaging\nstate"]
