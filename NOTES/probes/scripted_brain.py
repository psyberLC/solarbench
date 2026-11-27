"""A fixed plan behind the endpoint, to test what the helper commands do in contact (no model involved).

Reads the privileged lines of each state report (commands=assist, privileged=on) and answers:
  1. aim STANDOFF mm out from the head top on the bolt axis, socket pointing into the bolt, until centred;
  2. then press PRESS mm past the head top while turning TURN degrees, re-aiming if the socket drifts > 0.6 mm;
  3. once engaged (and more than 2 mm deep: the flag is stale on an episode's first report), {"done": true}.
Prints one line per round (depth, offset, tilt, drive torque, engaged) and a summary per episode.

  .venv/bin/python NOTES/probes/scripted_brain.py --press 1.5 --turn 30 [--port 8084]
"""

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

parser = argparse.ArgumentParser()
parser.add_argument("--press", type=float, default=1.5, help="mm past the head top to press while turning")
parser.add_argument("--turn", type=float, default=30.0, help="degrees per press-and-turn command")
parser.add_argument("--standoff", type=float, default=2.0, help="mm out from the head top to aim at first")
parser.add_argument("--port", type=int, default=8084)
args = parser.parse_args()


def numbers(text: str, label: str) -> list[float]:
    line = next(line for line in text.splitlines() if line.startswith(label))
    return [float(x) for x in re.findall(r"-?\d+\.\d+", line.split(":", 1)[1])]


def plan(state: str) -> tuple[str, dict]:
    depth, offset = numbers(state, "socket depth")[0], numbers(state, "socket axis off")[0]
    tilt, engaged = numbers(state, "socket axis tilted")[0], numbers(state, "engaged")[0]
    tool, rel, axis = numbers(state, "tool_pos"), numbers(state, "head_top_minus_tool"), numbers(state, "bolt_axis")
    head = [t + r for t, r in zip(tool, rel, strict=True)]
    drive, wrist = numbers(state, "drive_torque")[0], numbers(state, "joint_pos")[5]
    row = (f"depth {depth:6.2f} mm  off {offset:5.2f} mm  tilt {tilt:4.2f} deg  drive {drive:6.3f} N*m  "
           f"wrist3 {wrist:6.3f} rad  engaged {engaged:.0f}")
    if engaged > 0.5 and depth > 2.0:
        return row, {"done": True}
    if offset > 0.6 or depth < -3.0 or tilt > 1.0:  # far off: stop 30 mm out on the axis first, then come in
        out = 0.030 if offset > 3.0 or depth < -40.0 else args.standoff / 1000
        aim = [h + out * a for h, a in zip(head, axis, strict=True)]
        return row, {"aim": aim, "socket_toward": [-a for a in axis]}
    return row, {"push_mm": max(0.0, -depth) + args.press, "turn_deg": args.turn}


class Handler(BaseHTTPRequestHandler):
    episode, rounds = -1, 0

    def do_POST(self):
        messages = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))["messages"]
        if sum(m["role"] == "user" for m in messages) == 2:
            Handler.episode, Handler.rounds = Handler.episode + 1, 0
        Handler.rounds += 1
        row, command = plan(messages[-1]["content"])
        print(f"ep {Handler.episode} round {Handler.rounds:2d}: {row}  -> {json.dumps(command)}", flush=True)
        if command.get("done"):
            print(f"== episode {Handler.episode}: engaged after {Handler.rounds - 1} commands", flush=True)
        body = json.dumps({"choices": [{"message": {"content": json.dumps(command)}, "finish_reason": "stop"}],
                           "usage": {}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_):
        pass


print(f"scripted brain: press {args.press} mm, turn {args.turn} deg, on port {args.port}", flush=True)
ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
