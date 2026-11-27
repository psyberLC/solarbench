
### SolarBench-T3-ClampTighten-UR16e-R2-v0

|  | privileged | valid / run | engaged | snug | in_spec | released | safe success | damage | time to release, s (median) |
|---|---|---|---|---|---|---|---|---|---|
| oracle (scripted, privileged) | yes | 8/8 | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 0/8 (0%, 0–32) | 15.2 |
| skills, fixed sequence, unprivileged | no | 8/8 | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 0/8 (0%, 0–32) | 17.4 |
| skills, Nemotron 3.5 Lightning, unprivileged | no | 8/8 | 5/8 (62%, 31–86) | 4/8 (50%, 22–78) | 2/8 (25%, 7–59) | 2/8 (25%, 7–59) | 2/8 (25%, 7–59) | 0/8 (0%, 0–32) | 19.5 |

skills, Nemotron 3.5 Lightning, unprivileged: 58 model calls over 8 episodes (median 6 per episode), thinking + reply median 448 tokens per call (max 2199), model time 22.0 min; calls without a usable tool call: 0.
Per episode: ep 0: safe, 14.98 N·m; ep 1: failed, 1.12 N·m; ep 2: failed, 0.56 N·m; ep 3: safe, 15.59 N·m; ep 4: failed, 4.39 N·m; ep 5: failed, 2.94 N·m; ep 6: failed, 3.81 N·m; ep 7: failed, 0.53 N·m.

oracle (scripted, privileged), installed torque by episode (N·m): 16.08, 16.05, 16.05, 16.02, 16.04, 16.02, 16.04, 16.03
skills, fixed sequence, unprivileged, installed torque by episode (N·m): 15.47, 15.46, 15.53, 15.56, 15.43, 15.51, 15.47, 15.59
skills, Nemotron 3.5 Lightning, unprivileged, installed torque by episode (N·m): 14.98, 1.12, 0.56, 15.59, 4.39, 2.94, 3.81, 0.53

### SolarBench-T2-MC4-G1-v0

|  | privileged | valid / run | grasped | unlocked | separated | realigned | relatched | released | safe success | damage | time to release, s (median) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| oracle (scripted, privileged) | yes | 7/8 | 7/7 (100%, 65–100) | 7/7 (100%, 65–100) | 7/7 (100%, 65–100) | 7/7 (100%, 65–100) | 7/7 (100%, 65–100) | 7/7 (100%, 65–100) | 7/7 (100%, 65–100) | 0/7 (0%, 0–35) | 5.1 |
| phase skills, fixed sequence, privileged | yes | 8/8 | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 7/8 (88%, 53–98) | 7/8 (88%, 53–98) | 7/8 (88%, 53–98) | 0/8 (0%, 0–32) | 6.3 |
| phase skills, Nemotron 3.5 Lightning, privileged | yes | 8/8 | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 8/8 (100%, 68–100) | 0/8 (0%, 0–32) | 6.8 |

phase skills, Nemotron 3.5 Lightning, privileged: 32 model calls over 8 episodes (median 4 per episode), thinking + reply median 111 tokens per call (max 201), model time 2.1 min; calls without a usable tool call: 0.
Per episode: ep 0: safe; ep 1: safe; ep 2: safe; ep 3: safe; ep 4: safe; ep 5: safe; ep 6: safe; ep 7: safe.

