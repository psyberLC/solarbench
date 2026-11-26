# Sources

Where the numbers come from: the source behind each key used in [`solarbench/specs`](../solarbench/specs), with measurements and platform notes. Retrieved 2026-10-26 unless a line says otherwise.

- **UNVERIFIED** means no primary source was found.
- **[S]** means the value was read from a search snippet or summary, not the full document.
- **DERIVED** means we computed it from cited inputs.

## A. Measurements on the reference workstation

**Machine:**
- NVIDIA RTX 2070, 8 GB, sm_75, driver 580.178.04, CUDA 13.0
- Ubuntu 24.04, 16 cores, 125 GB RAM
- The desktop uses about 0.6–1.0 GB of VRAM at idle.

**Software:**
- Isaac Lab v3.0.0 (commit `e3f7d9f`), installed with `uv sync`, kit-less. The `.venv` is 8.1 GB.
- torch 2.11.0+cu130, Newton 1.6.1, Warp 1.17.0.
- Standalone check: Newton 1.7.0 with Warp 1.18.0.

Reproduce the training rows with `scripts/dev/vram_probe.sh`. "Peak GPU mem" is the whole-GPU figure from `nvidia-smi`, including roughly 0.6 GB idle.

| Job | Envs | Peak GPU mem | Throughput |
|---|---|---|---|
| `Isaac-Velocity-Flat-G1`, newton_mjwarp, RSL-RL PPO | 512 | 0.98 GB | about 19k env-steps/s |
| same | 4096 | 1.97 GB | about 41k env-steps/s |
| `Isaac-Velocity-Rough-G1` | 1024 | 1.81 GB | about 22k env-steps/s |
| `IsaacContrib-Factory-Franka` (Newton peg-insert preset) | 64 | **5.59 GB** | about 440 env-steps/s |
| Newton 1.7 `nut_bolt_sdf` / `nut_bolt_hydro` example | default | 1.26 / 2.15 GB | 51 / 138 FPS |
| Newton 1.7 `contacts_rj45_plug` (connector insertion) | default | 1.19 GB | 68 FPS |
| Newton 1.7 `franka_cable_ik_pick_place` | default | 1.09 GB | 30 FPS |

**Takeaways:**
- **Locomotion and large-scale state-based RL are cheap on this card.**
- **Contact-rich insertion is the binding constraint.** The Factory preset allocates `rigid_contact_max=5e6` and `max_triangle_pairs=6e7`. Simple MC4 geometry should let us shrink those buffers a lot.

## B. Platform (Isaac Lab 3.0, Newton, assets)

### Isaac Lab v3.0.0

- **Release:** GA on 2026-10-20. https://github.com/isaac-sim/IsaacLab/releases/tag/v3.0.0
- **Stack:** Python 3.12, PyTorch 2.11/cu130, Warp 1.17, Newton 1.6.1, OvPhysX 0.6.4, OVRTX 0.5.1. Isaac Sim 6.2 is optional.
- **Requirements:** Turing (7.5) or newer and driver ≥ 580.65.06. "Headless Newton simulation does not require RTX hardware." https://isaac-sim.github.io/IsaacLab/v3.0.0/source/isaaclab/installation.html
- **Isaac Sim requirements, for contrast:** ≥ 16 GB VRAM and an RTX 4080-class GPU. https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/requirements.html
- **Backends:** `physics=newton_mjwarp | newton_kamino | ovphysx | isaacsim_physx`. https://docs.nvidia.com/isaaclab/3.0/concepts/backends-and-presets.md
  - MJWarp is the primary validated Newton solver. Kamino is only for selected tasks. VBD cables are experimental. https://docs.nvidia.com/isaaclab/3.0/concepts/newton.md
  - OvPhysX is PhysX without Kit. https://docs.nvidia.com/isaaclab/3.0/concepts/ov-phys-x.md
  - Surface (suction) grippers are PhysX/Kit only.
  - Equal friction coefficients do not give equal slip across solvers. https://docs.nvidia.com/isaaclab/3.0/concepts/solver-differences.md
- **Factory / Forge / AutoMate:** now under `contrib/factory` and PhysX-only.
  - The new `contrib/nist` `IsaacContrib-Factory-Franka` has a `newton_mjwarp` preset (peg/rod insert at 4–16 mm). We ran it locally; see section A.
  - Arena 0.3.1 lists "better Newton support for contact-rich insertion" as future work.
- **Renderers:**
  - `newton_renderer`: a Warp ray tracer, kit-less, no RT cores needed.
  - `ovrtx`: kit-less RTX, pre-release.
  - Source: https://docs.nvidia.com/isaaclab/3.0/concepts/renderers.md
- **Multi-agent:** `DirectMARLEnv` runs on Newton (Shadow-Handover and Pendulum-MARL are benchmarked there). MAPPO/IPPO come from skrl.
- **Agent skills in the repo** (`IsaacLab/skills/user`): `prepare-assets-for-newton`, `plan-manipulation-tasks`, `create-environments`, `select-backends`, `isaaclab-transferring-policies-sim-to-sim`, `domain-randomization-events`.

### LEAPP

- **What it is:** "Lightweight Export Annotations for Policy Pipelines". v0.7.2, Apache-2.0, alpha.
- **Export formats:** ONNX (default), TorchScript, and PT2.
- **Usage:** `isaaclab leapp export` and `isaaclab leapp deploy`. Direct envs are RSL-RL only.
- **Sources:** https://github.com/nvidia-isaac/leapp · https://docs.nvidia.com/isaaclab/3.0/resources/sim-2-real-deployment-of-policies-trained-in-isaac-lab/exporting-policies-with-leapp.md

### RL post-training and GR00T

- **RL post-training:** done through RLinf (`rlinf==0.2.0dev2`). It has one task, `assemble_trocar` (G1 + Dex3, PhysX + RTX). https://docs.nvidia.com/isaaclab/3.0/experimental-features/rl-post-training-for-vla-models.md
- **GR00T:** upstream is N1.7; no N2 was found. https://github.com/NVIDIA/Isaac-GR00T

### Humanoid low-level controllers

- **SONIC (GEAR-SONIC):** three G1 29-DoF checkpoints in ONNX/PyTorch. Code is Apache-2.0; weights are under the NVIDIA Open Model License. https://github.com/NVlabs/GR00T-WholeBodyControl · https://huggingface.co/nvidia/GEAR-SONIC
- **AGILE:** Isaac Lab's `IsaacContrib-PickPlace-Locomanipulation-G1-Abs` pairs the AGILE lower-body policy with a Pink-IK upper body. This is the L1 action pattern we want. It runs on the PhysX default; a Newton preset was not found.

### Cosmos

- `nvidia/Cosmos3-Nano-Sim-Transfer`, released 2026-10-20.
- About 16B parameters, BF16, Hopper/Blackwell only. License: OpenMDW-1.1.
- Source: https://huggingface.co/nvidia/Cosmos3-Nano-Sim-Transfer

### Isaac Lab-Arena

- Status: alpha, v0.3.x.
- Features: Scene/Embodiment/Task composition, subtask predicates, normalised progress, variation sweeps, and GR00T/π0.5 policy servers.
- Its installation pulls Isaac Sim 6.2.
- Sources: https://github.com/isaac-sim/IsaacLab-Arena · https://isaac-sim.github.io/IsaacLab-Arena/release/0.3.1/pages/references/release_notes.html

### SimReady

- **SimReady Central:** 2,000+ assets, ungated, with a per-asset licence (the sample we checked was CC-BY-4.0).
  - No solar, PV, MC4 or inverter assets turned up in a search of `nvidia/simready-assets` (2,576 folders).
  - Sources: https://huggingface.co/blog/nvidia/simready-central-assets-robotics-ai-factories · https://github.com/NVIDIA-Omniverse/simready-central
- **SimReady Foundation:** v2026.08.0, Apache-2.0. https://github.com/NVIDIA/simready-foundation
  - The **Robotics-Prop** profile requires FET_000, 001 and 003 (rigid-body physics). From version 3.2 it also requires FET_011 (semantics), FET_046 (Wikidata Q-code), and FET_031/033 (packaging/provenance).
  - Newton variant: `NewtonMeshCollisionAPI` or `NewtonSDFCollisionAPI`, `NewtonMassAPI`, `NewtonMaterialAPI`.
- **Validators (pip, kit-free):** `simready-validate` 2026.8.0, `omniverse-asset-validator` 1.18.0, `usd-validation-nvidia`.
- **CAD-to-SimReady skill:** https://github.com/NVIDIA/skills/tree/main/skills/omniverse-cad-to-simready. It needs Docker + NVIDIA Container Toolkit, an LLM key, and a proprietary HOOPS-based converter.

## C. Embodiments

All of these were read from the manufacturer's page or the URDF/MJCF.

| Robot | Mass / height | Per-arm payload | Reach | Hand | Asset (licence) | Isaac Lab / controllers |
|---|---|---|---|---|---|---|
| Unitree G1 / G1 EDU | 35 kg / 1.32 m | about 2 / 3 kg (varies with extension) | arm span about 0.45 m | Dex3-1, 7 DoF | unitree_ros and menagerie, **BSD-3** | Velocity-G1 (Newton), PickPlace/Locomanip-G1; SONIC, unitree_rl_lab |
| Unitree H2 | 70 kg / 1.82 m | **7 kg rated, 15 kg peak** | 0.69 m | dexterous options (EDU) | unitree_ros `H2.urdf`, **BSD-3** | none; no public controller found |
| Unitree H1-2 | 70 kg / 1.78 m | 7 kg rated, 21 kg peak | 0.685 m | Dex5-1 | BSD-3, but the URDF arm limits are stale (40/18 N·m) | unitree_rl_gym |
| Agility Digit | 45–65 kg | 16–18 kg total | n/p | claw | proprietary Isaac Sim USD only | Contrib Digit tasks |
| Fourier GR-1 / 2 / 3 | 55–71 kg | about 3 kg | — | 6–12 DoF | **GPL-3.0** | GR1T2 PickPlace |
| Agile ONE SN | 40 kg / 1.40 m | 3 kg | — | WUJI 20 DoF | no public asset | GR00T N1.7 reference platform |
| Asimov 1 | 35 kg / 1.2 m | 5 kg rated (claimed) | — | none | CERN-OHL-S / GPL-2.0 | — |
| Apptronik Apollo | 72.5 kg | 25 kg total | — | — | menagerie, Apache-2.0 | — |
| Husky A300 + UR10e / **UR16e** / UR20 | base about 80 kg; 50 kg all-terrain payload | 12.5 / **16** / 20 kg (tool included) | 1.30 / 0.90 / 1.75 m | Robotiq 2F-85: 20–235 N, 5 kg | clearpath + UR description, **BSD-3** | Isaac Lab UR10e Deploy-Reach / GearAssembly |
| FR3 (or Mobile FR3 Duo) | — | 3 kg | 0.855 m | Franka Hand | menagerie Apache-2.0; ±87/±12 N·m matches the datasheet | Factory/Forge peg/nut |
| Spot Arm | 39.7 kg | 5 kg continuous at 0.5 m, 11 kg max | 0.984 m | 130 N clamp | menagerie arm effort ±1000 N·m (unrealistic) | Spot velocity |

**Torque-limit audit:**
- Isaac Lab's `G1_CFG` and `H1_CFG` set arm effort to 300 N·m. The URDF gives G1 25 N·m, and H1 40/18 N·m.
- `GR1T2_CFG` sets arm effort to infinity.
- The G1 knee is 139 N·m in the URDF, against 90 (G1) or 120 (EDU) N·m published.
- H2 shoulder pitch is 130 N·m in the URDF, against 120 N·m published.
- **Decision:** SolarBench ships its own actuator configs and documents every deviation.

**Embodiment sources:**
- Unitree: https://www.unitree.com/g1/ · https://www.unitree.com/H2/ · https://www.unitree.com/h1/ · https://github.com/unitreerobotics/unitree_ros
- MuJoCo Menagerie: https://github.com/google-deepmind/mujoco_menagerie
- Universal Robots: https://www.universal-robots.com/products/ur16e/ · https://github.com/UniversalRobots/Universal_Robots_ROS2_Description
- Clearpath: https://clearpathrobotics.com/husky-spec-comparison/
- Franka: https://franka.de/hubfs/Datasheet%20Franka%20Research%203_R02212_1.3_EN.pdf
- Robotiq: https://robotiq.com/hubfs/Product-sheets/Adaptive%20Grippers/2F_Adaptive_Grippers_ProductSheet_KOR.pdf
- Boston Dynamics: https://bostondynamics.com/wp-content/uploads/2020/10/spot-arm.pdf

**Field solar robots** (all are new-install robots; none does O&M or MC4 connectors):

| Robot | How it works | Sources |
|---|---|---|
| AES Maximo | suction cups on an industrial arm; a second arm tightens clamps | https://www.aes.com/maximo |
| Sarcos O-AMPP | vacuum lift on a Guardian XM arm | https://www.constructiondive.com/news/mortenson-pilots-sarcos-robots-solar-installation-project/646830/ |
| Cosmic Robotics | KUKA KR IONTEC on a UGV; needs 36 kg payload at full extension | https://www.kuka.com/en-us/industries/solutions-database/2025/12/automating-solar-panel-installation |
| Rosendin + ULC | 9 suction cups | https://www.enr.com/articles/60249-rosendin-electric-deploys-custom-robots-to-install-solar-panels |

## D. Solar hardware

### Modules

| Model | Size (mm) | Mass | Glass | Loads (front/rear) | Source |
|---|---|---|---|---|---|
| **LONGi LR7-72HVD (reference)** | 2382×1134×30 | **33.5 kg** | 2.0+2.0 mm semi-tempered | +5400 / −2400 Pa | https://aurinkosahkotukku.fi/wp-content/uploads/2025/11/LONGI-LR7-72HVD-635-645M-.pdf |
| Trina Vertex N NEG19RC.20 | 2384×1134×30 | 33.1 kg | 2+2 HS | 5400 / 2400 | https://storage.mtender.gov.md/get/b889dd5a-dd46-464f-a259-985b08f43890-1738048633389 |
| Jinko Tiger Neo 72HL4R (glass-backsheet) | 2335×1134×35 | 28.5 kg | 3.2 mm tempered | 5400 / 2400 | https://solarproof.com.au/datasheets/panel_datasheet_JKM590-615N-72HL4R-V-F2C1-EN-AU-CEC.pdf |
| Canadian Solar CS7N-TB-AG | 2384×1303×33 | 37.8 kg | 2+2 HS | 5400 / 2400 | https://solarproof.com.au/datasheets/panel_datasheet_CS-Datasheet-TOPBiHiKu7_CS7N-TB-AG_v1.9_EN.pdf |
| First Solar Series 7 TR1 | 2300×1216, frameless | 38.5–39.7 kg | HS/HS | 2400 | https://firstsolar.com/-/media/First-Solar/Technical-Documents/Series-7/Series-7-TR1-Datasheet.ashx |

- **Industry standard size:** 2382×1134 mm, agreed by nine manufacturers in 2023. https://www.trinasolar.com/us/resources/newsroom/TrinaSolar-takes-lead-standardization-initiative-unify-module-dimensions/
- **Clamp zones:**
  - Jinko: L = 476–596 mm from the short edge; M8 at 16–20 N·m; frame overlap ≥ 10 mm. https://jinkosolar.us/wp-content/uploads/2025/02/202602-UL-61730-Installation-Manual-G6-G7-1.pdf
  - Trina: 420–520 mm; M8 at 10–14 N·m. https://www-cdn.trinasolar.com/wwwstorage/sites/5/UM-M-0002-PP7-Trina-Solar-Vertex-Series-User-Manual_EN.pdf
  - LONGi: overlap 8–11 mm; M8 at 14–18 N·m. https://cdn.shopify.com/s/files/1/0510/6148/9855/files/LONGI_IM.pdf
- **Handling rules:**
  - Never lift a module by its junction box or cables.
  - Carry with two or more people (Trina).
  - Do not twist the frame (Jinko).
  - **No manual gives numeric limits for bending, twist, drop or point force.** That is why the damage thresholds in the next section are proxies.

### Damage proxies

| Proxy | Value | Source |
|---|---|---|
| IEC 61215 MQT 16 static load | minimum 2400 Pa, safety factor γm ≥ 1.5 | https://sinovoltaics.com/learning-center/testing/iec-61215-mqt-16-static-mechanical-load-test-for-solar-modules/ |
| Dynamic mechanical load (TS 62782) | ±1000 Pa × 1000 cycles | https://www.tuv-nord.com/cn/en/renewable-energy/tuev-nord-testing-suzhou-co-ltd/photovoltaic-pv-modules-cyclic-dynamic-mechanical-load-testing/ |
| Hail test | 25 mm ice ball at 23 m/s, about 2 J (DERIVED) | LONGi datasheet |
| Glass strength (2 mm) | Weibull 154.4 MPa, m = 10. In glass-glass modules, cell cracking under uniform load is "very unlikely"; failures are glass fracture at the clamps and frame yield | https://www.tib-op.org/ojs/index.php/pv-symposium/article/view/2649 |
| Point-force / drop / twist thresholds | **UNVERIFIED** (the ISFH study and IEC 62759-1 are paywalled) | — |

### Table and clamps

**Table geometry:**
- Tilt 20–30°, panel clearance 446–691 mm, posts 0.86–1.4 m (Clenergy SolarTerrace II-A). https://rheem.co.nz/assets/technical_documents/Solar/Racking/147bd3b9c3/11PV-ezRack-SolarTerrace-II-A-Installation-Guide-05152020.pdf
- Schletter FS Duo/Uno: 2P / 3P / 4L / 6L. https://www.schletter-group.com/mounting-systems/fixed-tilt-systems/
- TrinaTracker FixOrigin: clearance ≤ 1.2 m, tilt ≤ 30°. https://www.environdec.com/library/epd24995

**Reference table (DERIVED):** one module in portrait per table (1P), 20° tilt, lower edge at 0.60 m. Row pitch 6.0 m, from the 2.38 m slope length and a ground-coverage ratio of 0.40.

**Clamp hardware:**
- Clenergy: M8 socket head, 6 mm hex, 18–20 N·m.
- K2: M8, 13 mm socket, about 14–16 N·m [S].
- Schletter Rapid16: TX40, 12–14 N·m [S].

### MC4 connectors

- **Stäubli MC4-Evo 2:** 4 mm pin; cable OD 4.7–8.4 mm; 2.5–6 mm² cable; 1500 V; IP68 when mated; "do not disconnect under load". https://www.staubli.com/content/dam/spot/SOL-MC4-Evo-2-11014101-en.pdf
- **Locked retention:** at least 80 N pull (IEC 62852 §5.17). https://hollandsolar.nl/uploads/dekra-crossmating-met-mc4-definitief.pdf
- **Mating force:** UNVERIFIED. Stand-in: a Phoenix PV connector at 45 ± 10 N insertion and 250 ± 50 N locked disconnect. https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/3150/1284634.pdf
- **Body size:** about 71×19×19 mm [S].
- **Module leads:** 4 mm² cable, +400/−200 mm (LONGi).

### Friction

| Contact pair | μ | Source |
|---|---|---|
| Rubber pad on glass / aluminium | about 0.5 [S] | Schmalz |
| Aluminium on mild steel | 0.61 static / 0.47 kinetic | https://www.engineeringtoolbox.com/friction-coefficients-d_778.html |
| Tyre on gravel | 0.35 [S] | Cenek (citing Noon 1994) |
| Tyre on wet grass | 0.20 [S] | Cenek (citing Noon 1994) |

### O&M practice

- Isolate the string before touching connectors: open the combiner fuses, apply LOTO, verify the circuit is dead. https://www.fluke.com/en-us/learn/blog/renewable-energy/solar-panel-safety-lockout-tagout
- Crew of at least two people.
- Time per swap: UNVERIFIED.

Models and benchmarks in the field are tracked in [field.md](field.md).
