"""Offline eval runner. Reads a JSONL case file, drives TurnService, prints per-category results.

Default is the SCRIPT path: no network, no model, deterministic. ``--live`` additionally allows the
configured gateway (rewording is then reviewed by the same rules); it still never sends case text anywhere
except as the facts the service itself builds. The runner stores nothing and writes no learner data.

    python -m student_agent.evalrun [--cases PATH] [--live] [--verbose]

Exit code 0 only if every case passed. Fabrication (a ``must_not_include`` hit) is counted separately:
one is a regression by the project's own definition. These cases are a starting set, not proof of
general reliability.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections import defaultdict
from pathlib import Path

from .config import AGENT_ROOT, Settings
from .models import TurnRequest, TurnResponse
from .service import Meta, TurnService

DEFAULT_CASES = AGENT_ROOT / "data" / "eval" / "chun-wang.cases.jsonl"
BUNDLE_HASH = "60279d333becba38e65414e58d433ee58235acb08841277ddf7d62a598f91d11"
WORK_ID = "work-chun-wang"


def load_cases(path: Path) -> list[dict]:
    cases = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                cases.append(json.loads(line))
            except ValueError as exc:
                raise SystemExit(f"{path}:{n}: invalid JSON") from exc
    return cases


def check(case: dict, resp: TurnResponse, meta: Meta) -> tuple[list[str], list[str]]:
    """Return (failures, fabrications)."""
    exp = case.get("expect", {})
    say = resp.say
    fails: list[str] = []
    fabs: list[str] = []
    if "outcome" in exp and meta.outcome != exp["outcome"]:
        fails.append(f"outcome {meta.outcome} != {exp['outcome']}")
    if "role" in exp and resp.role != exp["role"]:
        fails.append(f"role {resp.role} != {exp['role']}")
    if "badge" in exp and resp.badge != exp["badge"]:
        fails.append(f"badge {resp.badge} != {exp['badge']}")
    any_of = exp.get("must_include_any")
    if any_of and not any(s in say for s in any_of):
        fails.append("none of must_include_any present")
    for s in exp.get("must_not_include", []):
        if s in say:
            fabs.append(f"forbidden text present: {s}")
    basis_any = exp.get("basis_any")
    if basis_any and not any(b.id in basis_any for b in resp.basis):
        fails.append("basis_any not satisfied")
    ev = resp.evaluation
    if "covered_exact" in exp and sorted(ev.covered if ev else []) != sorted(exp["covered_exact"]):
        fails.append("covered differs")
    if "missing_exact" in exp and sorted(ev.missing if ev else []) != sorted(exp["missing_exact"]):
        fails.append("missing differs")
    for p in exp.get("missing_includes", []):
        if not ev or p not in ev.missing:
            fails.append(f"missing lacks {p}")
    return fails, fabs


def run(cases: list[dict], settings: Settings) -> dict:
    service = TurnService(settings)
    summary: dict[str, dict] = defaultdict(lambda: {"total": 0, "passed": 0, "failed": []})
    fabrications: list[str] = []
    for i, case in enumerate(cases):
        req = TurnRequest(bundle_hash=BUNDLE_HASH, work_id=WORK_ID,
                          step=case["step"], action=case["action"], args=case.get("args", {}))
        resp, meta = service.handle_detailed(req, bucket=f"eval-{i}")  # one bucket per case: no rate limit effects
        fails, fabs = check(case, resp, meta)
        row = summary[case.get("category", "?")]
        row["total"] += 1
        if fails or fabs:
            row["failed"].append({"id": case["id"], "why": fails + fabs})
        else:
            row["passed"] += 1
        fabrications += [f"{case['id']}: {f}" for f in fabs]
    return {"categories": dict(summary), "fabrications": fabrications}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    ap.add_argument("--live", action="store_true", help="allow the configured gateway (default: script path only)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    base = Settings.from_env() if args.live else Settings()
    settings = dataclasses.replace(base, source="fixture", mode_override="" if args.live else "script")
    result = run(load_cases(args.cases), settings)
    total = passed = 0
    for cat, row in sorted(result["categories"].items()):
        total += row["total"]
        passed += row["passed"]
        print(f"{cat:10s} {row['passed']}/{row['total']}")
        if args.verbose or row["failed"]:
            for f in row["failed"]:
                print(f"   FAIL {f['id']}: {'; '.join(f['why'])}")
    print(f"total      {passed}/{total}   fabrications: {len(result['fabrications'])}")
    return 0 if passed == total and not result["fabrications"] else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
