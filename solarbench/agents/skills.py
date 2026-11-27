"""Closed-loop skills a model can call as tools (endpoint policy, ``tools=on,skills=on``).

A skill runs for many ticks: each tick it sends one tool pose (a one-tick ``TOOL_POSE`` record) worked out from the
latest readings, and it decides itself when it is finished. The model chooses which skill to run and when; the
skill does what a single pose per round cannot: keep the socket on the bolt's axis while it moves (a slow integral
of the measured offset), search for the hex flats by turning slowly under a light press, and stop tightening on a
torque reading. The method and its constants are the scripted oracle's (``solarbench/oracle/clamp_oracle.py``).

Skills read the privileged channel (head position, bolt axis, depth, drive and installed torque, engaged), so a
run that uses them is privileged, and it is a far easier task than the benchmark's: the model no longer has to
control the arm, only to sequence these skills.
"""

from __future__ import annotations

import math

import numpy as np

SEEK_RATE = 0.25  # rad/s while searching for the flats; their ±2.3° window then lasts ~0.16 s
CAUGHT = 2.0  # N·m of drive torque before the socket counts as seated: a corner is caught, unwind
TURN_RATE, FINAL_RATE = 1.0, 0.05  # rad/s while tightening, and once the drive torque passes half the target
PRESS_SEAT, PRESS_TURN = 0.0015, 0.007  # m past the current depth while seating; m past the head top while turning
BIAS_GAIN, BIAS_LIMIT = 0.15, 0.015  # integral of the measured offset (per tick, m)


def _qmul(a, b) -> np.ndarray:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz])


def _zaxis(q) -> np.ndarray:
    x, y, z, w = q
    return np.array([2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y)])


def _xaxis(q) -> np.ndarray:
    x, y, z, w = q
    return np.array([1 - 2 * (y * y + z * z), 2 * (x * y + w * z), 2 * (x * z - w * y)])


def _spin(q, angle: float) -> np.ndarray:
    """``q`` turned by ``angle`` about its own z axis."""
    return _qmul(q, np.array([0.0, 0.0, math.sin(angle / 2), math.cos(angle / 2)]))


def aligned(q, axis) -> np.ndarray:
    """``q`` turned as little as possible so that tool z points into the bolt (along minus ``axis``)."""
    u, v = _zaxis(q), -np.asarray(axis, float) / np.linalg.norm(axis)
    if u @ v < -0.9999:
        delta = np.array([*_xaxis(q), 0.0])
    else:
        delta = np.array([*np.cross(u, v), 1 + u @ v])
        delta /= np.linalg.norm(delta)
    return _qmul(delta, q)


DESCRIPTIONS = {
    "seat": "Closed loop: keep the socket centred on the bolt's axis, press lightly and turn slowly until the hex "
            "flats line up and the socket drops onto the head (engaged), unwinding if a corner catches. Start "
            "with the socket on the axis just off the head top. Ends when seated, or after max_s seconds.",
    "tighten_to": "Closed loop: turn the seated socket in the tightening direction, keeping it pressed on and "
                  "centred, slowing near the end, and stop as soon as the wrist's drive torque reaches torque_Nm. "
                  "Ends then, or if the socket comes off, or after max_s seconds.",
    "unload": "Closed loop: turn back slowly, keeping the socket on, until the drive torque is near zero (under "
              "0.1 N·m), so the socket no longer grips the flats. The bolt stays tight.",
    "retract": "Closed loop: move the socket straight out along the bolt's axis until its face is mm millimetres "
               "from the head top, keeping it centred and straight.",
}
PARAMETERS = {
    "seat": {"max_s": {"type": "number", "description": "time limit in seconds (default 10)"}},
    "tighten_to": {"torque_Nm": {"type": "number", "description": "drive torque to stop at, in N·m"},
                   "max_s": {"type": "number", "description": "time limit in seconds (default 15)"}},
    "unload": {},
    "retract": {"mm": {"type": "number", "description": "distance of the socket face from the head top, mm"}},
}
REQUIRED = {"seat": [], "tighten_to": ["torque_Nm"], "unload": [], "retract": ["mm"]}


def tools() -> list[dict]:
    return [{"type": "function", "function": {"name": name, "description": DESCRIPTIONS[name], "parameters": {
        "type": "object", "properties": PARAMETERS[name], "required": REQUIRED[name]}}} for name in DESCRIPTIONS]


class Skill:
    """One skill running on one environment. ``step`` takes this tick's readings and returns the tool pose to
    command, or a sentence saying how the skill ended."""

    def __init__(self, name: str, args: dict, readings: dict, tick_hz: float):
        self.name, self.args, self.dt, self.ticks = name, args, 1.0 / tick_hz, 0
        limit = {"seat": 10.0, "tighten_to": 15.0, "unload": 3.0, "retract": 5.0}[name]
        self.limit = float(args.get("max_s", limit))
        self.quat = aligned(readings["tool_quat"], readings["axis"])  # commanded orientation; turns accumulate
        self.bias = np.zeros(3)
        self.turned = 0.0

    def _target(self, r: dict, goal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """The pose to command for a position ``goal`` on the axis: the integral of the measured offset corrects
        the arm's steady error across the axis always, and along it only while the socket is off the head, so a
        press stays a small proportional push instead of winding up."""
        axis = r["axis"]
        err = goal - r["tool_pos"]
        along = (err @ axis) * axis
        self.bias = np.clip(self.bias + BIAS_GAIN * ((err - along) + (r["depth"] < -0.0005) * along),
                            -BIAS_LIMIT, BIAS_LIMIT)
        return goal + self.bias, self.quat

    def step(self, r: dict) -> tuple[np.ndarray, np.ndarray] | str:
        self.ticks += 1
        elapsed = self.ticks * self.dt
        head, axis, depth, drive = r["head"], r["axis"], r["depth"], r["drive"]
        if self.name == "seat":
            if r["engaged"] and depth > 0.0025:
                return f"seated after {elapsed:.1f} s: the head is {1e3 * depth:.1f} mm inside the socket"
            if elapsed > self.limit:
                return f"not seated after {elapsed:.1f} s (turned {math.degrees(self.turned):.0f} degrees)"
            rate = -math.copysign(0.3, drive) if abs(drive) > CAUGHT else SEEK_RATE
            self.quat, self.turned = _spin(self.quat, rate * self.dt), self.turned + rate * self.dt
            return self._target(r, head - (max(depth, 0.0) + PRESS_SEAT) * axis)
        if self.name == "tighten_to":
            target = float(self.args["torque_Nm"])
            if drive >= target:
                return (f"stopped at drive torque {drive:.2f} N·m after turning {math.degrees(self.turned):.0f} "
                        f"degrees; installed torque {r['installed']:.2f} N·m")
            if not r["engaged"] and depth < 0.002:
                return f"the socket came off the head after turning {math.degrees(self.turned):.0f} degrees"
            if elapsed > self.limit:
                return f"stopped by the time limit at drive torque {drive:.2f} N·m"
            rate = FINAL_RATE if drive > 0.5 * target else TURN_RATE
            self.quat, self.turned = _spin(self.quat, rate * self.dt), self.turned + rate * self.dt
            return self._target(r, head - PRESS_TURN * axis)
        if self.name == "unload":
            if abs(drive) < 0.1:
                return f"unloaded: drive torque {drive:.2f} N·m, installed torque {r['installed']:.2f} N·m"
            if elapsed > self.limit:
                return f"still loaded after {elapsed:.1f} s: drive torque {drive:.2f} N·m"
            self.quat = _spin(self.quat, -math.copysign(0.3, drive) * self.dt)
            return self._target(r, head - PRESS_TURN * axis)
        out = float(self.args["mm"]) / 1000  # retract
        if -depth >= out - 0.002:
            return f"retracted: the socket face is {-1e3 * depth:.0f} mm from the head top"
        if elapsed > self.limit:
            return f"stopped by the time limit with the face {-1e3 * depth:.0f} mm from the head top"
        return self._target(r, head + out * axis)
