"""The chat-completions adapter (solarbench.agents.endpoint), against a local stand-in for a model server."""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest
import torch

from solarbench import wire
from solarbench.agents import make_policy, prompts
from solarbench.agents.endpoint import parse, parse_call

TASK = "SolarBench-T3-ClampTighten-UR16e-R2-v0"
CATALOGUE = {
    "wire": [1, 0], "task": TASK, "tick_hz": 30, "opcodes": [wire.TOOL_POSE, wire.DONE], "max_depth": 1,
    "wake": ["idle"],
    "channels": [
        {"id": 1, "name": "clock", "dtype": "clock", "shape": []},
        {"id": 2, "name": "proprio", "dtype": "f4", "shape": [5], "fields": [
            {"name": "joint_pos", "start": 0, "count": 2, "unit": "rad"},
            {"name": "tool_pos", "start": 2, "count": 3, "unit": "m"}]},
        {"id": 3, "name": "wrench", "dtype": "f4", "shape": [6], "fields": [
            {"name": "force", "start": 0, "count": 3, "unit": "N"},
            {"name": "torque", "start": 3, "count": 3, "unit": "N*m"}]},
        {"id": 4, "name": "completions", "dtype": "completion", "shape": [2]},
        {"id": 5, "name": "policy", "dtype": "f4", "shape": [35], "privileged": True},
    ],
}
POSE = 'The bolt is below.\n{"position": [0.5, 0.0, 0.25], "quaternion": [0, 2, 0, 0]}'


@pytest.fixture
def server(monkeypatch):
    """A server that answers each request with the next scripted reply and keeps what it was sent."""
    seen, replies, together = [], [], []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append({"path": self.path, "key": self.headers.get("Authorization"), **body})
            if together:
                together[0].wait()  # answers only once that many requests are in flight at the same time
            reply = replies.pop(0) if replies else POSE  # a reply text, or a whole message (tool calls)
            answer = {"choices": [{"message": reply if isinstance(reply, dict) else {"content": reply}}],
                      "usage": {"prompt_tokens": 900, "completion_tokens": 40}}
            data = json.dumps(answer).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("SOLARBENCH_ENDPOINT_URL", f"http://127.0.0.1:{httpd.server_port}/v1")
    monkeypatch.setenv("SOLARBENCH_ENDPOINT_KEY", "not-a-real-key")
    yield seen, replies, together
    httpd.shutdown()


def frame(layout, ticks, flags=wire.AWAKE, completions=()):
    n = len(ticks)
    obs = {"clock": torch.tensor([[tick, flags] for tick in ticks], dtype=torch.int32),
           "proprio": torch.arange(5 * n, dtype=torch.float32).reshape(n, 5) / 8,
           "wrench": torch.full((n, 6), -1.5)}
    ended = np.zeros((n, 2), wire.COMPLETION)
    for env, record in completions:
        ended[env, -1] = record
    obs["completions"] = torch.from_numpy(ended.view("<i4").reshape(n, 2, 8))
    return {name: obs[name] for name, _, _ in layout.blocks}


@pytest.mark.unit
def test_only_a_reply_that_ends_with_a_whole_command_is_a_command():
    opcode, args = parse(POSE)
    assert opcode == wire.TOOL_POSE and args == [0.5, 0.0, 0.25, 0.0, 1.0, 0.0, 0.0]  # the quaternion is normalised
    assert parse('{"done": true}') == (wire.DONE, [])
    # the object may span lines or sit in a code fence, as models write it; thinking left in the text is skipped
    for reply in ('Lower it.\n{\n  "position": [0.5, 0.0, 0.25],\n  "quaternion": [0, 2, 0, 0]\n}',
                  '```json\n{"position": [0.5, 0.0, 0.25], "quaternion": [0, 2, 0, 0]}\n```',
                  '<think>{"done": true}</think>{"position": [0.5, 0.0, 0.25], "quaternion": [0, 2, 0, 0]}'):
        assert parse(reply) == (opcode, args)
    for reply in ("", "I would move down.", "[1, 2, 3]", '{"position": [0, 0, 0]}',
                  '{"position": [0, 0, NaN], "quaternion": [0, 0, 0, 1]}',
                  '{"position": [0, 0, 0], "quaternion": [0, 0, 0, 0]}',
                  '{"position": [0, 0, true], "quaternion": [0, 0, 0, 1]}',
                  '{"position": [0, 0, 0], "quaternion": [0, 0, 0, 1]}\nDone.'):
        assert parse(reply) is None


@pytest.mark.unit
def test_a_round_sends_the_fixed_text_first_and_returns_one_record_per_environment(server):
    seen, _, together = server
    policy, layout = make_policy("endpoint:some/model-27b,wrench=on,temperature=0.2,seed=7", CATALOGUE, None)
    assert [name for name, _, _ in layout.blocks] == ["clock", "proprio", "wrench", "completions"]
    assert not layout.privileged and (layout.depth, layout.wake) == (1, "idle")
    assert policy.name == "endpoint-some-model-27b-force"
    policy.reset(torch.arange(3), ["work order A", "work order B", "work order C"])
    together.append(threading.Barrier(3, timeout=10))  # the three requests must be in flight together
    records = policy.act(frame(layout, [0, 0, 0])).numpy().view(wire.COMMAND)[..., 0]
    together.clear()
    assert records.shape == (3, 1) and (records["opcode"] == wire.TOOL_POSE).all() and (records["id"] == 1).all()
    assert records["args"][0, 0].tolist() == [0.5, 0.0, 0.25, 0.0, 1.0, 0.0, 0.0, 0, 0, 0, 0, 0]
    first = sorted(seen, key=lambda request: request["messages"][1]["content"])[0]
    assert first["path"] == "/v1/chat/completions" and first["key"] == "Bearer not-a-real-key"
    assert (first["model"], first["temperature"], first["seed"]) == ("some/model-27b", 0.2, 7)
    assert first["chat_template_kwargs"] == {"enable_thinking": True}
    system, work_order, round_1 = first["messages"]
    assert system["content"].startswith(prompts.body(TASK, True)) and '{"done": true}' in system["content"]
    assert work_order == {"role": "user", "content": "work order A"}
    assert round_1["content"].splitlines() == [
        "tick 0", "joint_pos [rad]: 0.0000, 0.1250", "tool_pos [m]: 0.2500, 0.3750, 0.5000",
        "force [N]: -1.5000, -1.5000, -1.5000", "torque [N*m]: -1.5000, -1.5000, -1.5000"]

    seen.clear()
    ended = (1, wire.TOOL_POSE, wire.STALLED, 0, 44, [0.002, 0.01, 12.5, 3.25])
    records = policy.act(frame(layout, [45, 3, 3], completions=[(0, ended)])).numpy().view(wire.COMMAND)[..., 0]
    assert (records["id"] == 2).all() and records["based_on"].ravel().tolist() == [45, 3, 3]
    second = sorted(seen, key=lambda request: request["messages"][1]["content"])[0]["messages"]
    assert second[:3] == first["messages"] and second[3] == {"role": "assistant", "content": POSE}
    assert second[4]["content"].splitlines()[:3] == [
        "tick 45", "your last command stalled before arriving, 0.0020 m and 0.0100 rad from its target",
        "at its end: force 12.5000 N, torque about tool z 3.2500 N*m"]
    assert policy.calls[0] == [{"wall_s": pytest.approx(0, abs=10), "tokens_read": 900, "tokens_written": 40,
                                "tokens_cached": None, "finish": None, "parsed": True, "retry": False}] * 2
    assert "not-a-real-key" not in json.dumps([policy.settings, policy.calls])
    assert policy.settings["endpoint"] == "local" and "127.0.0.1" not in json.dumps(policy.settings)


@pytest.mark.unit
def test_without_force_the_model_is_given_no_force(server):
    seen, _, _ = server
    policy, layout = make_policy("endpoint:m", CATALOGUE, None)
    assert "wrench" not in [name for name, _, _ in layout.blocks] and policy.name == "endpoint-m-noforce"
    policy.reset([0], ["work order"])
    ended = (1, wire.TOOL_POSE, wire.OK, 0, 9, [0.0, 0.0, 0.0, 0.0])
    policy.act(frame(layout, [0]))
    policy.act(frame(layout, [10], completions=[(0, ended)]))
    text = json.dumps(seen[-1]["messages"])
    assert seen[-1]["messages"][0]["content"].startswith(prompts.body(TASK, False))
    assert "your last command arrived" in text and "force" not in text.replace("Nothing reports force", "")


@pytest.mark.unit
def test_an_unreadable_reply_is_asked_for_once_more_then_counted_and_the_robot_holds(server):
    seen, replies, _ = server
    policy, layout = make_policy("endpoint:m", CATALOGUE, None)
    policy.reset([0], ["work order"])
    replies += ["I think the bolt is tight.", "It is tight."]
    records = policy.act(frame(layout, [0])).numpy().view(wire.COMMAND)[..., 0]
    assert records["opcode"].ravel().tolist() == [wire.NOP] and len(seen) == 2
    assert seen[1]["messages"][-1]["content"].startswith("That reply did not end with a command")
    assert [(call["parsed"], call["retry"]) for call in policy.calls[0]] == [(False, False), (False, True)]
    seen.clear()
    replies += ["Still thinking.", '{"done": true}']
    records = policy.act(frame(layout, [1])).numpy().view(wire.COMMAND)[..., 0]
    assert seen[0]["messages"][-1]["content"].startswith("Your last reply did not end with a command")
    assert records["opcode"].ravel().tolist() == [wire.DONE] and records["id"].ravel().tolist() == [1]
    policy.reset([0], ["work order"])
    assert len(policy.finished) == 1 and len(policy.finished[0]) == 4 and policy.calls[0] == []


@pytest.mark.unit
def test_only_environments_whose_queue_is_empty_are_asked(server):
    seen, _, _ = server
    policy, layout = make_policy("endpoint:m", CATALOGUE, None)
    policy.reset([0, 1], ["work order", "work order"])
    busy = frame(layout, [5, 5])
    busy["clock"][1, 1] = 0  # environment 1 has a command running
    records = policy.act(busy).numpy().view(wire.COMMAND)[..., 0]
    assert len(seen) == 1 and records["opcode"].ravel().tolist() == [wire.TOOL_POSE, wire.NOP]
    assert policy.act(frame(layout, [6, 6], flags=0)) is None and len(seen) == 1


@pytest.mark.unit
def test_rounds_are_capped_reasoning_can_be_switched_off_and_each_call_is_logged(server, tmp_path):
    seen, _, _ = server
    log = tmp_path / "calls.jsonl"
    policy, layout = make_policy(f"endpoint:m,reasoning=off,rounds=2,log={log}", CATALOGUE, None)
    assert policy.name == "endpoint-m-noforce-noreasoning" and policy.settings["reasoning"] is False
    policy.reset([0], ["work order"])
    for tick in range(4):
        policy.act(frame(layout, [tick]))
    assert len(seen) == 2 and seen[0]["chat_template_kwargs"] == {"enable_thinking": False}
    lines = [json.loads(line) for line in log.read_text().splitlines()]
    assert [(line["env"], line["episode_on_env"], line["round"], line["tick"]) for line in lines] == [
        (0, 0, 1, 0), (0, 0, 2, 1)]
    assert lines[0]["tokens_read"] == 900 and lines[0]["reply"] == POSE and lines[0]["command"][0] == wire.TOOL_POSE
    assert "not-a-real-key" not in log.read_text() and "127.0.0.1" not in log.read_text()


@pytest.mark.unit
def test_the_address_comes_from_the_name_or_the_environment(server, monkeypatch):
    seen, _, _ = server
    url = os.environ["SOLARBENCH_ENDPOINT_URL"]
    monkeypatch.delenv("SOLARBENCH_ENDPOINT_URL")
    policy, layout = make_policy(f"endpoint:m,url={url}", CATALOGUE, None)
    policy.reset([0], ["work order"])
    policy.act(frame(layout, [0]))
    assert len(seen) == 1 and url not in json.dumps(policy.settings)
    with pytest.raises(ValueError, match="no endpoint"):
        make_policy("endpoint:m", CATALOGUE, None)
    with pytest.raises(ValueError, match="got 'm,colour=red'"):
        make_policy("endpoint:m,colour=red", CATALOGUE, None)


@pytest.mark.unit
def test_assisted_commands_become_poses_from_the_tool_pose_now():
    from solarbench.agents.endpoint import _axis

    here = (np.array([0.4, 0.0, 0.5]), np.array([0.0, 0.0, 0.0, 1.0]))  # socket pointing up (+z)
    opcode, args = parse('{"aim": [0.42, 0.015, 0.44], "socket_toward": [0, -0.342, -0.94]}', here)
    assert opcode == wire.TOOL_POSE and args[:3] == [0.42, 0.015, 0.44]
    assert np.allclose(_axis(args[3:], 2), np.array([0, -0.342, -0.94]) / np.hypot(0.342, 0.94), atol=1e-6)
    _, args = parse('{"aim": [0, 0, 0], "socket_toward": [0, 0, -2]}', here)  # straight back: half a turn about x
    assert np.allclose(np.abs(args[3:]), [1, 0, 0, 0], atol=1e-6)
    _, args = parse('{"push_mm": -10}', here)
    assert np.allclose(args, [0.4, 0.0, 0.49, 0, 0, 0, 1])
    _, args = parse('{"turn_deg": 400}', here)  # cut to 90 degrees about tool z
    assert np.allclose(args[3:], [0, 0, np.sqrt(0.5), np.sqrt(0.5)])
    _, args = parse('{"push_mm": 2, "turn_deg": 90}', here)  # press while turning
    assert np.allclose(args, [0.4, 0.0, 0.502, 0, 0, np.sqrt(0.5), np.sqrt(0.5)])
    assert parse('{"push_mm": "far"}', here) is None and parse('{"turn_deg": 30}') is None  # needs the pose


@pytest.mark.unit
def test_with_assisted_commands_the_model_is_told_where_the_socket_points(server):
    seen, replies, _ = server
    catalogue = json.loads(json.dumps(CATALOGUE))
    catalogue["channels"][1] = {"id": 2, "name": "proprio", "dtype": "f4", "shape": [7], "fields": [
        {"name": "tool_pos", "start": 0, "count": 3, "unit": "m"}, {"name": "tool_quat", "start": 3, "count": 4,
                                                                    "unit": "xyzw"}]}
    policy, layout = make_policy("endpoint:m,commands=assist", catalogue, None)
    assert policy.name.endswith("-assist") and policy.settings["commands"] == "assist"
    policy.reset(torch.arange(1), ["work order"])
    obs = {"clock": torch.tensor([[0, wire.FIRST | wire.AWAKE]], dtype=torch.int32),
           "proprio": torch.tensor([[0.4, 0.0, 0.5, 0.0, 0.0, 0.0, 1.0]]),
           "completions": torch.zeros(1, 2, 8, dtype=torch.int32)}
    replies.append('{"push_mm": 5}')
    records = policy.act(obs).numpy().view(wire.COMMAND)[..., 0]
    assert "socket points along (tool z, base frame): 0.0000, 0.0000, 1.0000" in seen[-1]["messages"][-1]["content"]
    assert '"push_mm"' in seen[-1]["messages"][0]["content"]
    assert records["opcode"][0, 0] == wire.TOOL_POSE and np.allclose(records["args"][0, 0, :3], [0.4, 0.0, 0.505])


@pytest.mark.unit
def test_privileged_readings_are_read_by_name_and_give_depth_offset_and_tilt():
    from solarbench.agents.endpoint import describe
    from solarbench.tasks.clamp_env import PRIVILEGED_FIELDS

    catalogue = json.loads(json.dumps(CATALOGUE))
    catalogue["channels"][1] = {"id": 2, "name": "proprio", "dtype": "f4", "shape": [7], "fields": [
        {"name": "tool_pos", "start": 0, "count": 3, "unit": "m"},
        {"name": "tool_quat", "start": 3, "count": 4, "unit": "xyzw"}]}
    catalogue["channels"][4]["fields"] = PRIVILEGED_FIELDS
    layout = wire.Layout(catalogue, {**make_policy("endpoint:m,privileged=on,url=http://x/v1", catalogue, None)[0]
                                     .selection})
    policy = np.zeros((1, 35), np.float32)
    policy[0, 19:22] = [0.001, 0.0, 0.004]  # head top 4 mm along the axis from the face, 1 mm to the side
    policy[0, 22:25] = [0.0, 0.0, 1.0]
    policy[0, 26], policy[0, 27], policy[0, 28] = 0.5, 0.25, 1.0
    frame = {"clock": np.zeros(1, wire.CLOCK), "proprio": np.array([[0, 0, 0, 1, 0, 0, 0]], np.float32),
             "completions": np.zeros((1, 2), wire.COMPLETION), "policy": policy}
    text = describe(catalogue, layout, frame, 0, None)
    assert "installed_torque [N*m]: 8.0000" in text and "drive_torque [N*m]: 5.0000" in text
    assert "socket depth on the head: 4.00 mm (the top of the head is 4.00 mm inside the socket)" in text
    assert "socket axis off the bolt axis: 1.00 mm (the socket's centre is at -1.00, 0.00, 0.00 mm" in text
    assert "socket axis tilted from the bolt axis: 0.00 deg" in text  # tool z (0, 0, -1) against the axis (0, 0, 1)
    here = '{"aim": [0.00100, 0.00000, 0.00000], "socket_toward": [0.0000, 0.0000, -1.0000]}'
    assert f"to centre the socket on the axis where it is now: {here}" in text  # no earlier pose: the axis itself
    # the last pose asked for 0.5 mm to one side of the axis and the socket settled 1 mm to the other: aim 1.5 mm over
    text = describe(catalogue, layout, frame, 0, None, target=np.array([0.0015, 0.0, 0.0]))
    assert '"aim": [0.00250, 0.00000, 0.00450]' in text  # 0.5 mm out from the head top (z 4 mm), shifted by the error
    assert '50 mm out from the head top on the axis: {"aim": [0.00250, 0.00000, 0.05400]' in text


@pytest.mark.unit
def test_notes_are_appended_to_the_system_message(tmp_path):
    notes = tmp_path / "lessons.md"
    notes.write_text("## Notes\nPress lightly.\n")
    policy, _ = make_policy(f"endpoint:m,url=http://x/v1,notes={notes}", CATALOGUE, None)
    assert policy._system.endswith("## Notes\nPress lightly.\n") and policy.settings["notes"] == "lessons.md"


@pytest.mark.unit
def test_kept_thinking_goes_back_with_the_reply_and_the_template_is_told(server):
    seen, replies, _ = server
    policy, layout = make_policy("endpoint:m,keep_thinking=on", CATALOGUE, None)
    policy.reset(torch.arange(1), ["work order"])
    policy._ask(0, "state 1", 0)
    policy._ask(0, "state 2", 1)
    assert seen[-1]["chat_template_kwargs"] == {"enable_thinking": True, "truncate_history_thinking": False}
    assert policy.settings["keep_thinking"] is True


@pytest.mark.unit
def test_with_tools_each_state_is_the_result_of_the_last_call_and_thinking_stays(server):
    seen, replies, _ = server
    catalogue = json.loads(json.dumps(CATALOGUE))
    catalogue["channels"][1] = {"id": 2, "name": "proprio", "dtype": "f4", "shape": [7], "fields": [
        {"name": "tool_pos", "start": 0, "count": 3, "unit": "m"},
        {"name": "tool_quat", "start": 3, "count": 4, "unit": "xyzw"}]}
    policy, _ = make_policy("endpoint:m,tools=on", catalogue, None)
    assert policy.name.endswith("-tools") and "call exactly one tool" in policy._system
    policy.reset(torch.arange(1), ["work order"])
    obs = {"clock": torch.tensor([[0, wire.FIRST | wire.AWAKE]], dtype=torch.int32),
           "proprio": torch.tensor([[0.4, 0.0, 0.5, 0.0, 0.0, 0.0, 1.0]]),
           "completions": torch.zeros(1, 2, 8, dtype=torch.int32)}
    call = {"id": "c1", "type": "function", "function": {"name": "push", "arguments": '{"mm": 5}'}}
    replies += [{"content": "", "reasoning_content": "press it on", "tool_calls": [call]},
                {"content": "I am done talking."},  # no call: asked again with another seed...
                {"content": "Still talking."}]  # ...and then counted as unreadable
    records = policy.act(obs).numpy().view(wire.COMMAND)[..., 0]
    assert np.allclose(records["args"][0, 0, :3], [0.4, 0.0, 0.505]) and seen[0]["tools"][0]["function"]["name"]
    assert "## The robot now" in seen[0]["messages"][1]["content"]
    obs["clock"] = torch.tensor([[16, wire.AWAKE]], dtype=torch.int32)
    assert policy.act(obs) is not None and policy._unread == {0}
    sent = seen[1]["messages"]
    assert sent[2] == {"role": "assistant", "content": "", "reasoning_content": "press it on", "tool_calls": [call]}
    assert sent[3]["role"] == "tool" and sent[3]["tool_call_id"] == "c1"
    assert (seen[1]["seed"], seen[2]["seed"]) == (0, 1)
    assert parse_call({"function": {"name": "turn", "arguments": "not json"}}, (np.zeros(3), np.eye(4)[3])) is None


@pytest.mark.unit
def test_thinking_is_read_under_either_field_name():
    from solarbench.agents.endpoint import _thought

    assert _thought({"reasoning_content": "a"}) == "a" and _thought({"reasoning": "b"}) == "b" and _thought({}) == ""


@pytest.mark.unit
def test_a_tunnelled_endpoint_can_be_recorded_as_remote():
    policy, _ = make_policy("endpoint:m,url=http://127.0.0.1:8000/v1,host=remote", CATALOGUE, None)
    assert policy.settings["endpoint"] == "remote"
    assert make_policy("endpoint:m,url=http://127.0.0.1:8000/v1", CATALOGUE, None)[0].settings["endpoint"] == "local"
