"""A fixed sequence of tool calls behind the endpoint, to check the closed-loop skills in the simulation before a
model uses them (endpoint policy with tools=on,privileged=on,skills=on). No model involved.

Calls, one per turn: the ready "50 mm out" aim, the ready "0.5 mm out" aim, seat, tighten_to(TORQUE), unload,
retract(50), done. Each skill's outcome is printed as it comes back.

  .venv/bin/python NOTES/probes/scripted_skills.py [--torque 15.5] [--port 8085]
"""

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

parser = argparse.ArgumentParser()
parser.add_argument("--torque", type=float, default=15.5)
parser.add_argument("--port", type=int, default=8085)
args = parser.parse_args()


def ready_aim(state: str, label: str) -> dict:
    line = next(line for line in state.splitlines() if line.startswith(label))
    return json.loads(re.search(r"\{.*\}", line).group(0))


def plan(turn: int, state: str) -> tuple[str, dict]:
    steps = [("aim", lambda: ready_aim(state, "to put it 50 mm out")),
             ("aim", lambda: ready_aim(state, "to centre it 0.5 mm out")),
             ("seat", dict), ("tighten_to", lambda: {"torque_Nm": args.torque}), ("unload", dict),
             ("retract", lambda: {"mm": 50}), ("done", dict)]
    name, arguments = steps[min(turn, len(steps) - 1)]
    return name, arguments()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        messages = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))["messages"]
        turn = sum(m["role"] == "assistant" for m in messages)
        state = messages[-1]["content"]
        if "finished:" in state.split("\n", 1)[0]:
            print("  result:", state.split("\n", 1)[0], flush=True)
        name, arguments = plan(turn, state)
        print(f"turn {turn + 1}: {name}({json.dumps(arguments)})", flush=True)
        call = {"id": f"c{turn}", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}
        body = json.dumps({"choices": [{"message": {"role": "assistant", "content": "", "tool_calls": [call]},
                                        "finish_reason": "tool_calls"}], "usage": {}}).encode()
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


print(f"scripted skills caller on port {args.port}, tightening to {args.torque} N·m", flush=True)
ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
