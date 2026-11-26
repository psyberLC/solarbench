---
id: sim-bolt-newton-speed
title: Bolt tasks on Newton without a solver rebuild every substep
track: sim
milestone: v1
priority: stretch
needs: gpu
size: small
status: doing
owner: psyberLC
depends_on: []
touches:
  - "solarbench/tasks/clamp_env.py"
done_when:
  - "tools/check.sh --gpu"
  - "oracle on both bolt tasks, Newton, test split, 32 episodes, 16 environments, before and after the change: the same safe success, damage and stages for every episode index, and installed torque within 0.01 N·m"
  - "the wall time of those runs, before and after, is recorded in this item's log"
---
## Why
The bolt resistance is written as joint friction every physics substep. Newton 1.6.1's MuJoCo solver answers every joint-property change with a full `set_const_0`, about 58 ms on an RTX 4060 Laptop and 91% of a profiled run, so the bolt tasks run about ten times slower than they need to. Friction loss is not an input of `set_const_0`; the rebuild returns what it had.

## What
- When nothing but joint friction changed since the last full update, copy the joint properties into the solver and skip `set_const_0`. Any other joint-property change still takes the full path. Newton only; PhysX is untouched.
- No physics value changes: before and after give the same outcome for every episode index.
- The fast path works around a broad flag in Newton. `deps-watch` should drop it once Newton no longer rebuilds on friction-only changes.

## Log
<!-- Owner only. Newest last. Date and sign each entry. -->
