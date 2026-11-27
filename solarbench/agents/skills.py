"""Closed-loop skills a model can call as tools (endpoint policy, ``tools=on,skills=on``).

A skill runs for many ticks: each tick it sends one tool pose (a one-tick ``TOOL_POSE`` record) worked out from the
latest readings, and it decides itself when it is finished. The model chooses which skill to run and when; the
skill does what a single pose per round cannot: keep the socket on the bolt's axis while it moves (a slow integral
of the measured offset), search for the hex flats by turning slowly under a light press, and stop tightening on a
torque reading. The method and its constants are the scripted oracle's (``solarbench/oracle/clamp_oracle.py``).

With the privileged channel, skills read the head position, bolt axis, depth, drive and installed torque and the
engaged flag directly. Without it they use what any policy has: the head position and axis the work order states
(to the millimetre), the tool pose, and the wrist force-torque sensor. That sensor clips at 10 N·m, below the job's
window, so above 9.5 N·m the drive torque is extrapolated from a straight line fitted to the sensor's own readings
between 2 and 9.5 N·m against the angle the tool has actually turned in the same tightening (the bolt's own
torque-angle line; the commanded angle runs ahead of it while turning fast). And the work order's head position is
only good to about half a millimetre, so in contact the skill follows the sensed sideways force (as in peg-in-hole
insertion) instead of holding the work order's axis. Either way the task is far
easier than the benchmark's: the model no longer controls the arm, it only sequences these skills.
"""

from __future__ import annotations

import math

import numpy as np

SEEK_RATE = 0.25  # rad/s while searching for the flats; their ±2.3° window then lasts ~0.16 s
CAUGHT = 2.0  # N·m of drive torque before the socket counts as seated: a corner is caught, unwind
TURN_RATE, FINAL_RATE = 1.0, 0.05  # rad/s while tightening, and once the drive torque passes half the target
PRESS_SEAT, PRESS_TURN = 0.0015, 0.007  # m past the current depth while seating; m past the head top while turning
BIAS_GAIN, BIAS_LIMIT = 0.15, 0.015  # integral of the measured offset (per tick, m)
COMPLY = 2e-6  # m per N per tick: in contact without privilege, move with the sensed sideways force
CONTACT = 3.0  # N pressing along the axis that counts as contact


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
            "with the socket on the axis just off the head top, reached in two aims: first the readings' ready "
            "'put it 50 mm out' aim, then the ready 'centre it 0.5 mm out from the head top' aim. A single move "
            "straight from far away can clip the head and jam the socket on it askew, and seat cannot recover "
            "from that. Ends when seated, or after max_s seconds.",
    "tighten_to": "Closed loop: turn the seated socket in the tightening direction, keeping it pressed on and "
                  "centred, slowing near the end, and stop as soon as the wrist's drive torque reaches torque_Nm. "
                  "The installed torque ends within about 0.1 N·m of where it stops. The job accepts 14 to 18 N·m "
                  "installed, so aim for the middle (about 15.5-16) to keep a margin on both sides. Ends then, "
                  "or if the socket comes off, or after max_s seconds.",
    "unload": "Closed loop: turn back slowly, keeping the socket on, until the drive torque is near zero (under "
              "0.1 N·m), so the socket no longer grips the flats. The bolt stays tight. Do this before "
              "retract: a socket still loaded grips the flats and the retract sticks.",
    "retract": "Closed loop: move the socket straight out along the bolt's axis until its face is mm millimetres "
               "from the head top, keeping it centred and straight. Unload first. 50 mm or more clears the job's "
               "30 mm condition with a margin.",
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
        self.samples: list[tuple[float, float]] = []  # (angle the tool turned, sensed torque) while in range
        self.previous, self.measured = np.asarray(readings["tool_quat"], float), 0.0  # measured turn about tool z
        self.quiet = 0  # consecutive ticks of near-zero sensed torque (unload without privilege)

    def _target(self, r: dict, goal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """The pose to command for a position ``goal`` on the axis: the integral of the measured offset corrects
        the arm's steady error across the axis always, and along it only while the socket is off the head, so a
        press stays a small proportional push instead of winding up. Without privilege, once pressing on the head,
        the sideways correction follows the sensed force instead (the work order's axis is only good to ~0.5 mm)."""
        axis = r["axis"]
        err = goal - r["tool_pos"]
        along = (err @ axis) * axis
        force = r.get("force_base")
        if force is not None and -(force @ -axis) > CONTACT:  # pressing on the head (force against tool z)
            across = COMPLY * (force - (force @ axis) * axis)
        else:
            across = BIAS_GAIN * (err - along)
        self.bias = np.clip(self.bias + across + BIAS_GAIN * (r["depth"] < -0.0005) * along, -BIAS_LIMIT, BIAS_LIMIT)
        return goal + self.bias, self.quat

    def drive(self, r: dict) -> float:
        """Wrist drive torque, tightening positive: read (privileged), or from the sensor, and above its range
        extrapolated along the line its in-range readings make against the angle turned."""
        if r.get("drive") is not None:
            return r["drive"]
        sensed = -r["torque_z"]  # the bolt's resistance reads as negative torque about tool z
        x, y, z, w = self.previous
        step = _qmul(np.array([-x, -y, -z, w]), r["tool_quat"])  # last tick's measured turn about tool z
        self.measured += 2 * math.atan2(step[2], step[3])
        self.previous = np.asarray(r["tool_quat"], float)
        if 2.0 < sensed < 9.5:
            self.samples.append((self.measured, sensed))
        if sensed >= 9.5 and len(self.samples) >= 10:
            turned, torque = np.array(self.samples).T
            slope, offset = np.polyfit(turned, torque, 1)
            return max(sensed, offset + slope * self.measured)
        if sensed >= 9.5:
            return math.nan  # saturated with no line to extrapolate: the caller must stop, not turn blind
        return sensed

    def _installed(self, r: dict) -> str:
        return f"; installed torque {r['installed']:.2f} N·m" if r.get("installed") is not None else ""

    def step(self, r: dict) -> tuple[np.ndarray, np.ndarray] | str:
        self.ticks += 1
        elapsed = self.ticks * self.dt
        head, axis, depth, drive = r["head"], r["axis"], r["depth"], self.drive(r)
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
            if math.isnan(drive):
                return ("stopped: the torque sensor reached its 10 N·m limit before enough readings to estimate "
                        "higher torque; the bolt is at about 10 N·m or a little more")
            if drive >= target:
                return (f"stopped at drive torque {drive:.2f} N·m after turning {math.degrees(self.turned):.0f} "
                        f"degrees{self._installed(r)}")
            if r.get("drive") is not None and not r["engaged"] and depth < 0.002:  # privileged readings only
                return f"the socket came off the head after turning {math.degrees(self.turned):.0f} degrees"
            if elapsed > self.limit:
                return f"stopped by the time limit at drive torque {drive:.2f} N·m"
            slow_from = 0.5 * target if r.get("drive") is not None else 2.0  # sample the sensor's range slowly
            rate = FINAL_RATE if drive > slow_from else TURN_RATE
            self.quat, self.turned = _spin(self.quat, rate * self.dt), self.turned + rate * self.dt
            return self._target(r, head - PRESS_TURN * axis)
        if self.name == "unload":
            self.quiet = self.quiet + 1 if abs(drive) < (0.1 if r.get("drive") is not None else 0.15) else 0
            needed = 1 if r.get("drive") is not None else 8  # the sensor's noise is about 0.07 N·m
            if self.quiet >= needed + (0 if r.get("drive") is not None else 2):
                return f"unloaded: drive torque {drive:.2f} N·m{self._installed(r)}"
            if self.quiet >= needed:  # without privilege, about 1 degree more into the socket's play on the flats
                self.quat = _spin(self.quat, -0.3 * self.dt)
                return self._target(r, head - PRESS_TURN * axis)
            if elapsed > self.limit:
                return f"still loaded after {elapsed:.1f} s: drive torque {drive:.2f} N·m"
            self.quat = _spin(self.quat, -math.copysign(0.3, drive) * self.dt)
            return self._target(r, head - PRESS_TURN * axis)
        out = float(self.args["mm"]) / 1000  # retract
        if -depth >= out - 0.002:
            return f"retracted: the socket face is {-1e3 * depth:.0f} mm from the head top"
        if elapsed > self.limit:
            where = (f"the socket is still on the head, the head top {1e3 * depth:.1f} mm inside it" if depth > 0
                     else f"the socket face is {-1e3 * depth:.0f} mm from the head top")
            return f"stopped by the time limit: {where}"
        return self._target(r, head + out * axis)
