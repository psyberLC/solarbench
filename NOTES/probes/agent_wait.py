"""The agent's side of agent_bridge.py: wait for the next request and print what is new in it.

Prints the request number, then, for the first request of a conversation, the system message and the work order,
and for every request the newest message. Exits 2 if nothing arrives within --timeout seconds.

  .venv/bin/python NOTES/probes/agent_wait.py --dir DIR [--timeout 540]
Answer request N by writing the reply text to DIR/reply-NNN.txt.
"""

import argparse
import json
import pathlib
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--dir", required=True)
parser.add_argument("--timeout", type=float, default=540)
args = parser.parse_args()
folder = pathlib.Path(args.dir)
deadline = time.time() + args.timeout
while time.time() < deadline:
    pending = [p for p in sorted(folder.glob("request-*.json"))
               if not (folder / p.name.replace("request-", "reply-").replace(".json", ".txt")).exists()]
    if pending:
        time.sleep(0.2)
        path = pending[0]
        messages = json.loads(path.read_text())["messages"]
        n = int(path.stem.split("-")[1])
        print(f"REQUEST {n} -> answer in {folder / f'reply-{n:03d}.txt'}")
        if sum(m["role"] == "user" for m in messages) <= 2:
            for m in messages[:-1]:
                print(f"=== {m['role']} ===\n{m['content']}\n")
        print(f"=== newest message ({messages[-1]['role']}) ===\n{messages[-1]['content']}")
        sys.exit(0)
    time.sleep(0.5)
print("no request arrived")
sys.exit(2)
