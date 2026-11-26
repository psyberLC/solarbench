"""Generate all SolarBench USD assets from the parameter specs.

Usage: .venv/bin/python scripts/build_assets.py [--out assets]
"""

import argparse
from pathlib import Path

from solarbench.assets import build
from solarbench.assets.thumbnail import render_thumbnail
from solarbench.specs import MODULES, TABLE_DEFAULT

parser = argparse.ArgumentParser()
parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "assets")
args = parser.parse_args()

paths = [build.build_pv_module(spec, args.out) for spec in MODULES.values()]
paths.append(build.build_table(TABLE_DEFAULT, MODULES["longi_lr7_72hvd"], args.out))
paths.append(build.build_mc4_male(args.out))
paths.append(build.build_mc4_female(args.out))
paths.append(build.build_end_clamp(MODULES["longi_lr7_72hvd"], args.out))
paths.append(build.build_husky_a300(args.out))
for kw in ({}, {"name": "low_mount_site_row_end", "row_end": True}):
    scenery = build.build_site_scenery(TABLE_DEFAULT, MODULES["longi_lr7_72hvd"], args.out, **kw)
    print(scenery.relative_to(args.out.parent))
for p in paths:
    render_thumbnail(p)
    print(p.relative_to(args.out.parent))
