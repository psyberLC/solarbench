"""A model behind a chat-completions endpoint, driving the robot one tool pose per round (profile R2).

Where the model runs is a URL. A local server for open weights and a remote service look the same from here.
Settings come with the policy name, or else from the environment variable named beside each:
    --policy endpoint:<model>[,wrench=on][,reasoning=on][,temperature=0][,max_tokens=4096][,seed=0][,rounds=40]
                             [,log=<file.jsonl>][,url=<base url>][,commands=pose][,privileged=off][,notes=<file>]
                             [,keep_thinking=off][,tools=off][,skills=off][,host=local|remote]
    SOLARBENCH_ENDPOINT_URL        the server's base address, ending in /v1 (or url=)
    SOLARBENCH_ENDPOINT_LOG        a JSON-lines file that gets one line per call (or log=)
    SOLARBENCH_ENDPOINT_KEY        sent as a bearer token if set; never stored, logged or written to a result
``reasoning`` asks the server's chat template to let the model think first (``enable_thinking``), or not.
``rounds`` caps the calls per episode; once it is reached the robot holds until the episode ends.
``commands=assist`` adds commands that leave the rotation arithmetic to the adapter (aim the socket along a direction,
push along it, turn about it), each turned into one pose from the tool pose now, and tells the model where the socket
points. The model still decides every move; the arm still moves within its own limits.
``privileged=on`` also gives the model the task's privileged channel, read by its field names (where the head is from
the tool, the bolt's axis and angle, installed and drive torque, whether the socket counts as seated), and how deep,
how far off the axis and how tilted the socket is. The result is then marked privileged.
``notes=<file>`` appends that text file to the system message (advice written for the model, such as lessons from
earlier attempts); the result records the file's name.
``keep_thinking=on`` sends the model's earlier thinking back with its earlier replies and asks the chat template to
keep it (``truncate_history_thinking`` off), so it need not work everything out again each round. The conversation
then grows by each round's thinking: cap it with the server's thinking budget and ``rounds``.
``skills=on`` (with ``tools=on`` and ``privileged=on``) adds closed-loop skills as tools: seat, tighten_to, unload,
retract (``solarbench/agents/skills.py``). While one runs, the policy sends a pose every tick without asking the
model; when it ends, how it ended goes back as that call's result. This makes the task far easier: the model only
sequences skills.
``host=remote`` records the model as remote when the URL is local only because of a tunnel (the default is read
from the URL's host).
``tools=on`` drives the model through native tool calls instead of a line of JSON: aim, push, turn, push_and_turn,
pose and done (the commands of ``commands=assist``, which it implies). Each call's result is the next state report,
sent as the tool's result, so the conversation stays one tool loop and a chat template that drops thinking before
the latest user message keeps all of it. A reply without a usable call is asked for once more with another seed.

What the model reads: the description of its body and how to reply (the system message), the work order, then one
message per round with the selected channels as text. Its own earlier replies stay in the conversation, so each
request extends the last and a server's prompt cache keeps the prefix. What it writes: reasoning if it wishes, then
one JSON object, which becomes one ``TOOL_POSE`` or ``DONE`` record (docs/interface.md, section 4). A reply that
cannot be read is asked for once more; if that one cannot be read either, no command is sent, the call is counted
as unreadable, and the model is told so in the next round.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import torch

from solarbench import wire
from solarbench.agents import prompts, register, select, skills

REPLY = """
## Commands
Each round you send one command: a pose for the tool frame, in the base frame. The arm moves the tool there within \
its limits and stops when it arrives, when it can go no further, or when the command's time runs out. You are then \
told how the command ended and what the robot senses, and asked for the next command.

Reason as you wish, then end your reply with one line of JSON and nothing after it:
{"position": [x, y, z], "quaternion": [x, y, z, w]}
or, when the job is finished or cannot be finished:
{"done": true}
"""
REPLY_ASSIST = """
## Commands
Each round you send one command. The arm moves the tool within its limits and stops when it arrives, when it can go \
no further, or when the command's time runs out. You are then told how the command ended and what the robot senses, \
including the direction the socket points, and asked for the next command. The commands:
- {"aim": [x, y, z], "socket_toward": [dx, dy, dz]}: put the centre of the socket's open face at the point (x, y, z), \
with the open face pointing along (dx, dy, dz), both in the base frame. The direction is where tool z points; it need \
not be a unit vector. The tool turns as little as it can to get there.
- {"push_mm": d}: move the tool d mm straight along the way the socket points, keeping its orientation. A negative d \
moves it back.
- {"turn_deg": a}: turn the tool a degrees about its own z axis, keeping its position. A positive a turns clockwise as \
seen from behind the tool, which tightens a right-hand thread. At most 90 degrees per command; more is cut to 90.
- {"push_mm": d, "turn_deg": a}: both at once: turn while pressing (or pulling) along the socket's axis.
- {"position": [x, y, z], "quaternion": [x, y, z, w]}: a pose for the tool frame in the base frame.
- {"done": true}: the job is finished or cannot be finished.

Reason as you wish, then end your reply with one command, as one line of JSON, and nothing after it.
"""
PRIVILEGED = """
## Privileged readings
Each round also gives what a scripted controller with full knowledge of the simulation reads:
- head_top_minus_tool: the vector from the centre of the socket's face to the centre of the top of the head.
- bolt_axis: the direction the bolt's axis points out of the head.
- bolt_angle: how far the bolt has been turned in the tightening direction; 0 when it is snug, negative before.
- installed_torque: the tightening torque the bolt has reached (what the job is judged on).
- drive_torque: the torque wrist 3 applies, tightening positive. It is not limited by the force-torque sensor's range.
- engaged: 1 while the socket counts as seated on the head, 0 otherwise.
- where the top of the head is, how deep the socket is on it (said in words), how far and which way the socket is \
off the bolt's axis, and the angle between them.
- three ready commands: one that centres the socket on the bolt's axis where it is now, one that centres it 0.5 mm \
out from the head top, and one that puts it 50 mm out on the axis. All point the socket into the bolt and allow for \
where your last pose actually left the socket (the arm settles a little off its target, consistently the same way).
"""
TOOLS_REPLY = """
## Commands
You act through the tools you are given: call exactly one tool each turn. The arm moves the tool within its limits \
and stops when it arrives, when it can go no further, or when the command's time runs out; the tool's result then \
tells you how the command ended and what the robot senses. Keep calling tools until the job is finished or cannot \
be finished, then call done.
"""


def _tool(name: str, description: str, **properties) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties, "required": list(properties)}}}


def _vector(n: int, what: str) -> dict:
    return {"type": "array", "items": {"type": "number"}, "minItems": n, "maxItems": n, "description": what}


TOOLS = [
    _tool("aim", "Put the centre of the socket's open face at a point, with the open face pointing along a direction, "
          "both in the base frame. The tool turns as little as it can to get there.",
          aim=_vector(3, "the point [x, y, z] in metres"),
          socket_toward=_vector(3, "the direction tool z points; need not be a unit vector")),
    _tool("push", "Move the tool straight along the way the socket points, keeping its orientation. Negative moves "
          "it back.", mm={"type": "number", "description": "distance in millimetres"}),
    _tool("turn", "Turn the tool about its own z axis, keeping its position. Positive turns clockwise as seen from "
          "behind the tool, which tightens a right-hand thread. At most 90 degrees; more is cut to 90.",
          deg={"type": "number", "description": "angle in degrees"}),
    _tool("push_and_turn", "Both at once: turn while pressing (or pulling) along the socket's axis.",
          mm={"type": "number", "description": "distance in millimetres"},
          deg={"type": "number", "description": "angle in degrees, at most 90"}),
    _tool("pose", "Send the tool frame to a pose in the base frame.", position=_vector(3, "[x, y, z] in metres"),
          quaternion=_vector(4, "[x, y, z, w]")),
    _tool("done", "The job is finished or cannot be finished."),
]
_CALLS = {"aim": lambda a: {"aim": a.get("aim"), "socket_toward": a.get("socket_toward")},
          "push": lambda a: {"push_mm": a.get("mm")}, "turn": lambda a: {"turn_deg": a.get("deg")},
          "push_and_turn": lambda a: {"push_mm": a.get("mm"), "turn_deg": a.get("deg")},
          "pose": lambda a: {"position": a.get("position"), "quaternion": a.get("quaternion")},
          "done": lambda a: {"done": True}}
AGAIN = 'That reply did not end with a command that could be read. Send only the line of JSON.'
UNREAD = "Your last reply did not end with a command that could be read.\n"
ENDED = {wire.OK: "arrived", wire.STALLED: "stalled before arriving", wire.TIMED_OUT: "ran out of time",
         wire.PREEMPTED: "was dropped", wire.UNKNOWN: "was refused: unknown command",
         wire.INVALID: "was refused: invalid argument", wire.FULL: "was refused: queue full"}
ENCODING = "text, 4 decimals"
OPTIONS = {"wrench": "off", "reasoning": "on", "temperature": "0", "max_tokens": "4096", "seed": "0", "rounds": "40",
           "log": "", "url": "", "commands": "pose", "privileged": "off", "notes": "", "keep_thinking": "off",
           "tools": "off", "skills": "off", "host": ""}
_DECODER = json.JSONDecoder()


def _last_object(reply: str):
    """The JSON object that ends ``reply`` (after any reasoning, and ignoring a code fence around it), or ``None``."""
    text = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip().strip("`").strip()
    for start in (i for i in range(len(text) - 1, -1, -1) if text[i] == "{"):
        try:
            data, end = _DECODER.raw_decode(text, start)
        except ValueError:
            continue
        return data if not text[end:].strip() else None
    return None


def _number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _qmul(a, b) -> np.ndarray:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz])


def _axis(q, k: int) -> np.ndarray:
    """Where tool axis ``k`` (0 x, 1 y, 2 z) points in the base frame, for a tool orientation ``q`` (xyzw)."""
    x, y, z, w = q
    return np.array([(1 - 2 * (y * y + z * z), 2 * (x * y + w * z), 2 * (x * z - w * y)),
                     (2 * (x * y - w * z), 1 - 2 * (x * x + z * z), 2 * (y * z + w * x)),
                     (2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y))][k])


def _assisted(data: dict, position: np.ndarray, quaternion: np.ndarray):
    """An aim, push or turn command as a target pose, from the tool pose now; ``None`` if it is none of those."""
    if "aim" in data or "socket_toward" in data:
        point, toward = data.get("aim"), data.get("socket_toward")
        if not all(isinstance(v, list) and len(v) == 3 and all(map(_number, v)) for v in (point, toward)):
            return None
        v, u = np.array(toward, float), _axis(quaternion, 2)
        if np.linalg.norm(v) < 1e-6:
            return None
        v /= np.linalg.norm(v)
        if u @ v < -0.9999:  # straight back: half a turn about tool x
            delta = np.array([*_axis(quaternion, 0), 0.0])
        else:  # the shortest rotation that takes tool z onto v
            delta = np.array([*np.cross(u, v), 1 + u @ v])
            delta /= np.linalg.norm(delta)
        return np.array(point, float), _qmul(delta, quaternion)
    if "push_mm" in data or "turn_deg" in data:  # either, or both at once: press while turning
        push, turn = data.get("push_mm", 0), data.get("turn_deg", 0)
        if not (_number(push) and _number(turn)):
            return None
        half = math.radians(max(-90.0, min(90.0, turn))) / 2
        return (position + push / 1000 * _axis(quaternion, 2),
                _qmul(quaternion, np.array([0.0, 0.0, math.sin(half), math.cos(half)])))
    return None


def _tool_pose(catalogue: dict, frame: dict[str, np.ndarray], env: int) -> tuple[np.ndarray, np.ndarray]:
    """The measured tool position and orientation (unit quaternion) of one environment."""
    fields = {f["name"]: f for c in catalogue["channels"] if c["name"] == "proprio" for f in c.get("fields", ())}
    row = frame["proprio"][env]
    p, q = fields["tool_pos"]["start"], fields["tool_quat"]["start"]
    quat = np.array(row[q : q + 4], float)
    return np.array(row[p : p + 3], float), quat / np.linalg.norm(quat)


def parse(reply: str, pose: tuple[np.ndarray, np.ndarray] | None = None) -> tuple[int, list[float]] | None:
    """The opcode and arguments of the command that ends a reply, or ``None`` if it does not end with one.
    Given the tool ``pose`` now, aim, push and turn commands are read too (``commands=assist``)."""
    return _command(_last_object(reply), pose)


def _thought(message: dict) -> str:
    """The model's thinking: llama.cpp calls the field reasoning_content, newer vLLM calls it reasoning."""
    return message.get("reasoning_content") or message.get("reasoning") or ""


def parse_call(call: dict, pose: tuple[np.ndarray, np.ndarray]) -> tuple[int, list[float]] | None:
    """The command a native tool call asks for (``tools=on``), or ``None`` if it names no tool or its arguments
    cannot be read."""
    function = call.get("function") or {}
    arguments = function.get("arguments") or {}
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments or "{}")
        except ValueError:
            return None
    if function.get("name") not in _CALLS or not isinstance(arguments, dict):
        return None
    return _command(_CALLS[function["name"]](arguments), pose)


def _command(data, pose: tuple[np.ndarray, np.ndarray] | None) -> tuple[int, list[float]] | None:
    if not isinstance(data, dict):
        return None
    if data.get("done") is True:
        return wire.DONE, []
    position, quaternion = data.get("position"), data.get("quaternion")
    if pose is not None and (target := _assisted(data, *pose)) is not None:
        position, quaternion = [float(x) for x in target[0]], [float(x) for x in target[1]]
    if not (isinstance(position, list) and isinstance(quaternion, list) and (len(position), len(quaternion)) == (3, 4)):
        return None
    numbers = [*position, *quaternion]
    if not all(map(_number, numbers)):
        return None
    norm = math.sqrt(sum(x * x for x in quaternion))
    if norm < 1e-6:
        return None
    return wire.TOOL_POSE, [*map(float, position), *(x / norm for x in quaternion)]


def describe(catalogue: dict, layout: wire.Layout, frame: dict[str, np.ndarray], env: int, sent: int | None,
             pose: tuple[np.ndarray, np.ndarray] | None = None, target: np.ndarray | None = None) -> str:
    """One environment's frame as text: the tick, how the last command ended, then each field of each channel, and,
    given the tool ``pose``, the direction the socket points."""
    lines = [f"tick {int(frame['clock'][env]['tick'])}"]
    for record in frame["completions"][env][::-1] if "completions" in frame else ():
        if sent is not None and record["id"] == sent and record["opcode"] == wire.TOOL_POSE:
            status, result = int(record["status"]), record["result"]
            ended = ENDED.get(status, f"ended with status {status}")
            lines.append(f"your last command {ended}, {result[0]:.4f} m and {result[1]:.4f} rad from its target")
            if "wrench" in frame:
                lines.append(f"at its end: force {result[2]:.4f} N, torque about tool z {result[3]:.4f} N*m")
            break
    by_name = {channel["name"]: channel for channel in catalogue["channels"]}
    for name, _, _ in layout.blocks:
        for field in by_name[name].get("fields", ()):
            values = frame[name][env][field["start"] : field["start"] + field["count"]] * field.get("scale", 1.0)
            lines.append(f"{field['name']} [{field['unit']}]: " + ", ".join(f"{value:.4f}" for value in values))
    if pose is not None:
        lines.append("socket points along (tool z, base frame): " + ", ".join(f"{v:.4f}" for v in _axis(pose[1], 2)))
    if "head_top_minus_tool" in by_field(catalogue, "policy"):
        lines += _seating(catalogue, frame, env, target)
    return "\n".join(lines)


def by_field(catalogue: dict, channel: str) -> dict:
    return {f["name"]: f for c in catalogue["channels"] if c["name"] == channel for f in c.get("fields", ())}


def _seating(catalogue: dict, frame: dict[str, np.ndarray], env: int, target: np.ndarray | None) -> list[str]:
    """Where the socket is on the head, from the privileged channel, and three ready aims along the axis. ``target`` is
    the position the last pose command asked for: the gap between it and where the socket settled is carried into
    the suggested aims, as an integrator would."""
    fields, row = by_field(catalogue, "policy"), frame["policy"][env]
    rel, axis = (np.array(row[fields[k]["start"] : fields[k]["start"] + 3], float) for k in ("head_top_minus_tool",
                                                                                              "bolt_axis"))
    tool, quat = _tool_pose(catalogue, frame, env)
    head, depth = tool + rel, float(rel @ axis)
    side = -(rel - depth * axis)  # from the bolt's axis to the socket's centre, across the axis
    lateral = float(np.linalg.norm(side))
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, float(-_axis(quat, 2) @ axis)))))
    near = target is not None and np.linalg.norm(target - tool) < 0.01  # the last pose's error applies here
    asked = (target - head) - ((target - head) @ axis) * axis if near else side  # across the axis
    shift = asked - side

    def fmt(v, scale=1.0, digits=4) -> str:
        return ", ".join(f"{round(scale * x, digits) + 0.0:.{digits}f}" for x in v)  # + 0.0: no "-0.0000"

    def aim(out: float) -> str:
        return f'{{"aim": [{fmt(head + out * axis + shift, digits=5)}], "socket_toward": [{fmt(-axis)}]}}'

    where = (f"the socket's face is {-1e3 * depth:.2f} mm short of the head top; the head is not in the socket"
             if depth < 0 else f"the top of the head is {1e3 * depth:.2f} mm inside the socket")
    return [f"head top centre [m]: {fmt(head)}",
            f"socket depth on the head: {1e3 * depth:.2f} mm ({where})",
            f"socket axis off the bolt axis: {1e3 * lateral:.2f} mm (the socket's centre is at "
            f"{fmt(side, 1e3, 2)} mm from the axis, base frame)",
            f"socket axis tilted from the bolt axis: {tilt:.2f} deg",
            f"to centre the socket on the axis where it is now: {aim(-depth)}",
            f"to centre it 0.5 mm out from the head top: {aim(0.0005)}",
            f"to put it 50 mm out from the head top on the axis: {aim(0.050)}"]


class EndpointPolicy:
    def __init__(self, arg: str, catalogue: dict):
        model, *given = arg.split(",")
        given = dict(option.split("=", 1) for option in given)
        if not model or set(given) - set(OPTIONS):
            raise ValueError(f"endpoint:<model>[,{'][,'.join(f'{k}=' for k in OPTIONS)}], got {arg!r}")
        options = {k: given.get(k, os.environ.get(f"SOLARBENCH_ENDPOINT_{k.upper()}", v)) for k, v in OPTIONS.items()}
        if not options["url"]:
            raise ValueError("no endpoint: set SOLARBENCH_ENDPOINT_URL or pass url=")
        self._url = options["url"].rstrip("/") + "/chat/completions"
        self._log, self._log_lock = options["log"], threading.Lock()
        wrench, reasoning = options["wrench"] == "on", options["reasoning"] == "on"
        if options["commands"] not in ("pose", "assist"):
            raise ValueError(f"commands=pose or commands=assist, got {options['commands']!r}")
        self._tools = options["tools"] == "on"
        self._skills = options["skills"] == "on"
        if self._skills and not (self._tools and options["privileged"] == "on"):
            raise ValueError("skills=on needs tools=on and privileged=on")
        self._assist = options["commands"] == "assist" or self._tools
        privileged = options["privileged"] == "on"
        offered = {channel["name"] for channel in catalogue["channels"]}
        wanted = ["proprio", *(["wrench"] if wrench else []), *(["completions"] if "completions" in offered else []),
                  *(["policy"] if privileged else [])]
        self.selection = {**select(catalogue, *wanted), "depth": 1, "wake": "idle"}
        self.name = ("endpoint-" + re.sub(r"[^A-Za-z0-9.]+", "-", model) + ("-force" if wrench else "-noforce")
                     + ("" if reasoning else "-noreasoning") + ("-assist" if self._assist else "")
                     + ("-privileged" if privileged else "") + ("-tools" if self._tools else "")
                     + ("-skills" if self._skills else ""))
        if options["host"] not in ("", "local", "remote"):
            raise ValueError(f"host=local or host=remote, got {options['host']!r}")
        local = (options["host"] == "local" if options["host"]
                 else urlparse(self._url).hostname in ("localhost", "127.0.0.1", "::1"))
        # what a result has to say about the model (docs/interface.md, section 10): not the address, not the key
        self.settings = {"model": model, "endpoint": "local" if local else "remote", "encoding": ENCODING,
                         "reasoning": reasoning, "temperature": float(options["temperature"]),
                         "max_tokens": int(options["max_tokens"]), "seed": int(options["seed"]),
                         "rounds": int(options["rounds"]), "commands": options["commands"], "privileged": privileged,
                         "notes": os.path.basename(options["notes"]),
                         "keep_thinking": options["keep_thinking"] == "on", "tools": self._tools,
                         "skills": self._skills}
        self._catalogue, self._layout = catalogue, wire.Layout(catalogue, self.selection)
        notes = "\n" + Path(options["notes"]).read_text() if options["notes"] else ""
        reply = TOOLS_REPLY if self._tools else REPLY_ASSIST if self._assist else REPLY
        self._system = (prompts.body(catalogue["task"], wrench) + reply
                        + (PRIVILEGED if privileged else "") + notes)
        self._messages: dict[int, list[dict]] = {}
        self._sent: dict[int, int | None] = {}  # id of the last command each environment sent
        self._target: dict[int, np.ndarray | None] = {}  # position the last pose command asked for
        self._call: dict[int, str | None] = {}  # id of the tool call the next state report answers (tools=on)
        self._skill: dict[int, skills.Skill | None] = {}  # the closed-loop skill running on each environment
        self._episode: dict[int, int] = {}  # how many episodes each environment has started
        self._unread: set[int] = set()
        self.calls: dict[int, list[dict]] = {}  # per environment, one entry per call in the episode under way
        self.finished: list[list[dict]] = []  # the calls of each episode that has ended, in the order they ended
        self._pool: ThreadPoolExecutor | None = None

    def attach(self, env) -> None:
        """A privileged selection hands over the environment; this policy reads only the channel, never the env."""

    def reset(self, env_ids, work_orders):
        for env, work_order in zip(torch.as_tensor(env_ids).tolist(), work_orders, strict=True):
            if self.calls.get(env):
                self.finished.append(self.calls[env])
            self._messages[env] = [{"role": "system", "content": self._system}, {"role": "user", "content": work_order}]
            self._sent[env], self._target[env], self._call[env], self.calls[env] = None, None, None, []
            self._skill[env] = None
            self._episode[env] = self._episode.get(env, -1) + 1
            self._unread.discard(env)

    def _post(self, messages: list[dict], retry: bool = False) -> dict:
        s = self.settings
        body = {"model": s["model"], "messages": messages, "temperature": s["temperature"],
                "max_tokens": s["max_tokens"], "seed": s["seed"] + retry,
                **({"tools": TOOLS + (skills.tools() if self._skills else [])} if self._tools else {}),
                "chat_template_kwargs": {"enable_thinking": s["reasoning"],
                                         **({"truncate_history_thinking": False} if s["keep_thinking"] else {})}}
        headers = {"Content-Type": "application/json"}
        if key := os.environ.get("SOLARBENCH_ENDPOINT_KEY"):
            headers["Authorization"] = f"Bearer {key}"
        request = urllib.request.Request(self._url, json.dumps(body).encode(), headers)
        for attempt in range(3):  # a server that is restarting gets a minute; an error it answers with stops the run
            try:
                with urllib.request.urlopen(request, timeout=1800) as response:
                    return json.load(response)
            except urllib.error.HTTPError:
                raise
            except (urllib.error.URLError, ConnectionError):
                if attempt == 2:
                    raise
                time.sleep(30)
        raise AssertionError("unreachable")

    def _ask(self, env: int, text: str, tick: int, pose=None) -> tuple[int, list[float]] | None:
        if self._tools:
            return self._ask_tools(env, text, tick, pose)
        messages = self._messages[env]
        messages.append({"role": "user", "content": text})
        command = None
        for retry in (False, True):
            started = time.perf_counter()
            answer = self._post(messages)
            choice = answer["choices"][0]
            message = choice["message"]
            reply, thought = message.get("content") or "", _thought(message)
            kept = {"reasoning_content": thought} if self.settings["keep_thinking"] and thought else {}
            messages.append({"role": "assistant", "content": reply, **kept})
            command, usage = parse(reply, pose), answer.get("usage", {})
            call = {"wall_s": time.perf_counter() - started, "tokens_read": usage.get("prompt_tokens"),
                    "tokens_written": usage.get("completion_tokens"),
                    "tokens_cached": (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
                    "finish": choice.get("finish_reason"), "parsed": command is not None, "retry": retry}
            self.calls[env].append(call)
            self._write_log(env, tick, call, reply, thought, command)
            if command is not None:
                break
            if not retry:
                messages.append({"role": "user", "content": AGAIN})
        return command

    def _ask_tools(self, env: int, text: str, tick: int, pose) -> tuple[int, list[float]] | None:
        """One turn of the tool loop: the state report goes back as the result of the last call (or, before the
        first call, after the work order), and the model's first tool call becomes the command."""
        messages = self._messages[env]
        if self._call[env]:
            messages.append({"role": "tool", "tool_call_id": self._call[env], "content": text})
        elif len(messages) == 2:  # first turn: the state follows the work order in the same message
            messages[1] = {"role": "user", "content": messages[1]["content"] + "\n\n## The robot now\n" + text}
        else:
            messages.append({"role": "user", "content": text})
        for retry in (False, True):
            started = time.perf_counter()
            answer = self._post(messages, retry)
            choice = answer["choices"][0]
            message = choice["message"]
            reply, thought = message.get("content") or "", _thought(message)
            tool_calls = message.get("tool_calls") or []
            command, usage = self._read_call(tool_calls[0], pose) if tool_calls else None, answer.get("usage", {})
            call = {"wall_s": time.perf_counter() - started, "tokens_read": usage.get("prompt_tokens"),
                    "tokens_written": usage.get("completion_tokens"),
                    "tokens_cached": (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
                    "finish": choice.get("finish_reason"), "parsed": command is not None, "retry": retry}
            self.calls[env].append(call)
            shown = (reply + "\n" + json.dumps(tool_calls[0]["function"])).strip() if tool_calls else reply
            self._write_log(env, tick, call, shown, thought, command)
            if command is not None:
                first = {**tool_calls[0], "id": tool_calls[0].get("id") or f"call-{len(messages)}"}
                messages.append({"role": "assistant", "content": reply, "tool_calls": [first],
                                 **({"reasoning_content": thought} if thought else {})})
                self._call[env] = first["id"]
                return command
        messages.append({"role": "assistant", "content": reply, **({"reasoning_content": thought} if thought else {})})
        self._call[env] = None
        return None

    def _read_call(self, call: dict, pose):
        """A pose command, or ``("skill", name, arguments)`` for a skill (skills=on), or ``None``."""
        function = call.get("function") or {}
        if self._skills and function.get("name") in skills.DESCRIPTIONS:
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except ValueError:
                return None
            required = skills.REQUIRED[function["name"]]
            if not isinstance(arguments, dict) or not all(_number(arguments.get(k)) for k in required):
                return None
            return "skill", function["name"], arguments
        return parse_call(call, pose)

    def _readings(self, frame: dict, env: int) -> dict:
        """What a skill reads each tick, from proprio and the privileged channel."""
        tool, quat = _tool_pose(self._catalogue, frame, env)
        fields, row = by_field(self._catalogue, "policy"), frame["policy"][env]

        def field(name):
            f = fields[name]
            return np.array(row[f["start"] : f["start"] + f["count"]], float) * f.get("scale", 1.0)

        rel, axis = field("head_top_minus_tool"), field("bolt_axis")
        return {"tool_pos": tool, "tool_quat": quat, "head": tool + rel, "axis": axis, "depth": float(rel @ axis),
                "drive": float(field("drive_torque")[0]), "installed": float(field("installed_torque")[0]),
                "engaged": bool(field("engaged")[0] > 0.5)}

    def _write_log(self, env, tick, call, reply, thought, command) -> None:
        if not self._log:
            return
        line = {"env": env, "episode_on_env": self._episode[env], "round": len(self.calls[env]), "tick": tick,
                **call, "reply": reply, "reasoning_chars": len(thought), "reasoning": thought,
                "command": None if command is None else list(command) if command[0] == "skill"
                else [command[0], [round(x, 5) for x in command[1]]]}
        with self._log_lock, open(self._log, "a") as f:  # requests for several environments end at once
            f.write(json.dumps(line) + "\n")

    def act(self, obs):
        frame = {name: array.cpu().numpy() for name, array in obs.items()}
        frame["clock"] = np.ascontiguousarray(frame["clock"]).view(wire.CLOCK)[:, 0]
        if "completions" in frame:
            frame["completions"] = np.ascontiguousarray(frame["completions"]).view(wire.COMPLETION)[..., 0]
        clock = frame["clock"]
        records = np.zeros((len(clock), 1), wire.COMMAND)
        rounds = self.settings["rounds"]
        awake = [env for env in range(len(clock)) if clock[env]["flags"] & wire.AWAKE]
        if not awake:
            return None
        asked, prefixes = [], {}
        for env in awake:
            if self._skill.get(env) is not None:  # a running skill answers this tick itself
                done = self._skill[env].step(self._readings(frame, env))
                if not isinstance(done, str):
                    self._command(records, env, clock, (wire.TOOL_POSE, [*done[0], *done[1]]), skill=True)
                    continue
                prefixes[env] = f"{self._skill[env].name} finished: {done}\n"
                self._skill[env] = None
            if sum(not call["retry"] for call in self.calls[env]) < rounds:
                asked.append(env)
        if not asked:
            return torch.from_numpy(records.view("<i4").reshape(len(clock), 1, 16)).to(obs["clock"].device)
        texts, poses = [], [_tool_pose(self._catalogue, frame, env) if self._assist else None for env in asked]
        for env, pose in zip(asked, poses, strict=True):
            sent = None if env in prefixes else self._sent[env]  # a skill's last one-tick record says nothing
            text = describe(self._catalogue, self._layout, frame, env, sent, pose, self._target.get(env))
            texts.append(prefixes.get(env, "") + (UNREAD + text if env in self._unread else text))
        ticks = [int(clock[env]["tick"]) for env in asked]
        self._pool = self._pool or ThreadPoolExecutor(max_workers=len(clock))
        for env, command in zip(asked, self._pool.map(self._ask, asked, texts, ticks, poses), strict=True):
            if command is None:
                self._unread.add(env)
                continue
            self._unread.discard(env)
            if command[0] == "skill":  # starts next tick, from that tick's readings
                self._skill[env] = skills.Skill(command[1], command[2], self._readings(frame, env),
                                                self._catalogue["tick_hz"])
                continue
            self._command(records, env, clock, command)
        return torch.from_numpy(records.view("<i4").reshape(len(clock), 1, 16)).to(obs["clock"].device)

    def _command(self, records, env: int, clock, command, skill: bool = False) -> None:
        """Write one command record; a skill's pose runs for one tick and replaces anything still running."""
        self._sent[env] = (self._sent[env] or 0) + 1
        record = records[env, 0]
        record["opcode"], record["id"], record["based_on"] = command[0], self._sent[env], clock[env]["tick"]
        record["args"][: len(command[1])] = command[1]
        if skill:
            record["timeout"], record["flags"] = 1, wire.REPLACE
        self._target[env] = np.array(command[1][:3]) if command[0] == wire.TOOL_POSE else None


register("endpoint")(EndpointPolicy)
