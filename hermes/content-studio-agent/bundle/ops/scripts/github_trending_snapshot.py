#!/usr/bin/env python3
"""Fetch a lightweight snapshot of github.com/trending for Hermes cron jobs.

Stdout is injected into the agent prompt when used with:
  hermes cron create --script scripts/github_trending_snapshot.py ...

Install: cp to ~/.hermes/profiles/github/scripts/
"""

from __future__ import annotations

import re
import sys
import urllib.request

URL = "https://github.com/trending"
USER_AGENT = "hermes-dev-github-trending/1.0"


def main() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except OSError as exc:
        print(f"ERROR: failed to fetch {URL}: {exc}", file=sys.stderr)
        return 1

    # Minimal parse: repo links like /owner/repo
    repos = []
    seen: set[str] = set()
    for match in re.finditer(r'href="/([^/]+/[^/]+)"[^>]*data-hydro-click', html):
        slug = match.group(1)
        if slug in seen or slug.count("/") != 1:
            continue
        seen.add(slug)
        repos.append(slug)
        if len(repos) >= 25:
            break

    if not repos:
        for match in re.finditer(r'href="/([^/]+/[^/]+)"', html):
            slug = match.group(1)
            if slug in seen or "." in slug.split("/")[-1]:
                continue
            seen.add(slug)
            repos.append(slug)
            if len(repos) >= 25:
                break

    print(f"# GitHub Trending snapshot\nSource: {URL}\n")
    if not repos:
        print("_No repositories parsed; agent should use web search as fallback._")
        return 0

    for i, slug in enumerate(repos, start=1):
        print(f"{i}. https://github.com/{slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
