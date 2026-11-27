"""Throughput of the model server with the real prompt: N concurrent requests, one round each.

Usage: .venv/bin/python NOTES/probes/bench_server.py <concurrent> <reasoning on|off> [temperature] [endpoint.py]
"""

import ast
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from solarbench.agents import prompts

TASK = "SolarBench-T3-ClampTighten-UR16e-R2-v0"
REPLY = ast.literal_eval(re.search(r'^REPLY = (""".*?""")', Path(sys.argv[4] if len(sys.argv) > 4 else
                         "solarbench/agents/endpoint.py").read_text(), re.S | re.M).group(1))  # the adapter's text
n, reasoning = int(sys.argv[1]), sys.argv[2] == "on"
temperature = float(sys.argv[3]) if len(sys.argv) > 3 else (1.0 if reasoning else 0.0)
values = dict(loose_min_deg=149.0, loose_max_deg=212.0, installed_min=14.0, installed_max=18.0, engage_depth_mm=2.5,
              engage_lateral_mm=1.2, engage_angle_deg=6.0, torque_min=14.0, torque_max=18.0, backoff_turns=0.75,
              released_mm=30.0, time_limit_s=30.0, head_y=0.015, head_z=0.439, axis_x=0.0, axis_y=0.0, axis_z=1.0)
STATE = """tick 0
joint_pos [rad]: 0.0412, -1.6311, 1.9502, -1.8903, -1.5708, -0.0391
joint_vel [rad/s]: 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000
tool_pos [m]: 0.4021, 0.0120, 0.6314
tool_quat [xyzw]: 0.9999, 0.0031, -0.0102, 0.0005
force [N]: 0.0000, 0.0000, 0.0000
torque [N*m]: 0.0000, 0.0000, 0.0000"""


def one(i):
    wo = prompts.work_order(TASK, head_x=0.42 + 0.001 * i, **values)  # a distinct work order per request
    body = {"model": "m", "temperature": temperature, "max_tokens": 4096, "seed": i,
            "chat_template_kwargs": {"enable_thinking": reasoning},
            "messages": [{"role": "system", "content": prompts.body(TASK, True) + REPLY},
                         {"role": "user", "content": wo}, {"role": "user", "content": STATE}]}
    t = time.perf_counter()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=3600))
    tm, m = d["timings"], d["choices"][0]["message"]
    return dict(wall=time.perf_counter() - t, prompt_n=tm["prompt_n"], cache_n=tm["cache_n"],
                prompt_tps=tm["prompt_per_second"], gen_n=tm["predicted_n"], gen_tps=tm["predicted_per_second"],
                finish=d["choices"][0]["finish_reason"], reply=(m.get("content") or "")[-160:])


t0 = time.perf_counter()
with ThreadPoolExecutor(n) as pool:
    results = list(pool.map(one, range(n)))
wall = time.perf_counter() - t0
for r in results:
    print({k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()})
total = sum(r["gen_n"] for r in results)
print(f"{n} concurrent, reasoning {'on' if reasoning else 'off'}: wall {wall:.1f} s, {total} tokens written, "
      f"aggregate {total / wall:.1f} tok/s, slowest request {max(r['wall'] for r in results):.1f} s")
