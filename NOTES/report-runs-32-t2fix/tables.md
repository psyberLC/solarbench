
### SolarBench-T2-MC4-G1-v0

|  | privileged | valid / run | grasped | unlocked | separated | realigned | relatched | released | safe success | damage | time to release, s (median) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| oracle (scripted, privileged) | yes | 32/32 | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 0/32 (0%, 0–11) | 5.1 |
| phase skills, fixed sequence, privileged | yes | 31/32 | 31/31 (100%, 89–100) | 31/31 (100%, 89–100) | 31/31 (100%, 89–100) | 31/31 (100%, 89–100) | 31/31 (100%, 89–100) | 31/31 (100%, 89–100) | 31/31 (100%, 89–100) | 0/31 (0%, 0–11) | 5.1 |
| phase skills, Nemotron 3.5 Super, privileged | yes | 32/32 | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 32/32 (100%, 89–100) | 0/32 (0%, 0–11) | 5.1 |

phase skills, Nemotron 3.5 Super, privileged: 128 model calls over 32 episodes (median 4 per episode), thinking + reply median 106 tokens per call (max 468), model time 2.1 min; calls without a usable tool call: 0.
Per episode: ep 0: safe; ep 1: safe; ep 2: safe; ep 3: safe; ep 4: safe; ep 5: safe; ep 6: safe; ep 7: safe; ep 8: safe; ep 9: safe; ep 10: safe; ep 11: safe; ep 12: safe; ep 13: safe; ep 14: safe; ep 15: safe; ep 16: safe; ep 17: safe; ep 18: safe; ep 19: safe; ep 20: safe; ep 21: safe; ep 22: safe; ep 23: safe; ep 24: safe; ep 25: safe; ep 26: safe; ep 27: safe; ep 28: safe; ep 29: safe; ep 30: safe; ep 31: safe.

