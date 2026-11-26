"""Scripted oracles, keyed by task id prefix."""


def make_oracle(task: str, env, **kwargs):
    if task.startswith("SolarBench-T2-"):
        from .mc4_oracle import MC4Oracle

        return MC4Oracle(env, **kwargs)
    if task.startswith("SolarBench-T3-"):
        from .clamp_oracle import ClampOracle

        return ClampOracle(env)
    raise KeyError(f"no oracle for {task}")
