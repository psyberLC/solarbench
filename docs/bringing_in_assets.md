# Bringing a physical object into the benchmark

How a person or an agent takes something that exists on a solar plant (an enclosure door, an oil gauge, another connector, a grease point) and turns it into an asset and a task that can be trusted. Tool notes were checked in November 2026: **[P]** read in a primary source, **[S]** secondary only. Tools move fast; re-check before relying on one.

## The idea in one paragraph
An asset here has two halves that come from different places. **What it looks like** can come from a scan, a splat or a generated model. **How it behaves in contact** (dimensions that touch, mass, friction, joint limits, latch and insertion forces) comes only from a datasheet, a standard or a measurement, is written in `solarbench/specs` with its source, and is simulated with simple analytic shapes. Nothing a camera or a generative model produced is ever used as a physical quantity.

## Steps

### 1. Describe the object and why it matters
- Which rows of [`atlas/tasks.csv`](../atlas/tasks.csv) does it serve? If none, add the row first.
- What is the contact? Name the mechanism: hinge and quarter-turn latch, threaded cap, spring clip, push-fit.
- What does success look like as a physical fact, and what does damage look like? Find the manufacturer's or the standard's number for each (a torque, a force, an angle, a clearance).

### 2. Collect the numbers
| Quantity | Preferred source | If unavailable |
|---|---|---|
| Functional dimensions (what touches what, clearances) | Manufacturer drawing or datasheet | Calipers on a real part; record the instrument |
| Mass | Datasheet | Kitchen or luggage scale |
| Joint range, hinge and latch travel | Drawing | Protractor or ruler on a real part |
| Operating force or torque (latch, detent, insertion, breakaway) | Standard or datasheet | Force gauge or torque wrench, at least 10 repeats |
| Friction between the materials in contact | Published value for the material pair | Inclined-plane test with the real surfaces |
| Load limits that define damage | Standard or datasheet | Leave it out and say so; do not guess a limit |

Every value goes into `solarbench/specs/params.py` with its source and one status: CITED, MEASURED, DERIVED, STAND_IN or ASSUMED. Raw measurements go under `assets/measurements/` with instrument, method and date. Anything not CITED or MEASURED gets an entry in `ASSUMPTIONS.md`.

No tool found estimates latch, detent or insertion forces reliably from images or video. Measure them.

### 3. Model the physical half
- **Collision geometry is analytic primitives** (boxes, cylinders, capsules, spheres), authored from the spec values by a builder in `solarbench/assets/build.py`. The same file then simulates in Newton, MuJoCo and PhysX. Mesh decomposition tools (CoACD, V-HACD [S]) give convex pieces, not primitives; use them only to check a primitive fit by eye.
- **Joints** (hinge, slider, screw) are authored directly in the builder, following the layout Isaac robot assets use: sibling rigid bodies and, for a fixed-base mechanism, a world-fixed root joint. PhysX rejects nested rigid bodies.
- **Mass and inertia** come from the datasheet mass and the primitive geometry. Set mass before inertia is derived.
- **Mechanism forces** (a latch that snaps, a bolt that tightens, a detent) are modelled explicitly as a small, unit-tested function of joint state, like [`solarbench/tasks/latch.py`](../solarbench/tasks/latch.py) and [`bolt.py`](../solarbench/tasks/bolt.py). They are not left to emerge from mesh contact.

### 4. Make the visual half
Any of these is fine, because none of it affects physics or scores:
- **Parametric model from the same spec values.** What the existing assets use. An agent writing build123d or CadQuery code produces exact geometry if you give it measured dimensions; given only a photo it produces a look-alike [S].
- **Photogrammetry** (COLMAP, Meshroom, RealityScan [S]). The reconstruction has no absolute scale: put a ruler in frame and check one datasheet dimension afterwards.
- **Gaussian splats** (gsplat, Nerfstudio; 3DGRUT exports splats to OpenUSD as a `ParticleField` [P]). Isaac Sim reads them. Whether the kit-less renderers used here (Newton Warp, OVRTX) can draw splats is **unverified**: test it, and keep a mesh as the fallback.
- **Generated models.** Useful as a starting shape; treat every dimension as unknown until checked.

Align the visual to the collision primitives and look at them overlaid before going further.

### 5. Validate the file
```bash
git clone --depth 1 --branch v2026.08.0 https://github.com/NVIDIA/simready-foundation.git data/cache/simready-foundation
cd tools/validate && uv sync
uv run simready-validate --project-config ../../data/cache/simready-foundation/sample_content/project_config.toml \
    --profile Robotics-Prop --version 3.3.0 ../../assets/<name>/simready_usd/<name>.usda
```
The validator runs in its own environment because it conflicts with Isaac Lab's USD package. It checks that the file conforms to the specification. It does not check that a friction value is right.

### 6. Audit the physics
The checks that catch what the validator cannot (several are taken from a public audit of another benchmark, which found configured friction never reaching its engine):
1. **Read back from the engine** after load: mass, inertia, friction, joint limits and effort limits equal the spec values, on both backends.
2. **Plausibility:** density, mass and friction are possible for a real object; joint limits match the hardware.
3. **Invariance:** the outcome does not change with half the time step or a different number of parallel environments.
4. **No free energy:** a dropped or released part does not gain speed.
5. **Mechanism test:** the latch, detent or thread model reproduces the measured force or torque curve within the measurement's spread.
6. **Both backends:** the oracle result on Newton and on PhysX, with the gap reported.

### 7. Turn it into a task
Follow "A task" in [CONTRIBUTING.md](../CONTRIBUTING.md): environment, config, oracle, registration, task card, per-episode variation of the physical parameters, degenerate policies failing.

## Help for agents
Skill packs that exist for coding agents and are relevant here:

| Skill pack | Useful for | Limits |
|---|---|---|
| Isaac Lab agent skills, in the Isaac Lab repository under `skills/` [P] | Environment authoring, backend choice, preparing assets for Newton, on exactly this stack | Discovered through links inside the Isaac Lab checkout, not a global install |
| Isaac Sim bundled skills (`usd-articulation`, `urdf-mjcf-to-usd-conversion`, `physx-to-newton-conversion`, …) [P] | Articulation and conversion recipes | Most need Isaac Sim itself; this project runs without it |
| `NVIDIA/skills` catalogue (`omniverse-cad-to-simready`, `physical-ai-physics-selection`, …) [P] | CAD-to-SimReady preparation | Descriptions are thin; check what a skill does before trusting it |
| `NVIDIA/newton-skills` [P] | Pointers into Newton's documentation | Early draft |
| Build123d / CadQuery agent skills such as `earthtojake/text-to-cad` [S] | Parametric visual geometry from stated dimensions | Licences not checked |

No Hugging Face or LeRobot skill for simulation assets was found. Kit-less URDF and MJCF import works through Isaac Lab's `importers` extra [P].

A skill can do the authoring. It cannot supply a number. Rule 2 of [AGENTS.md](../AGENTS.md) applies to whatever an agent or a skill produces: every physical value has a source, or it is recorded as an assumption.

## Things that go wrong
- **A pretty asset with invented physics.** The most likely failure. The review asks for the source of every value in step 2 before looking at anything else.
- **Scale.** Scans and generated models are off by arbitrary factors.
- **Branded products.** Scanning or modelling a manufacturer's product, and using its name, may need permission. Model the part from its published dimensions and use the name only to cite the datasheet.
- **Values that never reach the engine.** Materials attached after the engine has parsed the bodies are silently ignored. Step 6.1 exists for this.
- **Tight clearances.** The two physics backends disagree most on sub-millimetre fits. Expect a gap and report it.

## Worked example
The board item `assets-enclosure` builds a combiner-box door with a quarter-turn latch by following this page, and corrects the page wherever it turned out to be wrong.
