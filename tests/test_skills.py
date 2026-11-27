"""Closed-loop skills (solarbench.agents.skills) and how the endpoint policy runs them between model calls."""

import json
import math

import numpy as np
import pytest
import torch

from solarbench import wire
from solarbench.agents import make_policy
from solarbench.agents.skills import Skill, _qmul, _zaxis, aligned
from solarbench.tasks.clamp_env import PRIVILEGED_FIELDS
from tests.test_endpoint import CATALOGUE, server  # noqa: F401  (the fake model server fixture)

AXIS = np.array([0.0, 0.342, 0.9397])
HEAD = np.array([0.42, 0.015, 0.439])
DOWN = np.array([1.0, 0.0, 0.0, 0.0])  # tool z pointing straight down


def readings(depth=0.0, drive=0.0, installed=1.0, engaged=False, side=(0.0, 0.0, 0.0)):
    tool = HEAD - depth * AXIS + np.array(side)
    return {"tool_pos": tool, "tool_quat": aligned(DOWN, AXIS), "head": HEAD, "axis": AXIS, "depth": depth,
            "drive": drive, "installed": installed, "engaged": engaged}


def angle_about_z(q0, q1) -> float:
    """Signed turn about the tool's own z from ``q0`` to ``q1``."""
    x0, y0, z0, w0 = q0
    r = _qmul(np.array([-x0, -y0, -z0, w0]), q1)  # q0^-1 * q1
    return 2 * math.atan2(r[2], r[3])


@pytest.mark.unit
def test_aligned_points_the_socket_into_the_bolt():
    assert np.allclose(_zaxis(aligned(DOWN, AXIS)), -AXIS / np.linalg.norm(AXIS), atol=1e-6)


@pytest.mark.unit
def test_seat_presses_lightly_on_the_axis_turns_slowly_and_unwinds_when_caught():
    skill = Skill("seat", {}, readings(), 30)
    position, quat = skill.step(readings(depth=0.0002))
    assert np.allclose(position, HEAD - (0.0002 + 0.0015) * AXIS, atol=1e-9)  # no offset yet: no correction
    assert angle_about_z(skill.quat, quat) == pytest.approx(0.0) and skill.turned == pytest.approx(0.25 / 30)
    skill.step(readings(depth=0.0002, drive=3.0))  # a corner caught: turn back
    assert skill.turned == pytest.approx(0.25 / 30 - 0.3 / 30)
    assert skill.step(readings(depth=0.004, engaged=True)).startswith("seated after")


@pytest.mark.unit
def test_seat_corrects_a_steady_offset_across_the_axis():
    skill = Skill("seat", {}, readings(), 30)
    for _ in range(20):
        position, _ = skill.step(readings(side=(0.0004, 0.0, 0.0)))
    assert position[0] < HEAD[0] - 0.0003  # aims the other way to cancel the 0.4 mm


@pytest.mark.unit
def test_tighten_to_slows_near_the_target_and_stops_on_drive_torque():
    skill = Skill("tighten_to", {"torque_Nm": 15.0}, readings(depth=0.004, engaged=True), 30)
    skill.step(readings(depth=0.004, engaged=True, drive=1.0))
    fast = skill.turned
    skill.step(readings(depth=0.004, engaged=True, drive=9.0))
    assert skill.turned - fast == pytest.approx(0.05 / 30)
    done = skill.step(readings(depth=0.004, engaged=True, drive=15.2, installed=15.1))
    assert done.startswith("stopped at drive torque 15.20") and "installed torque 15.10" in done


@pytest.mark.unit
def test_unload_and_retract_end_on_their_conditions():
    unload = Skill("unload", {}, readings(depth=0.004, engaged=True), 30)
    assert not isinstance(unload.step(readings(depth=0.004, drive=5.0)), str)
    assert unload.step(readings(depth=0.004, drive=0.05)).startswith("unloaded")
    retract = Skill("retract", {"mm": 50}, readings(depth=0.004), 30)
    position, _ = retract.step(readings(depth=0.004))
    assert np.allclose(position, HEAD + 0.05 * AXIS, atol=1e-3)
    assert retract.step(readings(depth=-0.049)).startswith("retracted")


@pytest.mark.unit
def test_a_skill_runs_between_model_calls_and_reports_back_as_the_calls_result(server):  # noqa: F811
    seen, replies, _ = server
    catalogue = json.loads(json.dumps(CATALOGUE))
    catalogue["channels"][1] = {"id": 2, "name": "proprio", "dtype": "f4", "shape": [7], "fields": [
        {"name": "tool_pos", "start": 0, "count": 3, "unit": "m"},
        {"name": "tool_quat", "start": 3, "count": 4, "unit": "xyzw"}]}
    catalogue["channels"][4]["fields"] = PRIVILEGED_FIELDS
    policy, _ = make_policy("endpoint:m,tools=on,privileged=on,skills=on", catalogue, None)
    policy.reset(torch.arange(1), ["work order"])

    def obs(tick, depth, engaged):
        tool = HEAD - depth * AXIS
        privileged = np.zeros(35, np.float32)
        privileged[19:22], privileged[22:25] = HEAD - tool, AXIS
        privileged[26], privileged[28] = 1.0 / 16, float(engaged)
        return {"clock": torch.tensor([[tick, wire.AWAKE]], dtype=torch.int32),
                "proprio": torch.tensor([[*tool, *aligned(DOWN, AXIS)]], dtype=torch.float32),
                "completions": torch.zeros(1, 2, 8, dtype=torch.int32), "policy": torch.from_numpy(privileged[None])}

    seat = {"id": "s1", "type": "function", "function": {"name": "seat", "arguments": "{}"}}
    replies += [{"content": "", "tool_calls": [seat]}, {"content": "", "tool_calls": [
        {"id": "d1", "type": "function", "function": {"name": "done", "arguments": "{}"}}]}]
    policy.act(obs(0, 0.0, False))  # the model calls seat; nothing is sent this tick
    records = policy.act(obs(1, 0.0, False)).numpy().view(wire.COMMAND)[..., 0]
    assert len(seen) == 1 and records["opcode"][0, 0] == wire.TOOL_POSE
    assert records["timeout"][0, 0] == 1 and records["flags"][0, 0] == wire.REPLACE
    records = policy.act(obs(2, 0.004, True)).numpy().view(wire.COMMAND)[..., 0]
    assert len(seen) == 2 and records["opcode"][0, 0] == wire.DONE
    result = seen[1]["messages"][-1]
    assert result["role"] == "tool" and result["tool_call_id"] == "s1" and result["content"].startswith("seat finished")
    assert {t["function"]["name"] for t in seen[0]["tools"]} >= {"seat", "tighten_to", "unload", "retract", "aim"}
