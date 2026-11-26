# Hypotheses and analysis plan, written before the runs

**Status: draft.** Frozen by the board item `paper-prereg` with the tag `prereg-v1`, before any model result exists. After that, changes go in a dated addendum at the end, never an edit.

## Question
Reasoning models can now drive robot arms, and reported results put them near zero on tasks decided by contact (insertion, plugging). In those evaluations the model receives no force signal. So:

> **Does giving a model the sense of force close the contact gap, and where does contact fail: in the body, in the model, or in the interface between them?**

## Design
A full factorial over the factors below, on tasks whose success is a physical specification.

| Factor | Levels |
|---|---|
| Task | Connector (unmate and re-mate an MC4 pair); Bolt (tighten an M8 clamp bolt into 14–18 N·m). Stretch: enclosure door |
| Body | UR16e on a parked Husky A300, at the manufacturer's limits |
| Brain | Zero (floor); scripted oracle (privileged ceiling); Qwen3.8-27B; Qwen3.8-27B-PEAR (the same model after simulation training to drive arms) |
| Interface | R2: one end-effector pose per round. R3: guarded force skills |
| Force feedback | Off; on (wrist force and torque in the observation, and in skill status) |
| Time | Lockstep; measured (the world advances while the model thinks) |
| Difficulty dial | 3.0, 1.5 and 1.0 times the real tolerance (1.0 is the specification) |

- The oracle and zero rows are run once per task and dial level; they do not vary with interface or force feedback.
- **Episodes:** at least 30 per cell for the language models, on held-out seeds, the same seeds in every cell. The oracle and zero rows use 100.
- **Prompts** are fixed before the runs and identical across brains (`agents-prompts`).

## Outcomes
- **Primary:** safe success at dial 1.0 (the task done to specification with no damage event).
- **Secondary:** margin to spec (the dial level with 50% safe success); damage rate; furthest stage reached; time to success; model calls, tokens and wall time per episode.
- **Failure label** for every failed episode, assigned by rule from the episode record: wrong target, no contact, lost contact, under-force (out of window low), over-force (damage), time out, malformed output.

## Hypotheses
- **H1. Without force feedback, specification-level contact fails.** With R2 and force off, both language models reach at most 10% safe success at dial 1.0 on both tasks.
- **H2. Force feedback helps.** With R2, switching force feedback on raises safe success at dial 1.0 on each task for at least one language model, with the interval of the paired difference excluding zero.
- **H3. Force feedback reduces damage.** On the bolt task with R2, the damage rate is lower with force on than off.
- **H4. The interface moves the bottleneck.** With force on, R3 gives higher safe success than R2, and the share of failures labelled wrong target or no contact rises while under- and over-force fall.
- **H5. Simulation training for motion does not transfer to contact for free.** PEAR beats the base model by a wider margin at dial 3.0 than at dial 1.0.
- **H6. Thinking time costs more where force must be stopped in time.** Going from lockstep to measured time lowers safe success more on the bolt task than on the connector task.

Each hypothesis can fail, and a failure is reported in the same table as a success. If the language models score zero everywhere, H2–H6 are untestable at dial 1.0 and are evaluated at the easiest dial level at which any cell exceeds 10%; that fallback is stated here so it is not a choice made after seeing the data.

## Analysis
- Rates with 95% Wilson intervals. Paired differences across the same seeds with bootstrap intervals.
- Margin to spec: an isotonic (pool-adjacent-violators) fit of the safe-success rate against the logarithm of the dial level; the 50% crossing by linear interpolation between levels; a bootstrap over episodes within each level (2,000 resamples, fixed seed) for the interval. If the fit never crosses 50% inside the tested levels, the margin is reported as "beyond the tested range", not extrapolated.
- No episode is excluded except for a simulator error, and those are counted and reported.
- Every cell is reported, including the uninteresting ones.

## Threats to validity, stated in advance
- **Simulation only.** Nothing here shows what happens on hardware.
- **Physics backend.** The scripted oracle itself loses 16–44% on the second backend for these tight fits. Model results are run on the primary backend; the oracle gap is reported beside them.
- **Force model.** The wrist sensor is simulated; its noise and rate are assumptions until compared with a real sensor.
- **One body, two tasks.** Claims are about these tasks on this arm.
- **Prompt sensitivity.** One fixed prompt set; no claim about the best achievable prompt.
- **Quantisation.** If a model is quantised to fit, that is a different model; its accuracy cost on a public task is reported.
