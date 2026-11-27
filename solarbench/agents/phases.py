"""A model behind a chat-completions endpoint that sequences a scripted oracle's phases, called as tools (profile R1).

For tasks without a pose interface, such as the humanoid connector task (T2), this is the only way a model can act
in this repository: the model chooses which skill to run and when, and each skill runs the oracle's own controller
for a group of its phases, one R1 action per tick, until the oracle moves past that group or a time limit passes.
It reads the environment as the oracle does, so it is privileged, and the motion is the oracle's: a run shows
whether the model orders the steps well, not whether it can control the robot. Exploratory, never a benchmark.
    --policy phases:<model>,notes=<job description file>[,reasoning=on][,temperature=0.6][,max_tokens=12288]
                    [,seed=0][,rounds=20][,log=<file.jsonl>][,url=<base url>]
The environment variables of the endpoint policy (SOLARBENCH_ENDPOINT_URL, _LOG, _KEY) apply.
"""

from __future__ import annotations

import json
import os
import pathlib
import threading
import time

import torch

from solarbench.agents import register, select
from solarbench.agents.endpoint import post

# T2's oracle phases (solarbench/oracle/mc4_oracle.py, PHASES), grouped into skills: (first, last, time limit s)
SKILLS = {"grasp": (0, 2, 10.0), "unplug": (3, 5, 9.0), "plug_in": (6, 7, 8.0), "release": (8, 9, 4.0)}
DESCRIPTIONS = {
    "grasp": "Move the open hand to the connector's housing along the palm's normal, stop on contact, and close "
             "the fingers around it.",
    "unplug": "Hold the latch arms open, pull the housing straight out of the sleeve along its axis, and hold it "
              "squared up a few centimetres out.",
    "plug_in": "Bring the held housing in front of the sleeve's mouth, aligned with its axis, and push it in "
               "through the detent until the latch engages.",
    "release": "Open the hand and move it away from the connector.",
    "done": "The job is finished or cannot be finished.",
}
TOOLS = [{"type": "function", "function": {"name": name, "description": text,
                                           "parameters": {"type": "object", "properties": {}, "required": []}}}
         for name, text in DESCRIPTIONS.items()]
OPTIONS = {"reasoning": "on", "temperature": "0.6", "max_tokens": "12288", "seed": "0", "rounds": "20", "log": "",
           "url": "", "notes": ""}
INTRO = """You control a Unitree G1 humanoid with a dexterous right hand, through skills you call as tools: call \
exactly one tool each turn. Each skill runs to its end on its own; its result tells you how it ended and what the \
robot senses. Keep calling tools until the job is finished, then call done.
"""


class PhasesPolicy:
    def __init__(self, arg: str, catalogue: dict):
        model, *given = arg.split(",")
        given = dict(option.split("=", 1) for option in given)
        if not model or set(given) - set(OPTIONS):
            raise ValueError(f"phases:<model>[,{'][,'.join(f'{k}=' for k in OPTIONS)}], got {arg!r}")
        o = {k: given.get(k, os.environ.get(f"SOLARBENCH_ENDPOINT_{k.upper()}", v)) for k, v in OPTIONS.items()}
        if not o["url"] or not o["notes"]:
            raise ValueError("phases needs an endpoint (SOLARBENCH_ENDPOINT_URL or url=) and notes=<job file>")
        self._url, self._log, self._lock = o["url"].rstrip("/") + "/chat/completions", o["log"], threading.Lock()
        self.selection = {**select(catalogue, "policy"), "depth": 1, "wake": "tick"}
        self.name = "phases-" + "".join(c if c.isalnum() or c == "." else "-" for c in model)
        self.settings = {"model": model, "reasoning": o["reasoning"] == "on", "temperature": float(o["temperature"]),
                         "max_tokens": int(o["max_tokens"]), "seed": int(o["seed"]), "rounds": int(o["rounds"]),
                         "notes": os.path.basename(o["notes"])}
        self._system = INTRO + "\n" + pathlib.Path(o["notes"]).read_text()
        self._task, self.calls, self.finished = catalogue["task"], {}, []

    def attach(self, env) -> None:
        from solarbench.oracle import make_oracle

        self._env, self._oracle = env, make_oracle(self._task, env)
        n = env.num_envs
        self._messages, self._call = [None] * n, [None] * n
        self._skill: list[tuple[str, float] | None] = [None] * n  # (name, seconds run)
        self._grip = torch.full((n,), -1.0, device=env.device)  # held between skills, so a grasp is not dropped

    def reset(self, env_ids, work_orders):
        ids = torch.as_tensor(env_ids).tolist()
        self._oracle.reset(torch.as_tensor(ids, device=self._env.device))
        for env, work_order in zip(ids, work_orders, strict=True):
            if self.calls.get(env):
                self.finished.append(self.calls[env])
            self.calls[env] = []
            first = (work_order + "\n\n" if work_order else "") + "## The robot now\n" + self._state(env)
            self._messages[env] = [{"role": "system", "content": self._system}, {"role": "user", "content": first}]
            self._call[env], self._skill[env] = None, None
            self._grip[env] = -1.0

    def _state(self, env: int) -> str:
        e = self._env
        reached = [name for name, t in zip(e.stages, e.stage_time[env].tolist(), strict=True) if t >= 0]
        depth = float(e.depth[env]) * 1e3
        where = (f"the plug's tip is {depth:.1f} mm inside the sleeve" if depth >= 0
                 else f"the plug's tip is {-depth:.1f} mm out of the sleeve")
        return "\n".join([
            f"time {float(e.episode_length_buf[env]) * e.step_dt:.1f} s",
            f"hand holds the housing: {'yes' if bool(e.grasped[env]) else 'no'}",
            f"latch: {'engaged' if bool(e.latch.latched[env]) else 'not engaged'}"
            + (", arms held open" if bool(e.latch.open[env]) else ""),
            f"{where}; {float(e._lateral[env]) * 1e3:.1f} mm off the sleeve's axis",
            f"force on the hand {float(e.f_hand_w[env].norm()):.1f} N; "
            f"cable tension {float(e.cable_tension[env]):.1f} N",
            "stages reached: " + (", ".join(reached) if reached else "none")])

    def _ask(self, env: int, text: str):
        messages = self._messages[env]
        if self._call[env]:
            messages.append({"role": "tool", "tool_call_id": self._call[env], "content": text})
        elif text:
            messages.append({"role": "user", "content": text})
        for retry in (False, True):
            s, started = self.settings, time.perf_counter()
            body = {"model": s["model"], "messages": messages, "tools": TOOLS, "temperature": s["temperature"],
                    "max_tokens": s["max_tokens"], "seed": s["seed"] + retry,
                    "chat_template_kwargs": {"enable_thinking": s["reasoning"]}}
            answer = post(self._url, body)
            message = answer["choices"][0]["message"]
            reply = message.get("content") or ""
            thought = message.get("reasoning_content") or message.get("reasoning") or ""
            calls = message.get("tool_calls") or []
            name = (calls[0].get("function") or {}).get("name") if calls else None
            usage = answer.get("usage", {})
            call = {"wall_s": time.perf_counter() - started, "tokens_read": usage.get("prompt_tokens"),
                    "tokens_written": usage.get("completion_tokens"), "parsed": name in DESCRIPTIONS,
                    "retry": retry, "skill": name}
            self.calls[env].append(call)
            if self._log:
                with self._lock, open(self._log, "a") as f:
                    f.write(json.dumps({"env": env, "round": len(self.calls[env]), **call, "reply": reply,
                                        "reasoning": thought}) + "\n")
            if name in DESCRIPTIONS:
                first = {**calls[0], "id": calls[0].get("id") or f"call-{len(messages)}"}
                messages.append({"role": "assistant", "content": reply, "tool_calls": [first],
                                 **({"reasoning_content": thought} if thought else {})})
                self._call[env] = first["id"]
                return name
        messages.append({"role": "assistant", "content": reply, **({"reasoning_content": thought} if thought else {})})
        self._call[env] = None
        return None

    def act(self, obs):
        e, n = self._env, self._env.num_envs
        action = torch.zeros(n, 8, device=e.device)
        action[:, 7] = -1.0
        running = [env for env in range(n) if self._skill[env] is not None]
        if running:
            full = self._oracle.act()  # advances the oracle's phases; only running environments use its action
        for env in range(n):
            skill = self._skill[env]
            if skill is not None:
                name, seconds = skill
                first, last, limit = SKILLS[name]
                if int(self._oracle.phase[env]) <= last and seconds < limit:
                    action[env] = full[env]
                    self._grip[env] = full[env, 6]
                    self._skill[env] = (name, seconds + e.step_dt)
                    continue
                self._skill[env] = None
                ended = "finished" if int(self._oracle.phase[env]) > last else f"stopped by its {limit:.0f} s limit"
                text = f"{name} {ended}\n" + self._state(env)
            else:
                text = ""
            if sum(not c["retry"] for c in self.calls[env]) >= self.settings["rounds"] or (
                    skill is None and self.calls[env] and self._call[env] == "done"):
                action[env, 6] = self._grip[env]
                continue
            name = self._ask(env, text)
            if name in SKILLS:
                self._oracle.phase[env], self._oracle.timer[env] = SKILLS[name][0], 0.0
                self._skill[env] = (name, 0.0)
            elif name == "done":
                self._call[env] = "done"
            action[env, 6] = self._grip[env]
        return action


register("phases")(PhasesPolicy)
