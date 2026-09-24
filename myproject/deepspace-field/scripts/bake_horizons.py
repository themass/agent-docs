#!/usr/bin/env python3
"""Bake NASA Horizons/SPICE ephemeris into frontend JSON.

The MVP currently uses static orbital parameters in TypeScript. This script is
the planned replacement path for accurate time-sampled positions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_BODIES = [
    "sun",
    "mercury",
    "venus",
    "earth",
    "moon",
    "mars",
    "jupiter",
    "saturn",
    "uranus",
    "neptune",
    "pluto",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-date", default="2026-01-01")
    parser.add_argument("--to-date", default="2030-01-01")
    parser.add_argument("--out", default="public/catalogs/solar-system-ephemeris.json")
    args = parser.parse_args()

    payload = {
        "source": "NASA/JPL Horizons or SPICE planned",
        "from": args.from_date,
        "to": args.to_date,
        "status": "placeholder",
        "bodies": DEFAULT_BODIES,
        "next": [
            "Use astroquery.jplhorizons or spiceypy",
            "Sample heliocentric positions per day/hour",
            "Write coordinates in AU with source metadata",
        ],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
