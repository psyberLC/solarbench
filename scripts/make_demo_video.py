"""Compose a task demo video: RTX shots + HUD overlay driven by the logged per-step simulation state.

Usage: .venv/bin/python scripts/make_demo_video.py [--task t2|t3]
       (expects results/media/raw/<task>_rtx_<shot>.{mp4,json} from run_oracle.py --video --log_steps)
"""

import argparse
import json
from pathlib import Path

import numpy as np
from moviepy.editor import VideoFileClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont

RAW = Path(__file__).resolve().parents[1] / "results" / "media" / "raw"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def t2_readout(s: dict) -> list[tuple[str, str]]:
    latch = "LATCHED" if s["latched"] else ("HELD OPEN" if s["open"] else "free")
    return [("insertion depth", f"{s['depth_mm']:6.1f} mm"), ("axial push", f"{s['push_N']:6.1f} N"), ("latch", latch)]


def t3_readout(s: dict) -> list[tuple[str, str]]:
    return [("drive torque", f"{s['tau_meas_Nm']:5.1f} N·m"), ("installed", f"{s['tau_inst_Nm']:5.1f} N·m"),
            ("bolt turned", f"{s['theta_deg']:+5.0f}°"), ("preload", f"{s['preload_kN']:5.1f} kN")]


TASKS = {
    "t2": {
        "title": "SolarBench · T2 MC4 disconnect / reconnect",
        "stages": ("grasped", "unlocked", "separated", "realigned", "relatched", "released"),
        "readout": t2_readout,
        "caption": ("Unitree G1 + Dex3 · URDF torque limits (arm 25 N·m, fingers 1.4 N·m) · Newton / MuJoCo-Warp "
                    "600 Hz · scripted oracle · OVRTX path-traced"),
        "shots": [
            ("wide", "Unitree G1 humanoid unplugs and re-mates a PV string connector under a fixed-tilt table",
             False, {"t_end": 3.0}),
            ("rear", None, True, {"t_end": 1.9}),
            ("grasp", None, True, {"t_start": 1.7, "speed": 0.6}),
        ],
    },
    "t3": {
        "title": "SolarBench · T3 clamp bolt tightening",
        "stages": ("engaged", "snug", "in_spec", "released"),
        "readout": t3_readout,
        "caption": ("Husky A300 + UR16e · wrist limit 54 N·m · M8 torque–angle model (spec 14–18 N·m) · "
                    "Newton / MuJoCo-Warp 600 Hz · scripted oracle · OVRTX"),
        "shots": [
            ("wide", "A mobile manipulator torques a module end clamp to the manufacturer's specification",
             False, {"t_end": 4.0}),
            ("close", None, True, {"t_start": 3.5}),
        ],
    },
}


def font(size, bold=False):
    try:
        return ImageFont.truetype(BOLD if bold else FONT, size)
    except OSError:
        return ImageFont.load_default()


def panel(draw, box, alpha=150):
    draw.rounded_rectangle(box, radius=14, fill=(12, 16, 22, alpha))


def overlay(frame: np.ndarray, task: dict, state: dict | None, title: str | None, hud: bool,
            speed: float = 1.0) -> np.ndarray:
    img = Image.fromarray(frame).convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    W, H = img.size
    if title:
        panel(d, (40, 36, 1120, 170))
        d.text((66, 52), task["title"], font=font(44, True), fill=(255, 255, 255, 255))
        d.text((68, 112), title, font=font(26), fill=(205, 214, 224, 255))
    if hud and state:
        rows = task["readout"](state)
        x0, y0 = W - 470, 40
        y_read = y0 + 110 + 40 * len(task["stages"]) + 10
        panel(d, (x0, y0, W - 40, y_read + 44 * len(rows) + 6))
        d.text((x0 + 24, y0 + 18), "phase", font=font(22), fill=(160, 172, 186, 255))
        d.text((x0 + 24, y0 + 44), state["phase"].replace("_", " "), font=font(38, True), fill=(255, 255, 255, 255))
        for i, (name, done) in enumerate(zip(task["stages"], state["stages"], strict=True)):
            y = y0 + 110 + i * 40
            col = (92, 214, 140, 255) if done else (120, 128, 138, 255)
            d.ellipse((x0 + 26, y + 6, x0 + 46, y + 26), fill=col if done else None, outline=col, width=3)
            d.text((x0 + 60, y), name.replace("_", " "), font=font(26),
                   fill=(235, 240, 245, 255) if done else (150, 158, 168, 255))
        for i, (label, val) in enumerate(rows):
            y = y_read + 44 * i
            d.text((x0 + 24, y), label, font=font(22), fill=(160, 172, 186, 255))
            d.text((x0 + 250, y - 2), val, font=font(26, True), fill=(255, 255, 255, 255))
    if speed != 1.0:
        panel(d, (40, 36, 230, 96))
        d.text((62, 46), f"{speed:.1f}x speed", font=font(30, True), fill=(255, 214, 102, 255))
    panel(d, (40, H - 78, W - 40, H - 30), alpha=130)
    d.text((62, H - 70), task["caption"], font=font(22), fill=(225, 230, 236, 255))
    return np.asarray(Image.alpha_composite(img, layer).convert("RGB"))


def shot(key: str, task: dict, name: str, title: str | None, hud: bool, t_end: float | None = None,
         t_start: float = 0.0, speed: float = 1.0):
    clip = VideoFileClip(str(RAW / f"{key}_rtx_{name}.mp4"))
    trace = json.loads((RAW / f"{key}_rtx_{name}.json").read_text())
    dt = trace[1]["t"] - trace[0]["t"] if len(trace) > 1 else 1 / 30
    last = next((i for i, s in enumerate(trace) if all(s["stages"])), len(trace) - 1)
    end = min(clip.duration, t_end or (last * dt + 0.8))
    clip = clip.subclip(t_start, end)

    def fx(get_frame, t):
        k = min(int(round((t + t_start) / dt)), len(trace) - 1)
        return overlay(get_frame(t), task, trace[k], title, hud, speed)

    clip = clip.fl(fx)
    return clip.speedx(speed) if speed != 1.0 else clip


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="t2", choices=sorted(TASKS))
    key = parser.parse_args().task
    task = TASKS[key]
    out = RAW.parent / f"solarbench_{key}_demo.mp4"
    video = concatenate_videoclips([shot(key, task, name, title, hud, **kw) for name, title, hud, kw in task["shots"]])
    video.write_videofile(str(out), fps=30, codec="libx264", audio=False, preset="medium", bitrate="8M", logger=None)
    print(out, f"{video.duration:.1f}s")
