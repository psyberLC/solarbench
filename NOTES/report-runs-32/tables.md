
### SolarBench-T3-ClampTighten-UR16e-R2-v0

|  | privileged | valid / run | engaged | snug | in_spec | released | safe success | damage | time to release, s (median) |
|---|---|---|---|---|---|---|---|---|---|
| oracle (scripted, privileged) | yes | 32/32 | 30/32 (94%, 80–98) | 30/32 (94%, 80–98) | 30/32 (94%, 80–98) | 30/32 (94%, 80–98) | 30/32 (94%, 80–98) | 0/32 (0%, 0–11) | 15.0 |
| skills, fixed sequence, unprivileged | no | 32/32 | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 0/32 (0%, 0–11) | 18.0 |
| skills, Nemotron 3.5 Super, unprivileged | no | 32/32 | 29/32 (91%, 76–97) | 29/32 (91%, 76–97) | 27/32 (84%, 68–93) | 26/32 (81%, 65–91) | 26/32 (81%, 65–91) | 0/32 (0%, 0–11) | 16.9 |

skills, Nemotron 3.5 Super, unprivileged: 215 model calls over 32 episodes (median 6 per episode), thinking + reply median 209 tokens per call (max 12288), model time 27.2 min; calls without a usable tool call: 2.
Per episode: ep 0: safe, 15.97 N·m; ep 1: safe, 15.99 N·m; ep 2: safe, 16.11 N·m; ep 3: safe, 15.65 N·m; ep 4: safe, 15.93 N·m; ep 5: safe, 16.01 N·m; ep 6: safe, 15.95 N·m; ep 7: safe, 16.10 N·m; ep 8: failed, 1.03 N·m; ep 9: failed, 8.88 N·m; ep 10: safe, 15.86 N·m; ep 11: safe, 15.91 N·m; ep 12: safe, 16.10 N·m; ep 13: safe, 15.87 N·m; ep 14: safe, 15.82 N·m; ep 15: safe, 16.04 N·m; ep 16: failed, 2.34 N·m; ep 17: failed, 2.63 N·m; ep 18: failed, 2.72 N·m; ep 19: safe, 16.04 N·m; ep 20: safe, 15.83 N·m; ep 21: safe, 15.47 N·m; ep 22: safe, 16.01 N·m; ep 23: safe, 15.97 N·m; ep 24: safe, 15.90 N·m; ep 25: safe, 16.01 N·m; ep 26: safe, 15.68 N·m; ep 27: safe, 16.00 N·m; ep 28: safe, 15.74 N·m; ep 29: failed, 10.96 N·m; ep 30: safe, 15.97 N·m; ep 31: safe, 15.99 N·m.

oracle (scripted, privileged), installed torque by episode (N·m): 16.08, 16.05, 16.05, 16.02, 16.04, 16.02, 16.04, 16.03, 16.01, 16.09, 16.09, 16.04, 16.03, 16.09, 16.09, 16.07, 16.06, 16.01, 16.09, 16.06, 16.11, 16.02, 16.02, 16.06, 16.10, 16.04, 16.01, 16.03, 16.04, 16.02, 16.01, 16.05
skills, fixed sequence, unprivileged, installed torque by episode (N·m): 15.47, 15.47, 15.64, 15.55, 15.42, 15.51, 15.47, 15.60, 15.56, 15.55, 15.39, 15.40, 15.81, 15.45, 15.36, 15.45, 15.44, 15.55, 15.31, 15.56, 15.34, 15.47, 15.58, 15.44, 15.39, 15.53, 15.62, 15.51, 14.49, 15.60, 15.53, 15.46
skills, Nemotron 3.5 Super, unprivileged, installed torque by episode (N·m): 15.97, 15.99, 16.11, 15.65, 15.93, 16.01, 15.95, 16.10, 1.03, 8.88, 15.86, 15.91, 16.10, 15.87, 15.82, 16.04, 2.34, 2.63, 2.72, 16.04, 15.83, 15.47, 16.01, 15.97, 15.90, 16.01, 15.68, 16.00, 15.74, 10.96, 15.97, 15.99

### SolarBench-T2-MC4-G1-v0

|  | privileged | valid / run | grasped | unlocked | separated | realigned | relatched | released | safe success | damage | time to release, s (median) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| oracle (scripted, privileged) | yes | 32/32 | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 0/32 (0%, 0–11) | 5.1 |
| phase skills, fixed sequence, privileged | yes | 31/32 | 31/31 (100%, 89–100) | 31/31 (100%, 89–100) | 31/31 (100%, 89–100) | 31/31 (100%, 89–100) | 29/31 (94%, 79–98) | 29/31 (94%, 79–98) | 29/31 (94%, 79–98) | 0/31 (0%, 0–11) | 5.3 |
| phase skills, Nemotron 3.5 Super, privileged | yes | 31/32 | 31/31 (100%, 89–100) | 31/31 (100%, 89–100) | 31/31 (100%, 89–100) | 31/31 (100%, 89–100) | 28/31 (90%, 75–97) | 28/31 (90%, 75–97) | 28/31 (90%, 75–97) | 0/31 (0%, 0–11) | 5.3 |

phase skills, Nemotron 3.5 Super, privileged: 135 model calls over 32 episodes (median 4 per episode), thinking + reply median 124 tokens per call (max 929), model time 3.3 min; calls without a usable tool call: 0.
Per episode: ep 0: safe; ep 1: safe; ep 2: safe; ep 3: safe; ep 4: safe; ep 5: failed; ep 6: safe; ep 7: safe; ep 8: safe; ep 9: safe; ep 10: failed; ep 11: safe; ep 12: safe; ep 13: safe; ep 14: sim error; ep 15: safe; ep 16: safe; ep 17: safe; ep 18: safe; ep 19: safe; ep 20: safe; ep 21: safe; ep 22: safe; ep 23: safe; ep 24: safe; ep 25: failed; ep 26: safe; ep 27: safe; ep 28: safe; ep 29: safe; ep 30: safe; ep 31: safe.

