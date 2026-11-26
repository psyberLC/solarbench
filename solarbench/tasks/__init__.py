"""SolarBench task registrations (discovered via the isaaclab.tasks entry point).

Task ids are frozen once results are published under them: a change to physics, observations or
success criteria gets a new version suffix, never an edit in place.
"""

import gymnasium as gym

gym.register(
    id="SolarBench-T2-MC4-G1-v0",
    entry_point=f"{__name__}.mc4_env:MC4Env",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.mc4_env_cfg:MC4EnvCfg",
        "rsl_rl_cfg_entry_point": f"{__name__}.mc4_ppo_cfg:MC4PPORunnerCfg",
        "default_agent": "rsl_rl",
    },
)

for _mode, _cfg in (("Tighten", "ClampEnvCfg"), ("Loosen", "ClampLoosenEnvCfg")):
    gym.register(
        id=f"SolarBench-T3-Clamp{_mode}-UR16e-v0",
        entry_point=f"{__name__}.clamp_env:ClampEnv",
        disable_env_checker=True,
        kwargs={
            "env_cfg_entry_point": f"{__name__}.clamp_env_cfg:{_cfg}",
            "rsl_rl_cfg_entry_point": f"{__name__}.clamp_ppo_cfg:ClampPPORunnerCfg",
            "default_agent": "rsl_rl",
        },
    )
