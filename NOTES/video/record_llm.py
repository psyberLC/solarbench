"""Record one episode of a model driving a task, path-traced, for a demo video with the model's output beside it.

The task runs with the site scenery and the daylight rig through the Newton OVRTX viewer (--viz newton_rtx), one
environment, the dev split's episode 0. The policy is the same as in the comparison runs (evaluate.py's loop),
so the model's choices are its own; the simulation waits while it thinks. Every step's path-traced frame is saved,
with the state the overlay shows; every model call is saved with the step it was made at, its wall time, the text
it was given and its thinking and tool call (from the adapter's call log). The camera cuts between fixed shots at
the model's decisions, so each cut follows a choice the model made. Frames rendered without stepping the physics
(the robot held still: an establishing shot before the first call, and a short look in the new shot after each
call, while the simulation waits) are marked as such.
  SOLARBENCH_ENDPOINT_URL=... SOLARBENCH_ENDPOINT_KEY=... .venv/bin/python NOTES/video/record_llm.py \
      --task SolarBench-T3-ClampTighten-UR16e-R2-v0 --policy endpoint:... --out NOTES/video/raw/t3 --viz newton_rtx
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from isaaclab.app import add_launcher_args, launch_simulation

parser = argparse.ArgumentParser()
parser.add_argument("--task", required=True)
parser.add_argument("--policy", required=True)
parser.add_argument("--out", required=True)
add_launcher_args(parser)
args, hydra = parser.parse_known_args()
sys.argv = [sys.argv[0], *hydra]

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from isaaclab.utils.math import subtract_frame_transforms  # noqa: E402
from isaaclab_tasks.utils import resolve_task_config  # noqa: E402
from PIL import Image  # noqa: E402

import solarbench.tasks  # noqa: E402, F401
from solarbench import wire  # noqa: E402
from solarbench.agents import make_policy  # noqa: E402
from solarbench.eval.splits import SPLITS  # noqa: E402
from solarbench.render import daylight  # noqa: E402

T3 = args.task.startswith("SolarBench-T3")
# (eye, lookat) in the world frame; the camera pushes in slowly while a shot lasts
SHOTS = {
    "t3": {"wide": ((3.9, -1.6, 1.7), (1.9, 0.45, 0.75)), "medium": ((2.45, -0.55, 1.35), (1.73, 0.47, 0.80)),
           "close": ((1.98, -0.12, 0.98), (1.73, 0.45, 0.83))},
    "t2": {"wide": ((-1.1, 2.6, 1.1), (-0.05, 2.0, 1.05)), "close": ((-0.5, 2.0, 0.95), (-0.12, 1.94, 1.08)),
           "pull": ((-0.6, 1.55, 1.05), (-0.1, 1.95, 1.07))},
}["t3" if T3 else "t2"]
PUSH_IN = 0.012  # fraction of the eye's distance per second, up to 15 %
PREROLL, PAUSE = 75, 36  # frames rendered without stepping: before the first call, and after each call in its shot

out = Path(args.out)
(out / "frames").mkdir(parents=True, exist_ok=True)
os.environ["SOLARBENCH_ENDPOINT_LOG"] = str(out / "calls.jsonl")
if (out / "calls.jsonl").exists():
    (out / "calls.jsonl").unlink()
split = SPLITS["dev"]
env_cfg, _ = resolve_task_config(args.task, "")
env_cfg.scene.num_envs = 1
env_cfg.seed = split.base_seed
env_cfg.enable_scenery()
daylight.install()
first = "wide"
env_cfg.sim.default_visualizer_cfg.eye, env_cfg.sim.default_visualizer_cfg.lookat = SHOTS[first]
args.device = env_cfg.sim.device
torch.manual_seed(split.base_seed)

with launch_simulation(env_cfg, args):
    env = gym.make(args.task, cfg=env_cfg)
    u = env.unwrapped
    obs, _ = env.reset()
    policy, layout = make_policy(args.policy, u.catalogue, u)
    selected = [name for name, _, _ in layout.blocks]
    if hasattr(u, "select"):
        u.select(selected)
    policy.reset(torch.arange(u.num_envs, device=u.device), list(u.prompts))
    work_order = u.prompts[0]
    if wire.TOOL_DELTA in u.catalogue["opcodes"]:
        hold = torch.zeros(u.num_envs, u.cfg.action_space, device=u.device)
    else:
        hold = torch.zeros(u.num_envs, layout.depth, 16, dtype=torch.int32, device=u.device)
    viz = u.sim.visualizers[0]
    shot = {"name": first, "since": 0}
    step, steps, events, frames = 0, [], [], []
    clock = {"frame": 0}  # camera time in frames, rendered with or without a physics step

    def head_b() -> np.ndarray:
        head_w, _ = u.head_top_w()
        p, _ = subtract_frame_transforms(u.robot.data.root_pos_w.torch, u.robot.data.root_quat_w.torch, head_w)
        return p[0].cpu().numpy()

    def next_shot(result) -> str:
        if result is None:
            return shot["name"]
        if T3:
            if result[0] == "skill":
                return "medium" if result[1] == "retract" else "close"
            far = np.linalg.norm(np.asarray(result[1][:3]) - head_b()) > 0.02
            return "wide" if far else "medium"
        return {"grasp": "close", "unplug": "pull", "plug_in": "close", "release": "wide"}.get(result, shot["name"])

    asked = policy._ask

    def ask(*a, **k):
        started = time.perf_counter()
        result = asked(*a, **k)
        said = [m for m in policy._messages[0] if m.get("role") == "assistant"]  # the model's own tool call
        call = ((said[-1].get("tool_calls") or [{}])[0].get("function") or {}) if said else {}
        events.append({"step": step, "wall_s": time.perf_counter() - started, "given": a[1],
                       "tool": {"name": call.get("name"), "arguments": call.get("arguments")},
                       "result": result if result is None or isinstance(result, str) else list(result)})
        name = next_shot(result)
        if name != shot["name"]:
            shot.update(name=name, since=clock["frame"])
        return result

    policy._ask = ask

    def camera() -> None:
        eye, look = (np.asarray(v, float) for v in SHOTS[shot["name"]])
        k = min(PUSH_IN * (clock["frame"] - shot["since"]) * u.step_dt, 0.15)
        u.sim.set_camera_view(tuple(look + (eye - look) * (1 - k)), tuple(look))

    def state() -> dict:
        s = {"t": round(float(u.episode_length_buf[0]) * u.step_dt, 4), "shot": shot["name"],
             "stages": [bool(x >= 0) for x in u.stage_time[0].tolist()]}
        if T3:
            s.update({"depth_mm": 1e3 * float(u.depth[0]), "engaged": bool(u.engaged[0]),
                      "theta_deg": float(torch.rad2deg(u.theta[0] - u.theta0[0])),
                      "tau_meas_Nm": float(u.tau[0]), "tau_inst_Nm": float(u.bp.tau_req(u.theta)[0]),
                      "preload_kN": 1e-3 * float(u.bp.preload(u.theta)[0])})
        else:
            s.update({"depth_mm": 1e3 * float(u.depth[0]),
                      "push_N": float((-(u.f_hand_w[0] * u.axis_w[0]).sum()).clamp(min=0)),
                      "latched": bool(u.latch.latched[0]), "open": bool(u.latch.open[0]),
                      "grasped": bool(u.grasped[0])})
        return s

    def save(kind: str) -> None:
        Image.fromarray(viz.render_rgb_array()).save(out / "frames" / f"{len(frames):05d}.jpg", quality=95)
        frames.append({"kind": kind, "step": step, "calls": len(events), "shot": shot["name"]})
        clock["frame"] += 1

    def still(count: int, kind: str) -> None:  # the scene as it is, the camera moving, no physics step
        for _ in range(count):
            camera()
            u.sim.render()
            save(kind)

    still(PREROLL, "preroll")
    while True:
        with torch.inference_mode():
            before = len(events)
            action = policy.act({name: obs[name] for name in selected})
            if len(events) > before:
                still(PAUSE, "decision")
            camera()
            obs, _, term, trunc, _ = env.step(hold if action is None else action)
        if bool(term[0] | trunc[0]):
            break
        steps.append(state())
        save("step")
        step += 1
        if step % 30 == 0:
            print(f"step {step} t={steps[-1]['t']:.1f}s shot={shot['name']} calls={len(events)}", flush=True)
    record = u.completed_episodes[-1]
    print("episode", {k: record[k] for k in record if k.startswith("stage_") or k in ("safe_success", "damage")},
          flush=True)
    trace = {"task": args.task, "policy": args.policy, "work_order": work_order, "step_dt": u.step_dt,
             "steps": steps, "events": events, "frames": frames, "record": record}
    (out / "trace.json").write_text(json.dumps(trace, default=str))
    env.close()
