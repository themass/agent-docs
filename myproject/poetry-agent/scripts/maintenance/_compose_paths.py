"""Read `docker compose config --format json` on stdin and check that every path it refers to exists.

Used by check-layout.sh. Static only: nothing is built or started.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    cfg = json.load(sys.stdin)
    problems: list[str] = []
    for name, svc in cfg.get("services", {}).items():
        build = svc.get("build")
        if build:
            ctx = Path(build["context"])
            if not ctx.is_dir():
                problems.append(f"{name}: build context {ctx} missing")
            else:
                dockerfile = ctx / build.get("dockerfile", "Dockerfile")
                if not dockerfile.is_file():
                    problems.append(f"{name}: dockerfile {dockerfile} missing")
        for volume in svc.get("volumes", []):
            if volume.get("type") == "bind" and not Path(volume["source"]).exists():
                problems.append(f"{name}: bind mount source {volume['source']} missing")
    for problem in problems:
        print(f"FAIL  {problem}")
    if not problems:
        print("ok    compose build contexts, dockerfiles and bind mounts exist")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
