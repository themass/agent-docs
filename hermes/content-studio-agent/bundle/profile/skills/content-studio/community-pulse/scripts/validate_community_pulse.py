#!/usr/bin/env python3
"""Validate that a community pulse covers the daily report Top 3 repos."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_PATTERN = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)")


def _repos(path: Path) -> list[str]:
    found: list[str] = []
    for match in _REPO_PATTERN.finditer(path.read_text(encoding="utf-8", errors="replace")):
        repo = match.group(1).rstrip(").,")
        if repo not in found:
            found.append(repo)
    return found


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: validate_community_pulse.py <daily_report> <community_pulse>", file=sys.stderr)
        return 2

    daily = Path(sys.argv[1])
    social = Path(sys.argv[2])
    if not daily.is_file() or not social.is_file() or social.stat().st_size == 0:
        return 1

    expected = _repos(daily)[:3]
    actual = _repos(social)
    if len(expected) < 3:
        print("日报 Top 3 仓库解析失败", file=sys.stderr)
        return 1

    missing = [repo for repo in expected if repo not in actual]
    if missing:
        print("社区简报不是基于当日日报 Top 3，缺失: " + ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
