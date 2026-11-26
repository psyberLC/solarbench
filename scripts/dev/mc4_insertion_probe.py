"""Physics probe: can Newton/MJWarp seat the MC4 nose in the sleeve at realistic clearances?

The female housing is driven by a compliant 6-DoF spring (a stand-in for a soft gripper) whose *target* is
laterally misaligned from the sleeve axis by ``offset`` (a miscalibrated gripper). Compliance and the nose
chamfer must recover the offset; beyond the capture range the nose lands on the sleeve rim and must jam.
Reports final depth, peak lateral error and whether
the nose jammed or tunnelled through the sleeve. No latch model here: contact geometry only.

Usage: .venv/bin/python scripts/dev/mc4_insertion_probe.py [--clearance 0.0003] [--dt 0.002]
"""

import argparse
import tempfile
from pathlib import Path

import newton
import numpy as np
import warp as wp

from solarbench.assets import build
from solarbench.specs import MC4

parser = argparse.ArgumentParser()
parser.add_argument("--clearance", type=float, nargs="+", default=[0.0005, 0.0003, 0.00015])
parser.add_argument("--offsets_mm", type=float, nargs="+", default=[0.0, 1.0, 2.5, 4.0])
parser.add_argument("--dt", type=float, default=1 / 500)
parser.add_argument("--substeps", type=int, default=4)
parser.add_argument("--speed", type=float, default=0.02, help="insertion target speed, m/s")
parser.add_argument("--elliptic", action="store_true", help="elliptic cone + impratio 10 (grasp profile)")
args = parser.parse_args()

travel = float(MC4.insertion_travel)


def run(clearance: float, offset: float) -> dict:
    tmp = Path(tempfile.mkdtemp())
    male = build.build_mc4_male(tmp, clearance=clearance)
    female = build.build_mc4_female(tmp, clearance=clearance)
    b = newton.ModelBuilder()
    b.add_usd(str(male), floating=False, xform=wp.transform((0, 0, 0.5), wp.quat_identity()))
    start = (0.03, offset, 0.5)
    b.add_usd(str(female), floating=True, xform=wp.transform(start, wp.quat_identity()))
    model = b.finalize()
    extra = dict(cone="elliptic", impratio=10.0) if args.elliptic else {}
    solver = newton.solvers.SolverMuJoCo(model, use_mujoco_contacts=False, integrator="implicitfast", **extra)
    s0, s1, ctrl = model.state(), model.state(), model.control()
    newton.eval_fk(model, model.joint_q, model.joint_qd, s0)
    pipeline = newton.CollisionPipeline(model)
    contacts = pipeline.contacts()
    fb = model.body_count - 1  # female is the last body
    m = float(MC4.housing_mass)
    kp_ax, kp_lat, kd = 400.0, 300.0, 3.0  # N/m, N/m, N*s/m  (soft gripper stand-in)
    sim_dt = args.dt / args.substeps
    # Explicit rotational spring/damper must respect the tiny roll inertia: kd*dt/I < 0.5, (w*dt) < 0.3.
    i_min = float(model.body_inertia.numpy()[fb].diagonal().min())
    kdr = 0.4 * i_min / sim_dt
    kr = (0.25 / sim_dt) ** 2 * i_min
    T = 4.0
    peak_lat = 0.0
    bf = np.zeros((model.body_count, 6), dtype=np.float32)
    for k in range(int(T / sim_dt)):
        t = k * sim_dt
        q = s0.body_q.numpy()[fb]
        qd = s0.body_qd.numpy()[fb]
        p, quat = q[:3], q[3:]
        target_x = max(start[0] - args.speed * t, -travel - 0.004)  # aim past the back stop
        err = np.array([target_x, offset, 0.5]) - p  # commanded target carries the misalignment
        f = np.array([kp_ax * err[0], kp_lat * err[1], kp_lat * err[2]]) - kd * qd[:3]
        f[2] += m * 9.81  # gripper carries the weight
        rot_err = -2.0 * np.array(quat[:3]) * np.sign(quat[3])  # small-angle error to identity (xyzw)
        bf[fb] = np.r_[f, kr * rot_err - kdr * qd[3:]]
        s0.body_f.assign(bf)
        pipeline.collide(s0, contacts)
        solver.step(s0, s1, ctrl, contacts, sim_dt)
        s0, s1 = s1, s0
        if t > 1.0:
            qn = s0.body_q.numpy()[fb]
            peak_lat = max(peak_lat, float(np.hypot(qn[1], qn[2] - 0.5)))  # noqa: F841
    q = s0.body_q.numpy()[fb]
    depth = -q[0]  # tip x relative to mouth (mouth at x=0)
    lat = float(np.hypot(q[1], q[2] - 0.5))
    tilt = float(np.degrees(2 * np.arcsin(min(1.0, np.linalg.norm(q[3:6])))))
    ok = np.all(np.isfinite(q))
    return dict(
        depth_mm=depth * 1e3,
        lat_mm=lat * 1e3,
        tilt_deg=tilt,
        finite=bool(ok),
        tunnelled=bool(lat > float(MC4.sleeve_inner_radius)),
    ), peak_lat


print(f"dt={args.dt}s substeps={args.substeps} speed={args.speed} m/s  (seated = depth ~{travel * 1e3:.1f} mm)")
for clr in args.clearance:
    for off in args.offsets_mm:
        r, _ = run(clr, off * 1e-3)
        verdict = (
            "SEATED"
            if r["depth_mm"] > travel * 1e3 - 0.8 and not r["tunnelled"]
            else ("MISSED (on rim)" if r["tunnelled"] else "JAMMED/SHORT")
        )
        print(
            f"clearance={clr * 1e3:.2f}mm offset={off:.1f}mm -> depth={r['depth_mm']:6.2f}mm "
            f"lat={r['lat_mm']:5.2f}mm tilt={r['tilt_deg']:5.2f}deg finite={r['finite']}  {verdict}"
        )
