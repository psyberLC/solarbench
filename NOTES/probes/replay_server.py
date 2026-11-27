"""Replay a recorded agent_bridge run: answer each request with the reply recorded for it, in order.

The sim waits for every reply, so the same replies should give the same run. Each request's newest message is compared
with the recorded one, and a difference is printed, so a replay that drifts from the original shows where.

  .venv/bin/python NOTES/probes/replay_server.py --dir DIR [--port 8083]
"""

import argparse
import json
import pathlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

parser = argparse.ArgumentParser()
parser.add_argument("--dir", required=True)
parser.add_argument("--port", type=int, default=8083)
args = parser.parse_args()
folder = pathlib.Path(args.dir)
count = 0


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
        count += 1
        request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        recorded = json.loads((folder / f"request-{count:03d}.json").read_text())
        same = request["messages"][-1]["content"] == recorded["messages"][-1]["content"]
        print(f"request {count}: {'same state as recorded' if same else 'DIFFERENT state from recorded'}", flush=True)
        if not same:
            print(f"  recorded: {recorded['messages'][-1]['content']!r}")
            print(f"  now:      {request['messages'][-1]['content']!r}")
        content = (folder / f"reply-{count:03d}.txt").read_text()
        self._send({"object": "chat.completion", "model": request.get("model"), "usage": {},
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                                 "finish_reason": "stop"}]})

    def log_message(self, *_):
        pass


print(f"replaying {folder} on http://127.0.0.1:{args.port}", flush=True)
ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
