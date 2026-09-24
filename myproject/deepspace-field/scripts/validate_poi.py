#!/usr/bin/env python3
"""Validate DeepSpace Field POI metadata files.

This is a placeholder until POI YAML files are split out of the TypeScript
scaffold. It keeps the data quality contract visible from day one.
"""

from __future__ import annotations

from pathlib import Path


REQUIRED_FIELDS = {
    "id",
    "name",
    "source",
    "source_url",
    "observation_facts",
    "artistic_enhancements",
}


def main() -> None:
    poi_dir = Path("content/poi")
    if not poi_dir.exists():
        print("content/poi does not exist yet; scaffold validation passed.")
        return
    missing = []
    for path in poi_dir.glob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        for field in REQUIRED_FIELDS:
            if f"{field}:" not in text:
                missing.append(f"{path}: missing {field}")
    if missing:
        raise SystemExit("\n".join(missing))
    print("POI metadata validation passed.")


if __name__ == "__main__":
    main()
