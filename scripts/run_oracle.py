"""Run a task's scripted oracle and print per-stage outcomes.

Usage: .venv/bin/python scripts/run_oracle.py --num_envs 4 --episodes 8 [--phi 0] [--viz none]
"""

import argparse
import json
import sys

from isaaclab.app import add_launcher_args, launch_simulation
from isaaclab_rl.entrypoints.common import add_video_args, apply_video_recording

parser = argparse.ArgumentParser()
parser.add_argument("--task", default="SolarBench-T2-MC4-G1-v0")
parser.add_argument("--num_envs", type=int, default=4)
parser.add_argument("--episodes", type=int, default=8)
parser.add_argument("--phi", type=float, default=0.0, help="grasp roll about the connector axis [deg]")
parser.add_argument("--approach", default="palm", choices=["palm", "below", "above"])
parser.add_argument("--debug_every", type=int, default=0, help="print phase/state every N steps")
parser.add_argument("--debug_env", type=int, default=0, help="environment index printed by --debug_every (T3)")
parser.add_argument("--out", default=None, help="write per-episode records (JSON lines)")
parser.add_argument("--seed", type=int, default=0)
parser.add_argument("--log_steps", default=None, help="write per-step state of env 0 (JSON) for video overlays")
parser.add_argument("--scenery", action="store_true", help="add visual-only site context (demo renders)")
parser.add_argument("--eye", type=float, nargs=3, default=None, help="viewer camera position (env frame)")
parser.add_argument("--lookat", type=float, nargs=3, default=None, help="viewer camera target (env frame)")
add_launcher_args(parser)
add_video_args(parser, action="oracle playback")
args, hydra_overrides = parser.parse_known_args()  # e.g. physics=ovphysx for the cross-backend check
sys.argv = [sys.argv[0], *hydra_overrides]

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402
from isaaclab_tasks.utils import resolve_task_config  # noqa: E402

import solarbench.tasks  # noqa: E402, F401
from solarbench.oracle import make_oracle  # noqa: E402

torch.manual_seed(args.seed)
env_cfg, _ = resolve_task_config(args.task, "")
env_cfg.scene.num_envs = args.num_envs
env_cfg.seed = args.seed
if args.scenery:
    env_cfg.enable_scenery()
    from solarbench.render import daylight

    daylight.install()
if args.eye is not None:
    env_cfg.sim.default_visualizer_cfg.eye = tuple(args.eye)
if args.lookat is not None:
    env_cfg.sim.default_visualizer_cfg.lookat = tuple(args.lookat)
args.device = env_cfg.sim.device
apply_video_recording(env_cfg, "logs/oracle", args, subdir=args.task.split("-")[1].lower())
with launch_simulation(env_cfg, args):
    env = gym.make(args.task, cfg=env_cfg)
    u = env.unwrapped
    env.reset()
    kw = dict(phi_deg=args.phi, approach_dir=args.approach) if args.task.startswith("SolarBench-T2") else {}
    oracle = make_oracle(args.task, u, **kw)
    PHASES = __import__(type(oracle).__module__, fromlist=["PHASES"]).PHASES
    T3 = args.task.startswith("SolarBench-T3")

    def trace_state(u, oracle, step) -> dict:
        """Per-step state of env 0 for the demo HUD."""
        s = {"t": step * u.step_dt, "phase": PHASES[int(oracle.phase[0])],
             "stages": [bool(x >= 0) for x in u.stage_time[0].tolist()]}
        if T3:
            s.update({"depth_mm": 1e3 * float(u.depth[0]), "engaged": bool(u.engaged[0]),
                      "theta_deg": float(torch.rad2deg(u.theta[0] - u.theta0[0])),
                      "tau_meas_Nm": float(u.tau[0]), "tau_inst_Nm": float(u.bp.tau_req(u.theta)[0]),
                      "preload_kN": 1e-3 * float(u.bp.preload(u.theta)[0])})
        else:
            s.update({"depth_mm": 1e3 * float(u.depth[0]),
                      "push_N": float((-(u.f_hand_w[0] * u.axis_w[0]).sum()).clamp(min=0)),
                      "grip_N": float(sum(u.sensors[k].data.force_matrix_w.torch[0].sum(dim=(0, 1)).norm()
                                          for k in ("thumb", "fingers", "palm"))),
                      "latched": bool(u.latch.latched[0]), "open": bool(u.latch.open[0]),
                      "grasped": bool(u.grasped[0])})
        return s

    step = 0
    trace = []
    while len(u.completed_episodes) < args.episodes:
        with torch.inference_mode():
            a = oracle.act()
            if args.log_steps:
                trace.append(trace_state(u, oracle, step))
            if T3:
                was_over = u.over_torque.clone()
            _, _, term, trunc, _ = env.step(a)
            if T3 and args.debug_every:  # report the oracle state at the step an over-torque first happens
                for i in (u.over_torque & ~was_over).nonzero().flatten().tolist():
                    print(f"OVER env {i} step {step} phase={PHASES[int(oracle.phase[i])]} tau={float(u.tau[i]):.2f} "
                          f"inst={float(u.bp.tau_req(u.theta)[i]):.2f} k={float(u.bp.stiffness[i]):.1f} "
                          f"timer={float(oracle.timer[i]):.2f}")
            done = (term | trunc).nonzero(as_tuple=False).squeeze(-1)
            if len(done):
                oracle.reset(done)
        step += 1
        if args.debug_every and step % args.debug_every == 0 and T3:
            i = args.debug_env
            w3 = float(u.robot.data.joint_pos.torch[i, u.arm_ids[5]])
            print(f"step {step:4d} phase={PHASES[int(oracle.phase[i])]:8s} depth={1e3 * float(u.depth[i]):7.2f}mm "
                  f"lat={1e3 * float(u.lateral[i]):6.2f}mm tilt={float(u.axis_err_deg[i]):5.2f}deg "
                  f"engaged={bool(u.engaged[i])} theta={float(u.theta[i]):6.3f}rad tau_meas={float(u.tau[i]):6.2f}Nm "
                  f"tau_inst={float(u.bp.tau_req(u.theta)[i]):6.2f}Nm w3_lag={float(u.arm_q_des[i, 5]) - w3:+.3f} "
                  f"w3_q={w3:+.2f} spin={float(oracle.spin[i]):+.2f}")
        elif args.debug_every and step % args.debug_every == 0:
            from isaaclab.utils.math import quat_apply_inverse

            g, gq = u.grasp_pose_b()
            rp, rq = u.robot.data.root_pos_w.torch, u.robot.data.root_quat_w.torch
            fs, _ = u.female_site_w()
            err_palm = quat_apply_inverse(gq, quat_apply_inverse(rq, fs - rp) - g)[0] * 1e3
            ft = u.sensors["thumb"].data.force_matrix_w.torch[0].sum(dim=(0, 1)).norm()
            ff = u.sensors["fingers"].data.force_matrix_w.torch[0].sum(dim=(0, 1)).norm()
            fp = u.sensors["palm"].data.force_matrix_w.torch[0].sum(dim=(0, 1)).norm()
            print(
                f"      site-grasp err in palm frame (mm) = {[round(x, 1) for x in err_palm.tolist()]}  "
                f"F thumb/fingers/palm = {float(ft):5.1f}/{float(ff):5.1f}/{float(fp):5.1f} N"
            )
            print(
                f"step {step:4d} phase={PHASES[int(oracle.phase[0])]:9s} depth={1e3 * float(u.depth[0]):6.2f}mm "
                f"lat={1e3 * float(u._lateral[0]):5.2f}mm hand_err={1e3 * float(u._hand_dist[0]):6.1f}mm "
                f"grasped={bool(u.grasped[0])} latched={bool(u.latch.latched[0])} open={bool(u.latch.open[0])} "
                f"F_hand={float(u.f_hand_w[0].norm()):5.1f}N score={float(u.grasp_score[0]):.2f} "
                f"unlock_t={float(u.latch.unlock_timer[0]):.3f} cmd={bool(u.unlock_cmd[0])}"
            )
    if args.log_steps:
        with open(args.log_steps, "w") as f:
            json.dump(trace, f)
    recs = u.completed_episodes[: args.episodes]
    keys = [k for k in recs[0] if k.startswith("stage_")] + ["success", "safe_success", "damage"]
    print("\n== oracle summary over", len(recs), "episodes")
    for k in keys:
        print(f"  {k:22s} {sum(r[k] for r in recs)}/{len(recs)}")
    for k in ("peak_push_force_N", "peak_hand_force_N", "peak_cable_tension_N", "installed_torque_Nm",
              "peak_installed_torque_Nm", "preload_N", "duration_s"):
        if k not in recs[0]:
            continue
        vals = [r[k] for r in recs]
        print(f"  {k:22s} mean={sum(vals) / len(vals):7.2f} max={max(vals):7.2f}")
    if args.out:
        with open(args.out, "w") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")
    env.close()
