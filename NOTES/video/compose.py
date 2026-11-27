"""Compose a recorded episode (NOTES/video/record_llm.py) into one video: the path-traced viewer, the model's
terminal beside it, and the task's telemetry below.

Time is shown as it was: the simulation stands still while the model thinks (the frame holds and says so, with the
call's real wall time), long stretches of a skill run faster and say by how much, and everything the terminal
shows is the model's own thinking and tool calls from the call log, abridged only where marked.
  .venv/bin/python NOTES/video/compose.py NOTES/video/raw/t3 NOTES/video/solarbench_t3_llm.mp4
The frames stay out of git (raw/); each take's trace.json is kept as NOTES/video/<task>_trace.json. The README's
GIFs are the videos at 3x (bolt) and 2x (connector), 640 px wide, 10 fps, through ffmpeg's palettegen/paletteuse.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FPS = 30
W, H = 1920, 1080
VIEW = (24, 24, 1344, 756)
HUD = (24, 796, 1344, 260)
TERM = (1392, 24, 504, 1032)
BG, PANEL, EDGE = (9, 12, 17), (17, 21, 28), (38, 45, 56)
TEXT, DIM, FAINT = (230, 235, 241), (150, 160, 172), (96, 106, 118)
GREEN, AMBER, BLUE, CYAN, RED = (96, 214, 140), (255, 196, 92), (120, 170, 255), (110, 220, 230), (255, 110, 100)
UI = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
UI_BOLD = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
SIGN = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"  # has the symbols Noto Sans lacks
SIGN_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
MONO_IT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Oblique.ttf"
_fonts: dict = {}


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    if (path, size) not in _fonts:
        _fonts[path, size] = ImageFont.truetype(path, size)
    return _fonts[path, size]


TASKS = {
    "T3": {
        "title": "SolarBench · T3 clamp bolt",
        "subtitle": "Nemotron 3.5 Super drives a UR16e to torque a module clamp to spec",
        "stages": ("engaged", "snug", "in_spec", "released"),
        "command": ["$ solarbench run --task T3-ClampTighten-UR16e-R2",
                    "    --policy endpoint:nemotron-3.5-super-vl",
                    "    tools=on skills=on wrench=on (no privileged state)"],
        "caption": ("Nemotron 3.5 Super 120B-A12B (vLLM, RTU HPC) chooses closed-loop skills · unprivileged: work "
                    "order, tool pose, wrist F/T · Newton 600 Hz · OVRTX path-traced · dev episode 0, exploratory"),
    },
    "T2": {
        "title": "SolarBench · T2 MC4 connector",
        "subtitle": "Nemotron 3.5 Super directs a Unitree G1 to unplug and re-mate a PV connector",
        "stages": ("grasped", "unlocked", "separated", "realigned", "relatched", "released"),
        "command": ["$ solarbench run --task T2-MC4-G1",
                    "    --policy phases:nemotron-3.5-super-vl",
                    "    (phase skills: the oracle's controller, in the",
                    "     order the model chooses; privileged state)"],
        "caption": ("Nemotron 3.5 Super 120B-A12B (vLLM, RTU HPC) orders phase skills that run the scripted "
                    "controller · the task offers only privileged state · Newton 600 Hz · OVRTX path-traced · "
                    "dev episode 0, exploratory"),
    },
}


# ---------------------------------------------------------------------------------------------------- the story
def fmt_args(arguments) -> str:
    if not arguments:
        return ""
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except ValueError:
            return arguments

    def val(v):
        if isinstance(v, list):
            return "[" + ", ".join(f"{x:.3f}" if isinstance(x, float) else str(x) for x in v) + "]"
        return f"{v:g}" if isinstance(v, float) else str(v)

    return ", ".join(f"{k}={val(v)}" for k, v in arguments.items())


def call_text(event: dict) -> str:
    tool = event.get("tool") or {}
    name = tool.get("name") or (event["result"] if isinstance(event["result"], str) else None)
    if name is None and event["result"] and event["result"][0] == "skill":
        return f"{event['result'][1]}({fmt_args(event['result'][2])})"
    return f"{name or '?'}({fmt_args(tool.get('arguments'))})"


def result_text(given: str) -> list[str]:
    """What a call's result told the model: a line, and for the connector the state lines that matter."""
    lines = [line.strip() for line in given.splitlines() if line.strip()]
    for line in lines:
        if " finished" in line or " ended" in line or " stopped" in line:
            name, _, rest = line.partition(" finished")
            if rest.lstrip(": "):
                return [f"{name}: {rest.lstrip(': ')}"]
            return [line, " · ".join(x for x in lines if x.startswith(("latch:", "hand holds")))]
        if line.startswith("your last command"):
            return [line.replace("your last command ", "pose ")]
    return lines[:1] or [""]


# ---------------------------------------------------------------------------------------------------- drawing
def panel(d: ImageDraw.ImageDraw, box, fill=PANEL, radius=14, outline=EDGE):
    x, y, w, h = box
    d.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill=fill, outline=outline, width=1)


def chip(d, xy, text, color, size=20, bg=(0, 0, 0, 160)):
    f = font(SIGN, size)
    x, y = xy
    tw = d.textlength(text, font=f)
    d.rounded_rectangle((x, y, x + tw + 28, y + size + 18), radius=(size + 18) // 2, fill=bg)
    d.text((x + 14, y + 7), text, font=f, fill=color)
    return tw + 28


def bar(d, x, y, w, value, lo, hi, color, window=None, ticks=()):
    d.rounded_rectangle((x, y, x + w, y + 12), radius=6, fill=(32, 38, 48))
    if window:
        a, b = ((v - lo) / (hi - lo) * w for v in window)
        d.rectangle((x + a, y - 3, x + b, y + 15), fill=(40, 92, 62))
    frac = min(max((value - lo) / (hi - lo), 0.0), 1.0)
    if frac > 0:
        d.rounded_rectangle((x, y, x + max(frac * w, 12), y + 12), radius=6, fill=color)
    for t, label in ticks:
        tx = x + (t - lo) / (hi - lo) * w
        d.line((tx, y + 16, tx, y + 22), fill=FAINT, width=1)
        d.text((tx, y + 24), label, font=font(SIGN_REG, 12), fill=FAINT, anchor="mt")


def hud(d, task_key: str, task: dict, s: dict, stage_times: list[float | None]):
    x, y, w, h = HUD
    panel(d, HUD)
    # stages: a horizontal stepper with the time each was reached
    n = len(task["stages"])
    sx, sw = x + 64, 530
    gap = sw / (n - 1)
    d.text((x + 24, y + 18), "STAGES", font=font(UI_BOLD, 14), fill=FAINT)
    cy = y + 82
    for i in range(n - 1):
        done = s["stages"][i + 1]
        d.line((sx + i * gap, cy, sx + (i + 1) * gap, cy), fill=GREEN if done else (52, 60, 72), width=3)
    for i, name in enumerate(task["stages"]):
        cx, done = sx + i * gap, s["stages"][i]
        if done:
            d.ellipse((cx - 11, cy - 11, cx + 11, cy + 11), fill=GREEN)
            d.line((cx - 5, cy, cx - 1, cy + 4, cx + 6, cy - 5), fill=(10, 30, 18), width=3)
        else:
            d.ellipse((cx - 11, cy - 11, cx + 11, cy + 11), fill=PANEL, outline=(80, 90, 104), width=3)
        d.text((cx, cy + 22), name.replace("_", " "), font=font(UI_BOLD if done else UI, 16),
               fill=TEXT if done else DIM, anchor="ma")
        if stage_times[i] is not None:
            d.text((cx, cy + 52), f"{stage_times[i]:.1f} s", font=font(UI, 14), fill=GREEN, anchor="mt")
    # readings
    rx = x + 660
    d.line((rx - 30, y + 20, rx - 30, y + h - 62), fill=EDGE, width=1)
    d.text((rx, y + 18), "TELEMETRY", font=font(UI_BOLD, 14), fill=FAINT)
    d.text((x + w - 24, y + 14), f"sim t = {s['t']:5.2f} s", font=font(MONO_BOLD, 20), fill=TEXT, anchor="ra")
    label, value = font(UI, 16), font(MONO_BOLD, 19)
    if task_key == "T3":
        rows = [("wrist drive torque", f"{s['tau_meas_Nm'] + 0.0:5.1f} N·m".replace("-0.0", " 0.0"),
                 s["tau_meas_Nm"], (0, 20), BLUE, None),
                ("installed torque", f"{s['tau_inst_Nm']:5.1f} N·m", s["tau_inst_Nm"], (0, 20),
                 GREEN if 14 <= s["tau_inst_Nm"] <= 18 else AMBER, (14, 18))]
        for i, (name, text, v, (lo, hi), col, win) in enumerate(rows):
            yy = y + 50 + i * 62
            d.text((rx, yy), name, font=label, fill=DIM)
            d.text((rx + 400, yy - 2), text, font=value, fill=TEXT, anchor="ra")
            bar(d, rx, yy + 28, 400, v, lo, hi, col, win,
                ticks=[(0, "0"), (14, "14"), (18, "18"), (20, "20 N·m")] if win else ())
        kx = rx + 440
        for i, (name, text) in enumerate([("bolt turned", f"{s['theta_deg']:+5.0f}°"),
                                          ("clamp preload", f"{s['preload_kN']:4.1f} kN"),
                                          ("socket depth", f"{s['depth_mm']:5.1f} mm")]):
            yy = y + 50 + i * 42
            d.text((kx, yy), name, font=label, fill=DIM)
            d.text((x + w - 24, yy - 2), text, font=value, fill=TEXT, anchor="ra")
    else:
        latch = "LATCHED" if s["latched"] else ("HELD OPEN" if s["open"] else "free")
        d.text((rx, y + 50), "insertion depth", font=label, fill=DIM)
        d.text((rx + 400, y + 48), f"{s['depth_mm']:6.1f} mm", font=value, fill=TEXT, anchor="ra")
        bar(d, rx, y + 78, 400, s["depth_mm"], -45, 20, GREEN if s["depth_mm"] > 0 else BLUE,
            ticks=[(-40, "−40"), (0, "mouth"), (15, "seated")])
        kx = rx + 440
        for i, (name, text, col) in enumerate([
                ("latch", latch, GREEN if s["latched"] else AMBER if s["open"] else DIM),
                ("hand", "holding" if s["grasped"] else "open", TEXT),
                ("axial push", f"{s['push_N']:5.1f} N", TEXT)]):
            yy = y + 50 + i * 42
            d.text((kx, yy), name, font=label, fill=DIM)
            d.text((x + w - 24, yy - 2), text, font=font(MONO_BOLD, 18), fill=col, anchor="ra")
    # caption
    cap = textwrap.wrap(task["caption"], 140, break_on_hyphens=False)
    for i, line in enumerate(cap[:2]):
        d.text((x + 24, y + h - 50 + i * 20), line, font=font(UI, 14), fill=FAINT)


class Terminal:
    """The model's side of the run, as lines of (text, font, colour); the newest lines stay in view."""

    COLS = 50

    def __init__(self):
        self.lines: list[tuple[str, str, tuple]] = []

    def add(self, text: str, face=MONO, color=TEXT, indent=""):
        for para in text.splitlines() or [""]:
            wrapped = textwrap.wrap(para, self.COLS - len(indent), break_long_words=True,
                                    break_on_hyphens=False) or [""]
            self.lines += [(indent + w, face, color) for w in wrapped]

    def draw(self, d, extra: list[tuple[str, str, tuple]] = (), cursor: bool = False, title: str = ""):
        x, y, w, h = TERM
        panel(d, TERM, fill=(13, 16, 22))
        d.rounded_rectangle((x, y, x + w, y + 40), radius=14, fill=(24, 29, 38))
        d.rectangle((x, y + 26, x + w, y + 40), fill=(24, 29, 38))
        for i, col in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
            d.ellipse((x + 16 + i * 20, y + 14, x + 28 + i * 20, y + 26), fill=col)
        d.text((x + w / 2 + 30, y + 20), title, font=font(UI, 15), fill=DIM, anchor="mm")
        lines = self.lines + list(extra)
        lh, top = 21, y + 54
        rows = (h - 70) // lh
        view = lines[-rows:]
        for i, (text, face, color) in enumerate(view):
            d.text((x + 16, top + i * lh), text, font=font(face, 15), fill=color)
        if cursor:
            cy = top + (len(view) - 1) * lh if view else top
            last = view[-1][0] if view else ""
            cx = x + 16 + d.textlength(last, font=font(MONO, 15)) + 4
            d.rectangle((cx, cy + 2, cx + 9, cy + 18), fill=TEXT)


# ---------------------------------------------------------------------------------------------------- timeline
def main(raw: Path, out: Path):
    trace = json.loads((raw / "trace.json").read_text())
    calls = [json.loads(line) for line in (raw / "calls.jsonl").read_text().splitlines() if line.strip()]
    key = "T3" if trace["task"].startswith("SolarBench-T3") else "T2"
    task = TASKS[key]
    events, frames, steps = trace["events"], trace["frames"], trace["steps"]
    assert len(calls) == len(events), "one call log line per model call"
    stage_times: list[float | None] = [None] * len(task["stages"])

    term = Terminal()
    title = "nemotron-3.5-super-vl  ·  RTU HPC (vLLM)"
    for line in task["command"]:
        term.add(line, MONO_BOLD if line.startswith("$") else MONO, CYAN if line.startswith("$") else DIM)
    term.add("")
    wo = [p for p in trace["work_order"].split("\n\n") if p.strip()]
    job = Path(__file__).parents[1] / "probes" / "job_mc4.md"
    intro = " ".join(wo[1:3]) if key == "T3" else job.read_text().split("\n")[1]
    term.add("work order (abridged):" if key == "T3" else "job description (no work order yet; abridged):",
             MONO_BOLD, DIM)
    term.add(textwrap.shorten(intro.replace("# ", ""), 300, placeholder=" …"), MONO, FAINT, "  ")

    writer = imageio.get_writer(str(out), fps=FPS, codec="libx264", quality=None, bitrate="12M",
                                macro_block_size=8, ffmpeg_params=["-preset", "slow", "-pix_fmt", "yuv420p"])
    cache: dict[int, Image.Image] = {}

    def view_img(index: int) -> Image.Image:
        if index not in cache:
            cache.clear()
            cache[index] = Image.open(raw / "frames" / f"{index:05d}.jpg").convert("RGB").resize(
                (VIEW[2], VIEW[3]), Image.LANCZOS)
        return cache[index]

    def state_at(frame: dict) -> dict:
        return steps[min(max(frame["step"] - (frame["kind"] != "step"), 0), len(steps) - 1)]

    def emit(index: int, badge: tuple[str, tuple], extra=(), cursor=False, card=None):
        frame = frames[index]
        s = state_at(frame)
        if frame["kind"] != "step" and frame["step"] == 0:
            s = {**s, "t": 0.0, "stages": [False] * len(task["stages"])}
        for i, done in enumerate(s["stages"]):
            if done and stage_times[i] is None:
                stage_times[i] = float(trace["record"][f"t_{task['stages'][i]}"])
        canvas = Image.new("RGB", (W, H), BG)
        canvas.paste(view_img(index), VIEW[:2])
        d = ImageDraw.Draw(canvas, "RGBA")
        x, y, w, h = VIEW
        d.rounded_rectangle((x - 1, y - 1, x + w + 1, y + h + 1), radius=6, outline=EDGE, width=2)
        d.rounded_rectangle((x + 20, y + 18, x + 760, y + 104), radius=12, fill=(8, 11, 16, 170))
        d.text((x + 40, y + 28), task["title"], font=font(UI_BOLD, 30), fill=TEXT)
        d.text((x + 41, y + 70), task["subtitle"], font=font(UI, 18), fill=(200, 208, 218))
        bw = d.textlength(badge[0], font=font(SIGN, 20)) + 28
        chip(d, (x + w - 20 - bw, y + 22), badge[0], badge[1])
        if card:
            cw = d.textlength(card, font=font(SIGN, 26)) + 60
            d.rounded_rectangle((x + (w - cw) / 2, y + h - 110, x + (w + cw) / 2, y + h - 40), radius=16,
                                fill=(10, 40, 24, 215), outline=GREEN, width=2)
            d.text((x + w / 2, y + h - 75), card, font=font(SIGN, 26), fill=(220, 255, 230), anchor="mm")
        hud(d, key, task, s, stage_times)
        term.draw(d, extra, cursor, title)
        writer.append_data(np.asarray(canvas))

    total = 0
    i = 0
    # pre-roll: the scene before the first call returns; the work order goes in
    while i < len(frames) and frames[i]["kind"] == "preroll":
        emit(i, ("❚❚  SIM PAUSED · first call to the model", AMBER), cursor=(i // 15) % 2 == 0)
        i += 1
        total += 1
    for k, event in enumerate(events):
        call = calls[k]
        last = i - 1
        # the result of the previous call, then this call's thinking streamed while the frame holds
        if k:
            head, *more = result_text(event["given"])
            term.add("◀ " + head, MONO, AMBER)
            for line in more:
                term.add(line, MONO, (200, 170, 110), "  ")
        term.add("")
        term.add(f"── call {k + 1} · sim t = {steps[max(event['step'] - 1, 0)]['t'] if event['step'] else 0.0:.1f} s "
                 + "─" * 14, MONO_BOLD, BLUE)
        thought = (call.get("reasoning") or "").strip()
        tokens, wall = call.get("tokens_written") or 0, event["wall_s"]
        hold = min(max(1.0 + len(thought) / 2500, 1.4), 5.0)
        n = int(hold * FPS)
        words = thought.split()
        for f in range(n):
            shown = " ".join(words[: int(len(words) * min(1.0, (f + 1) / (0.8 * n)))])
            stream = Terminal()
            stream.add(shown, MONO_IT, (150, 160, 172), "  ")
            badge = (f"❚❚  SIM PAUSED · model thinking ({wall:.1f} s real)", AMBER)
            emit(last, badge, [("∴ thinking", MONO_BOLD, DIM)] + stream.lines[-14:], cursor=True)
            total += 1
        term.add(f"∴ thought for {wall:.1f} s · {tokens:,} tokens", MONO, FAINT)
        if call.get("reply") and not call["reply"].lstrip().startswith("{"):  # not the call echoed as text
            term.add(textwrap.shorten(call["reply"].strip().split("\n")[0], 160, placeholder=" …"), MONO, TEXT, "  ")
        term.add("▶ " + call_text(event), MONO_BOLD, GREEN)
        # the decision: the camera takes the shot for it while the robot is still held
        while i < len(frames) and frames[i]["kind"] == "decision" and frames[i]["calls"] == k + 1:
            emit(i, ("▶  executing the model's call", GREEN))
            i += 1
            total += 1
        # the skill runs: real time, or faster on a long stretch
        stretch = []
        while i < len(frames) and frames[i]["kind"] == "step" and (frames[i]["calls"] == k + 1):
            stretch.append(i)
            i += 1
        speed = 3 if len(stretch) > 180 else 2 if len(stretch) > 100 else 1
        badge = ("●  LIVE SIM  1×", GREEN) if speed == 1 else (f"●  SIM  {speed}× speed", AMBER)
        for j in stretch[::speed]:
            emit(j, badge)
            total += 1
    # the end: the episode's outcome, from its record
    rec = trace["record"]
    term.add("")
    if rec.get("safe_success") in (True, "True"):
        if key == "T3":
            card = (f"✓ Safe success · installed {float(rec['installed_torque_Nm']):.1f} N·m (spec 14–18) · "
                    f"released at {float(rec['t_released']):.1f} s · {len(events)} model calls")
        else:
            card = f"✓ Safe success · re-latched and released at {float(rec['t_released']):.1f} s · " \
                   f"{len(events)} model calls"
        term.add("✓ episode ended: safe success", MONO_BOLD, GREEN)
    else:
        card = "✗ Episode failed"
        term.add("✗ episode ended without safe success", MONO_BOLD, RED)
    for _ in range(int(3.0 * FPS)):
        emit(len(frames) - 1, ("■  EPISODE ENDED", TEXT), card=card)
        total += 1
    writer.close()
    print(out, f"{total / FPS:.1f} s, {total} frames")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
