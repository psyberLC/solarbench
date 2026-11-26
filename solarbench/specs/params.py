"""Physical parameters for SolarBench, with provenance.

Every number used to build assets or score tasks lives here as a :class:`P` carrying its unit,
a source key (resolved in ``docs/sources.md``) and a status. Nothing downstream
should hard-code a physical constant: import it from this module so that ASSUMPTIONS.md and the
code cannot drift apart.

Status values:
    CITED      value read from a primary source (datasheet, manual, standard)
    MEASURED   value measured on a real part; raw readings under assets/measurements/
    DERIVED    computed from CITED inputs (formula given in ``note``)
    STAND_IN   a cited value from a *different* product used as a proxy
    ASSUMED    engineering judgement, no source; must appear in ASSUMPTIONS.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import Literal

Status = Literal["CITED", "MEASURED", "DERIVED", "STAND_IN", "ASSUMED"]


@dataclass(frozen=True)
class P:
    """A physical parameter with provenance."""

    value: float
    unit: str
    source: str
    status: Status = "CITED"
    note: str = ""

    def __float__(self) -> float:
        return float(self.value)


# Source keys (full URLs in docs/sources.md)
SRC_LONGI_DS = "LONGi LR7-72HVD datasheet"
SRC_LONGI_IM = "LONGi installation manual V15"
SRC_JINKO_DS = "Jinko JKM590-615N-72HL4R datasheet"
SRC_JINKO_IM = "Jinko UL-61730 installation manual Ed.2/2026"
SRC_TRINA_IM = "Trina Vertex user manual PP7"
SRC_STAUBLI = "Staubli MC4-Evo 2 catalogue"
SRC_IEC62852 = "IEC 62852 cl.5.17 via DEKRA cross-mating report"
SRC_PHOENIX = "Phoenix Contact 16 mm2 PV connector datasheet"
SRC_CLENERGY = "Clenergy SolarTerrace II-A installation guide"
SRC_ETB = "Engineering Toolbox friction coefficients"
SRC_CENEK = "Cenek (Noon 1994) roadside friction"
SRC_PANDER = "Pander & Jaeckel 2025, PV Symposium"
SRC_IEC61215 = "IEC 61215 MQT 16 (Sinovoltaics summary)"
SRC_TS62782 = "IEC TS 62782 DML (TUV NORD)"


@dataclass(frozen=True)
class ModuleSpec:
    """A framed PV module, modelled as one rigid body (see ASSUMPTIONS P1)."""

    name: str
    cell_tech: str  # "hpbc" (back-contact, no front busbars) or "topcon"; visual only
    glass_glass: bool  # glass-glass (bifacial) vs glass-backsheet; visual only
    length: P  # long edge, m
    width: P  # short edge, m
    depth: P  # frame depth, m
    mass: P  # kg
    glass: str
    front_load_rating: P  # Pa
    rear_load_rating: P  # Pa
    clamp_zone_min: P  # clamp centre distance from short edge, m
    clamp_zone_max: P
    clamp_torque_min: P  # N*m, M8 clamp bolt
    clamp_torque_max: P
    frame_lip: P = P(0.010, "m", SRC_JINKO_IM, "DERIVED", "clamp overlap 8-12 mm across manuals; lip >= overlap")
    frame_width: P = P(0.033, "m", "none", "ASSUMED", "frame flange width; profile drawing not published")
    laminate_thickness: P = P(0.0055, "m", "none", "DERIVED", "2+2 mm glass + ~1.5 mm encapsulant/cells")
    lead_pos_length: P = P(0.400, "m", SRC_LONGI_DS)
    lead_neg_length: P = P(0.200, "m", SRC_LONGI_DS)
    lead_length_portrait: P = P(
        1.400,
        "m",
        SRC_LONGI_DS,
        "CITED",
        "+/-1400 mm lead option: needed to span ~1.13 m between portrait junction boxes",
    )
    jbox_from_top_edge: P = P(0.15, "m", "none", "ASSUMED", "junction box position not published")

    @property
    def clamp_zone_nominal(self) -> float:
        return 0.5 * (float(self.clamp_zone_min) + float(self.clamp_zone_max))

    @property
    def clamp_torque_nominal(self) -> float:
        return 0.5 * (float(self.clamp_torque_min) + float(self.clamp_torque_max))

    def box_inertia(self) -> tuple[float, float, float]:
        """Principal inertia (Ixx about long axis, Iyy about short axis, Izz normal), uniform box.

        DERIVED approximation (ASSUMPTIONS P13): the real mass is concentrated in the glass and the
        frame ring; a uniform box under-estimates Izz/Iyy by a few percent.
        """
        m, a, b, c = float(self.mass), float(self.length), float(self.width), float(self.depth)
        return (m / 12 * (b * b + c * c), m / 12 * (a * a + c * c), m / 12 * (a * a + b * b))


LONGI_LR7_72HVD = ModuleSpec(
    name="longi_lr7_72hvd",
    cell_tech="hpbc",  # LR7 = LONGi HPBC back-contact family ("H" in 72HVD); visual attribute, ASSUMPTIONS V1
    glass_glass=True,
    length=P(2.382, "m", SRC_LONGI_DS),
    width=P(1.134, "m", SRC_LONGI_DS),
    depth=P(0.030, "m", SRC_LONGI_DS),
    mass=P(33.5, "kg", SRC_LONGI_DS),
    glass="glass-glass 2.0+2.0 mm semi-tempered",
    front_load_rating=P(5400, "Pa", SRC_LONGI_DS),
    rear_load_rating=P(2400, "Pa", SRC_LONGI_DS),
    # LONGi V15 manual does not cover LR7; use Jinko/Trina intersection (476-520 mm).
    clamp_zone_min=P(0.476, "m", SRC_JINKO_IM, "STAND_IN", "Jinko A/5 for 2382 mm; intersect Trina 420-520"),
    clamp_zone_max=P(0.520, "m", SRC_TRINA_IM, "STAND_IN", "Trina upper bound, rails perpendicular"),
    clamp_torque_min=P(14.0, "N*m", SRC_LONGI_IM),
    clamp_torque_max=P(18.0, "N*m", SRC_LONGI_IM),
)

JINKO_TIGER_NEO_72HL4R = ModuleSpec(
    name="jinko_72hl4r",
    cell_tech="topcon",  # Tiger Neo = N-type TOPCon, 16 busbars
    glass_glass=False,
    length=P(2.335, "m", SRC_JINKO_DS),
    width=P(1.134, "m", SRC_JINKO_DS),
    depth=P(0.035, "m", SRC_JINKO_DS),
    mass=P(28.5, "kg", SRC_JINKO_DS),
    glass="glass-backsheet, 3.2 mm tempered",
    front_load_rating=P(5400, "Pa", SRC_JINKO_DS),
    rear_load_rating=P(2400, "Pa", SRC_JINKO_DS),
    clamp_zone_min=P(0.467, "m", SRC_JINKO_IM, "DERIVED", "A/5 with A = 2335 mm"),
    clamp_zone_max=P(0.584, "m", SRC_JINKO_IM, "DERIVED", "A/4 with A = 2335 mm"),
    clamp_torque_min=P(16.0, "N*m", SRC_JINKO_IM),
    clamp_torque_max=P(20.0, "N*m", SRC_JINKO_IM),
)

MODULES = {m.name: m for m in (LONGI_LR7_72HVD, JINKO_TIGER_NEO_72HL4R)}


@dataclass(frozen=True)
class TableSpec:
    """Fixed-tilt mounting table ("low mount"). Default is 1P portrait (ASSUMPTIONS P11)."""

    rows: int = 1  # modules up the slope (1P, 2P, ...)
    modules_per_row: int = 3
    orientation: Literal["portrait", "landscape"] = "portrait"
    tilt_deg: P = P(20.0, "deg", SRC_CLENERGY, "CITED", "Clenergy 20/30 deg; Schletter <= 25 deg")
    lower_edge_height: P = P(0.60, "m", SRC_CLENERGY, "CITED", "within Clenergy 446-691 mm clearance")
    module_gap: P = P(0.020, "m", SRC_JINKO_IM, "DERIVED", "Jinko requires >= 10 mm; 20 mm = mid-clamp body")
    station_spacing: P = P(3.0, "m", SRC_CLENERGY, "CITED", "Clenergy 1.95-3.5 m by wind zone")
    purlin_height: P = P(0.100, "m", "generic C-purlin", "ASSUMED", "C100x50x20x2.0 assumed")
    purlin_width: P = P(0.050, "m", "generic C-purlin", "ASSUMED")
    post_section: P = P(0.080, "m", "generic C-post", "ASSUMED")
    steel_linear_density: P = P(
        3.77,
        "kg/m",
        "generic C-purlin",
        "DERIVED",
        "C100x50x20x2.0: 2 mm x 240 mm developed width x 7850 kg/m3; used for all members",
    )

    @property
    def tilt(self) -> float:
        return math.radians(float(self.tilt_deg))


@dataclass(frozen=True)
class MC4Spec:
    """MC4-Evo 2 compatible connector pair (ASSUMPTIONS P4, P5, P14)."""

    housing_length: P = P(0.060, "m", "none", "ASSUMED", "per-half body length; catalogue drawing not parsed")
    housing_radius: P = P(0.0095, "m", "distributor listing [S]", "DERIVED", "~19 mm body width / 2")
    sleeve_inner_radius: P = P(0.0070, "m", "none", "ASSUMED", "coupling sleeve bore")
    radial_clearance: P = P(0.0003, "m", "none", "ASSUMED", "nominal; randomized 0.15-0.5 mm")
    nose_chamfer: P = P(0.0012, "m", "none", "ASSUMED", "lead-in chamfer on the insert nose")
    insertion_travel: P = P(0.016, "m", "none", "ASSUMED")
    latch_depth: P = P(0.013, "m", "none", "ASSUMED", "depth at which snap hooks engage")
    housing_mass: P = P(0.030, "kg", "none", "ASSUMED", "per half incl. crimp contact, excl. cable")
    insertion_force: P = P(45.0, "N", SRC_PHOENIX, "STAND_IN", "Phoenix 45 +/- 10 N; no MC4 value published")
    insertion_force_tol: P = P(10.0, "N", SRC_PHOENIX, "STAND_IN")
    locked_withdrawal_force: P = P(250.0, "N", SRC_PHOENIX, "STAND_IN", "Phoenix 250 +/- 50 N locked")
    min_locked_retention: P = P(80.0, "N", SRC_IEC62852, "CITED", ">= 80 N at 10 N/s without disengaging")
    unlocked_withdrawal_force: P = P(15.0, "N", "none", "ASSUMED", "residual seal friction once unlatched")
    cable_od: P = P(0.0055, "m", SRC_STAUBLI, "CITED", "4 mm2 cable in 4.7-6.4 mm range")
    cable_linear_density: P = P(0.065, "kg/m", "none", "ASSUMED", "4 mm2 Cu + XLPE jacket")
    cable_stub_length: P = P(0.050, "m", "none", "ASSUMED", "rigid first segment of the lead behind the housing")
    lead_free_tail: P = P(0.50, "m", "none", "ASSUMED",
                          "lead cable-tied along the purlin; free tail from the last tie to the housing rear")
    cable_min_bend_radius: P = P(0.043, "m", SRC_LONGI_IM)
    max_cable_pull: P = P(60.0, "N", SRC_JINKO_IM, "CITED", "Jinko caps cable-to-connector force at 60 N")


@dataclass(frozen=True)
class FrictionSpec:
    rubber_on_glass_or_al: P = P(0.5, "-", "Schmalz [S]", "CITED")
    al_on_steel_static: P = P(0.61, "-", SRC_ETB, "STAND_IN", "Al on mild steel; galvanized not found")
    al_on_steel_dynamic: P = P(0.47, "-", SRC_ETB, "STAND_IN")
    plastic_on_plastic: P = P(0.35, "-", "none", "ASSUMED", "PPE/PC housings")
    ground_gravel: P = P(0.35, "-", SRC_CENEK, "CITED", "locked-wheel tyre value")
    ground_wet_grass: P = P(0.20, "-", SRC_CENEK, "CITED")


@dataclass(frozen=True)
class DamageSpec:
    """Damage-proxy thresholds (ASSUMPTIONS P2/P3)."""

    warn_pressure: P = P(1000.0, "Pa", SRC_TS62782, "DERIVED", "DML test amplitude")
    damage_pressure: P = P(2400.0, "Pa", SRC_IEC61215, "DERIVED", "MQT16 minimum test load")
    damage_impact_energy: P = P(2.0, "J", SRC_LONGI_DS, "DERIVED", "25 mm hail at 23 m/s")
    glass_weibull_scale: P = P(154.4e6, "Pa", SRC_PANDER)
    glass_weibull_modulus: P = P(10.0, "-", SRC_PANDER)
    max_connector_axial_force: P = P(300.0, "N", SRC_PHOENIX, "DERIVED", "locked withdrawal upper bound")


TABLE_DEFAULT = TableSpec()
MC4 = MC4Spec()
FRICTION = FrictionSpec()
DAMAGE = DamageSpec()


def iter_params(obj, prefix: str = ""):
    """Yield (dotted_name, P) for every parameter in a spec dataclass."""
    for f in fields(obj):
        v = getattr(obj, f.name)
        if isinstance(v, P):
            yield f"{prefix}{f.name}", v


@dataclass(frozen=True)
class BoltSpec:
    """M8 clamp bolt (K2-style mid/end clamp, DIN 933 hex head 13 mm AF) and its torque-angle model (ASSUMPTIONS P7)."""

    across_flats: P = P(0.013, "m", "DIN 933 M8 / K2 clamp sheet", "CITED")
    head_height: P = P(0.0053, "m", "DIN 933 M8", "CITED")
    nominal_diameter: P = P(0.008, "m", "M8", "CITED")
    pitch: P = P(0.00125, "m", "ISO 261 M8 coarse", "CITED")
    nut_factor: P = P(0.20, "-", "Shigley, dry steel", "CITED", "T = K F d")
    running_torque: P = P(0.8, "N*m", "none", "ASSUMED", "prevailing torque before snug (thread + washer friction)")
    snug_to_spec_angle: P = P(0.52, "rad", "none", "ASSUMED", "~30 deg from snug to 16 N*m (clamp stack stiffness)")
    breakaway_ratio: P = P(0.9, "-", "none", "ASSUMED", "breakaway / installation torque")
    head_mass: P = P(0.03, "kg", "none", "ASSUMED", "bolt + washer")


BOLT = BoltSpec()
