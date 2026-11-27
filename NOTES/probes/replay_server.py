"""Play a recorded run back into the simulation: answer each request with the answer recorded for it, in order.

Two kinds of recording:
  --dir DIR             an agent_bridge run (DIR/request-NNN.json and DIR/reply-NNN.txt)
  --exchanges FILE      a model run recorded by watch_proxy.py --log (one JSON line per call: request and answer,
                        with thinking and tool calls)
The simulation waits for every answer, so the same answers should give the same run; it is not exactly repeatable
(contact forces drift in the 3rd-4th decimal after a few rounds), so each request's newest message is compared with
the recorded one and a difference is reported. The recorded thinking and reply are printed as each round is served.
--pace 1 waits as long as the model took (0, the default, answers at once); --pace 0.25 plays four times faster.

  .venv/bin/python NOTES/probes/replay_server.py --exchanges NOTES/live-runs/<run>/exchanges.jsonl --pace 0.5
  URL=http://127.0.0.1:8083/v1 ... NOTES/live.sh thinking=on      (the run's original settings; see its result file)
"""

import argparse
import json
import pathlib
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

parser = argparse.ArgumentParser()
source = parser.add_mutually_exclusive_group(required=True)
source.add_argument("--dir")
source.add_argument("--exchanges")
parser.add_argument("--port", type=int, default=8083)
parser.add_argument("--pace", type=float, default=0.0, help="fraction of the recorded wall time to wait per answer")
args = parser.parse_args()
DIM, BOLD, YELLOW, RED, END = "\033[2m", "\033[1m", "\033[33m", "\033[31m", "\033[0m"


def recorded() -> list[tuple[dict, dict, float]]:
    """(request, answer, wall seconds) for each recorded call, in order."""
    if args.exchanges:
        lines = [json.loads(line) for line in pathlib.Path(args.exchanges).read_text().splitlines() if line.strip()]
        return [(x["request"], x["answer"], x.get("wall_s", 0.0)) for x in lines]
    folder, calls = pathlib.Path(args.dir), []
    for request_file in sorted(folder.glob("request-*.json")):
        reply = folder / request_file.name.replace("request-", "reply-").replace(".json", ".txt")
        if reply.exists():
            message = {"role": "assistant", "content": reply.read_text()}
            calls.append((json.loads(request_file.read_text()), {"choices": [{"index": 0, "message": message,
                                                                              "finish_reason": "stop"}]}, 0.0))
    return calls


CALLS, count = recorded(), 0


class Handler(BaseHTTPRequestHandler):
    def _send(self, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send({"status": "ok"})

    def do_POST(self):
        global count
        request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        if count >= len(CALLS):
            print(f"{RED}request {count + 1}: the recording has only {len(CALLS)} calls{END}", flush=True)
            self.send_response(503)
            self.end_headers()
            return
        was, answer, wall = CALLS[count]
        count += 1
        same = request["messages"][-1].get("content") == was["messages"][-1].get("content")
        state = "same state as recorded" if same else "state differs from the recording"
        print(f"\n{BOLD}── call {count}/{len(CALLS)}: {state}{END}")
        if not same:
            print(f"{DIM}recorded: {was['messages'][-1].get('content')!r}")
            print(f"now:      {request['messages'][-1].get('content')!r}{END}")
        message = answer["choices"][0]["message"]
        if thought := message.get("reasoning_content") or message.get("reasoning"):
            print(f"{YELLOW}thinking:\n{thought.strip()}{END}")
        calls = "; ".join(f"{c['function']['name']}({c['function']['arguments']})"
                          for c in message.get("tool_calls") or [])
        print(f"{BOLD}reply:{END} {(message.get('content') or '').strip()} {calls}", flush=True)
        time.sleep(args.pace * wall)
        self._send(answer)

    def log_message(self, *_):
        pass


print(f"replaying {len(CALLS)} calls from {args.exchanges or args.dir} on http://127.0.0.1:{args.port}", flush=True)
ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
