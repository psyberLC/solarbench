"""Show what the model is told and what it answers, live, while a run goes on.

Sits between the endpoint policy and llama-server. A chat request is passed on with streaming turned on, so the
thinking and the reply print as they are written; the policy still gets one ordinary (non-streamed) answer, rebuilt
from the stream with the fields it reads (content, reasoning_content, finish_reason, usage). Other requests pass
through unchanged. Full exchanges go to --log as JSON lines. When several requests run at once, the first prints
live and the others print when they end.

  .venv/bin/python NOTES/probes/watch_proxy.py [--port 8081] [--to http://127.0.0.1:8080] [--log FILE]
  SOLARBENCH_ENDPOINT_URL=http://127.0.0.1:8081/v1 .venv/bin/python scripts/evaluate.py ... --policy endpoint:...
"""

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8081)
parser.add_argument("--to", default="http://127.0.0.1:8080")
parser.add_argument("--log", default=None)
args = parser.parse_args()

DIM, BOLD, CYAN, YELLOW, RED, END = "\033[2m", "\033[1m", "\033[36m", "\033[33m", "\033[31m", "\033[0m"
screen, names, seen = threading.Lock(), threading.Lock(), {}


def header(request: dict) -> str:
    messages = request.get("messages", [])
    rounds = sum(m["role"] == "assistant" for m in messages) + 1
    key = messages[1]["content"][:200] if len(messages) > 1 else ""  # the work order names the conversation
    with names:
        conversation = seen.setdefault(key, len(seen))
    text = f"\n{BOLD}{CYAN}── conversation {conversation}, round {rounds}  ({time.strftime('%H:%M:%S')}){END}\n"
    newest = messages[-1] if messages else {"role": "", "content": ""}
    return text + f"{DIM}sent ({newest['role']}):\n{newest.get('content') or ''}{END}\n"


class Out:
    """Prints live when it holds the screen, otherwise keeps the text until the call ends."""

    def __init__(self):
        self.live, self.kept, self.mode = screen.acquire(blocking=False), [], None

    def write(self, text: str, mode: str | None = None) -> None:
        if mode != self.mode:
            text = {"think": f"{YELLOW}thinking:\n", "reply": f"{END}\n{BOLD}reply:{END} "}.get(mode, "") + text
            self.mode = mode
        if self.live:
            sys.stdout.write(text)
            sys.stdout.flush()
        else:
            self.kept.append(text)

    def close(self) -> None:
        if self.live:
            screen.release()
        else:
            with screen:
                sys.stdout.write("".join(self.kept))
                sys.stdout.flush()


def stream(request: dict, headers: dict) -> tuple[int, dict]:
    body = json.dumps({**request, "stream": True, "stream_options": {"include_usage": True}}).encode()
    upstream = urllib.request.Request(args.to + "/v1/chat/completions", body, headers, method="POST")
    out, started = Out(), time.perf_counter()
    out.write(header(request))
    content, thought, finish, usage, timings, model = [], [], None, {}, {}, request.get("model")
    calls: dict[int, dict] = {}  # tool calls, assembled from their streamed pieces by index
    try:
        with urllib.request.urlopen(upstream, timeout=1800) as response:
            for raw in response:
                line = raw.decode().strip()
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                chunk = json.loads(line[6:])
                model, usage = chunk.get("model", model), chunk.get("usage") or usage
                timings = chunk.get("timings") or timings
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta", {})
                    if delta.get("reasoning_content"):
                        thought.append(delta["reasoning_content"])
                        out.write(delta["reasoning_content"], "think")
                    if delta.get("content"):
                        content.append(delta["content"])
                        out.write(delta["content"], "reply")
                    for piece in delta.get("tool_calls") or []:
                        call = calls.setdefault(piece.get("index", 0), {"type": "function",
                                                                        "function": {"name": "", "arguments": ""}})
                        call["id"] = piece.get("id") or call.get("id")
                        for key in ("name", "arguments"):
                            call["function"][key] += (piece.get("function") or {}).get(key) or ""
                    finish = choice.get("finish_reason") or finish
    except urllib.error.HTTPError as error:
        out.write(f"{RED}server answered {error.code}{END}\n")
        out.close()
        return error.code, json.loads(error.read() or b"{}")
    wall = time.perf_counter() - started
    if "prompt_tokens_details" not in usage and "cache_n" in timings:
        usage["prompt_tokens_details"] = {"cached_tokens": timings["cache_n"]}
    out.write(f"{END}\n{DIM}({wall:.1f} s, read {usage.get('prompt_tokens')}, wrote {usage.get('completion_tokens')}, "
              f"finish {finish}){END}\n")
    out.close()
    message = {"role": "assistant", "content": "".join(content)}
    if thought:
        message["reasoning_content"] = "".join(thought)
    if calls:
        message["tool_calls"] = [calls[i] for i in sorted(calls)]
        out.write(f"{BOLD}tool call:{END} " + "; ".join(f"{c['function']['name']}({c['function']['arguments']})"
                                                       for c in message["tool_calls"]) + "\n")
    answer = {"object": "chat.completion", "model": model, "usage": usage,
              "choices": [{"index": 0, "message": message, "finish_reason": finish}]}
    if args.log:
        with names, open(args.log, "a") as f:
            f.write(json.dumps({"time": time.time(), "wall_s": wall, "request": request, "answer": answer}) + "\n")
    return 200, answer


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, data: bytes, kind: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _forward(self, body: bytes | None) -> None:
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length")}
        if body and self.path.endswith("/chat/completions"):
            status, answer = stream(json.loads(body), headers)
            self._send(status, json.dumps(answer).encode())
            return
        upstream = urllib.request.Request(args.to + self.path, body, headers, method=self.command)
        try:
            with urllib.request.urlopen(upstream, timeout=1800) as response:
                self._send(response.status, response.read(), response.headers.get("Content-Type", "text/plain"))
        except urllib.error.HTTPError as error:
            self._send(error.code, error.read())

    def do_GET(self):
        self._forward(None)

    def do_POST(self):
        self._forward(self.rfile.read(int(self.headers.get("Content-Length", 0))))

    def log_message(self, *_):
        pass


print(f"watching http://127.0.0.1:{args.port} -> {args.to}", flush=True)
ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
