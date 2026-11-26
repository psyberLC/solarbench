# Interface contract: what a brain sees, what it may command, and how time passes

**Status: proposal.** It becomes `frozen v1` through the board item `contract-interface`. After the freeze, a change needs a new contract item.

**What the code does today:** only rung R1 with the privileged `policy` observation, as the [task cards](tasks.md) describe. The other keys, rungs and time modes below are what is being built.

The Python side of this contract is the `Policy` protocol in [`solarbench/agents/__init__.py`](../solarbench/agents/__init__.py). This document fixes the contents of the observation and action it carries.

## 1. Observation
`env.step` and `env.reset` return a dict of tensors batched over environments. A sensor-only policy may read every key except `policy`.

| Key | Shape (per environment) | Content |
|---|---|---|
| `prompt` | text, fixed per episode | The work order, for example "Tighten the end-clamp bolt at the east end of table R07-T12 to 16 N·m." Delivered once at reset through `env.unwrapped.prompts`, not as a tensor. |
| `proprio` | `(D,)` float32 | Joint positions (rad), joint velocities (rad/s), then tool pose in the robot base frame as position (m) and quaternion `xyzw`. The layout per robot is listed in [tasks.md](tasks.md). |
| `wrench` | `(6,)` float32 | Force (N) then torque (N·m) at the tool flange, in the tool frame, as a wrist sensor would report it. Present only when the task is configured with `force_feedback=True`. |
| `images/<camera>` | `(H, W, 3)` uint8 | RGB, row 0 at the top, lossless. Present only when cameras are enabled. Intrinsics `K` (3×3) and base-to-camera transform (4×4) are in `env.unwrapped.cameras`. |
| `policy` | `(N,)` float32 | **Privileged** state vector (exact object poses and flags) used by the reinforcement-learning baseline and the oracle. A result that used it is labelled privileged and never ranked against sensor-only results. |

- **Frames.** Base frame: x forward, y left, z up (REP-103). The world frame is used for scoring only and is never exposed.
- **Units.** SI throughout.
- **Camera names.** UR arm on the Husky: `wrist`, `overview`. G1: `head`, `left_wrist`, `right_wrist`.
- **Image size.** 640×480.
- **Wrench sensor model.** The contract fixes frame, units and order. Rate, noise and range are set where the channel is built and recorded in ASSUMPTIONS.md.
- **Proprio noise.** None in v1.

## 2. Action
The action mode is part of the task id, so a result always states which rung of the ladder it used.

| Rung | Mode | Action | Who does what |
|---|---|---|---|
| R1 | `ee_delta` | `(6,)`: Δ position (m) and Δ rotation (axis-angle, rad) of the tool, per 30 Hz step, clipped | The policy closes the loop at 30 Hz. Used by the oracle and the reinforcement-learning baseline. |
| R2 | `ee_pose` | `(7,)`: target tool pose in the base frame, position and quaternion `xyzw`, one per round | The policy picks waypoints; a fixed controller moves there under the robot's rate and torque limits and returns when it arrives, stalls or times out. This is the format PEAR and similar reasoning models emit. |
| R3 | `skill` | One call per round from a fixed list: `move_to`, `move_until_contact`, `push_with_force`, `turn_until_torque`, `retract`, `done` | The policy decides what to do and how hard; a fixed controller handles the contact and reports a status. |

Rules that hold on every rung:
- **Same limits.** Joint torque and velocity limits come from the manufacturer's robot description and apply to the fixed controllers exactly as they do to the oracle.
- **Controllers can fail.** A pose inside a collision stalls. A skill aimed at the wrong place misses. A torque request above the specification damages the bolt and is scored as damage.
- **No hidden help.** A fixed controller never uses object poses the policy was not given. Targets come from the policy.
- **Ending an episode.** The policy may send `done`; otherwise the episode ends at the time limit. Ending early without success is a failure, not a skip.

R2 takes quaternions only. An adapter for a model that emits roll-pitch-yaw converts them.

## 3. Time
| Mode | Meaning | Use |
|---|---|---|
| `lockstep` | The simulation waits while the policy computes. | Debugging, and the ceiling for what a model could do if it were instant. |
| `measured` | Simulated time advances by the wall-clock time each `act` call took; the robot holds its last command meanwhile. | The reported number for sensor-only policies. |
| `fixed:<s>` | As `measured`, with a declared delay. | Latency sweeps: where the brain runs (on board, on site, in a datacentre) becomes a number. |

- "Holds its last command" means zero motion on R1, the last target pose on R2, and the running skill on R3.
- Every result records the mode and the per-call delay distribution.
- There is no reference hardware for `measured`: the GPU model is recorded with the result, and results are plotted against the measured delay.

## 4. What a result must state
Today a result file records the task id, policy name, whether it was privileged, the split and the provenance (commit, clean tree, package versions, GPU, physics engine), checked by [`solarbench/eval/schema.py`](../solarbench/eval/schema.py). The board item `contract-result-fields` adds the observation keys enabled, the time mode and delays, the difficulty-dial value, the prompt hash, and the model name and endpoint kind.

## 5. Out of scope for v1
Joint-level action modes, action chunks at control rate (needed for vision-language-action models), multi-robot observation sharing, and streaming video. These are open tracks on the board.
