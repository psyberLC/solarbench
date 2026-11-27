"""A chat-completions endpoint answered by an agent through files, so an agent can drive a run as a model would.

Each request is written to <dir>/request-NNN.json (the full message list) and answered by whatever text appears in
<dir>/reply-NNN.txt. The endpoint policy sees an ordinary server: same prompts, same parser, same round rules.
NOTES/probes/agent_wait.py is the agent's side.

  .venv/bin/python NOTES/probes/agent_bridge.py --dir DIR [--port 8082]
  SOLARBENCH_ENDPOINT_URL=http://127.0.0.1:8082/v1 .venv/bin/python scripts/evaluate.py ... --policy endpoint:...
"""

import argparse
import json
import pathlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

parser = argparse.ArgumentParser()
parser.add_argument("--dir", required=True)
parser.add_argument("--port", type=int, default=8082)
args = parser.parse_args()
folder = pathlib.Path(args.dir)
folder.mkdir(parents=True, exist_ok=True)
lock = threading.Lock()
count = len(list(folder.glob("request-*.json")))


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
        with lock:
            count += 1
            n = count
        reply = folder / f"reply-{n:03d}.txt"
        (folder / f"request-{n:03d}.json").write_text(json.dumps(request, indent=1))
        print(f"{time.strftime('%H:%M:%S')} request {n} waiting", flush=True)
        while not reply.exists():
            time.sleep(0.5)
        time.sleep(0.2)  # let the writer finish
        content = reply.read_text()
        print(f"{time.strftime('%H:%M:%S')} request {n} answered: {content.strip()[-120:]}", flush=True)
        self._send({"object": "chat.completion", "model": request.get("model"),
                    "usage": {"prompt_tokens": None, "completion_tokens": None},
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                                 "finish_reason": "stop"}]})

    def log_message(self, *_):
        pass


print(f"bridge on http://127.0.0.1:{args.port}, files in {folder}", flush=True)
ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
