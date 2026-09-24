#!/usr/bin/env python3
"""Fetch Hubble/JWST observation metadata from MAST.

This scaffold intentionally writes metadata only. Downloading large FITS files
should be an explicit follow-up step after target review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="Object name or coordinates.")
    parser.add_argument("--out", default="data-raw/mast", help="Output directory.")
    args = parser.parse_args()

    out_dir = Path(args.out) / args.target.lower().replace(" ", "-")
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "target": args.target,
        "status": "placeholder",
        "next": [
            "Install astroquery: pip install astroquery astropy",
            "Use astroquery.mast.Observations.query_object/query_region",
            "Filter HST/JWST science/preview products",
            "Write observation IDs, filters, product URLs and source licenses",
        ],
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {out_dir / 'metadata.json'}")


if __name__ == "__main__":
    main()
