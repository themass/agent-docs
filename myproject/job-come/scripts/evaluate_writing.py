#!/usr/bin/env python3
"""Writing-semantics acceptance: does the pipeline keep its promises with a real model?

Why this layer exists
---------------------
JC's acceptance scripts cover three layers and leave one gap:

    evaluate_documents.py    extraction quality          offline, no model
    verify_resume_steps.py   frontend runtime            real Chromium, mocked API
    e2e_smoke.sh             HTTP contracts              live API, asserts shape only
    -> this script           writing semantics           live model, asserts behaviour

Everything the product promises about *writing* is enforced by a prompt and judged by a
model. Three claims in particular have never been measured:

1. Changing `framing_emphases` actually changes how the work is told, and does not drop
   content on the way.
2. The honesty invariant holds under pressure: angle `ownership` must not turn 参与 into
   主导, and no angle may introduce a number.
3. `resume_coverage._MATCH_THRESHOLD = 0.42` does not cry wolf on normal output.

Assertion strategy: differential, not literal
---------------------------------------------
Model output is not reproducible, so asserting on phrasing would make this script fail on
a retry or a model swap and teach everyone to ignore it. Instead it asserts the two
properties that must hold for *any* correct output:

- **variance** — two different angle selections must produce materially different text.
  If they do not, the angle control is decorative and the product is lying to the user.
- **invariance** — no run, under any angle, may add a fact the profile does not support
  or upgrade an ownership verb. This is delegated to `writing_invariants`, which is
  deterministic and unit-tested, so this script stays a harness rather than a second
  implementation of the rules.

Threshold calibration is **reported, not asserted**. The right response to "coverage
flagged 3 items on real output" is a human reading those three strings, not a red build.

Privacy
-------
The sample is somebody's real resume. The JSON report stores measurements, findings, and
short excerpts needed to explain a finding — never a full draft and never contact
details. Pass `--verbose` to see excerpts on stdout during a local run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lib.bootstrap import ensure_project_env

PROJECT_ROOT = ensure_project_env()
SERVER_ROOT = PROJECT_ROOT / "backend" / "server"

from jc.config import settings  # noqa: E402
from jc.db.session import engine as _db_engine  # noqa: E402
from jc.domain.role_families import resolve_role_family  # noqa: E402
from jc.schemas.profile_payload import ProfilePayload  # noqa: E402
from jc.services.framing_presets import MAX_EMPHASES, resolve_emphases  # noqa: E402
from jc.services.profile_ingest_service import ProfileIngestService  # noqa: E402
from jc.services.resume_coverage import audit_coverage  # noqa: E402
from jc.services.resume_diagnostics import diagnose  # noqa: E402
from jc.services.resume_elevator import ResumeElevator  # noqa: E402
from jc.services.resume_reviewer import ResumeReviewer  # noqa: E402
from jc.services.text_overlap import containment  # noqa: E402
from jc.services.writing_invariants import audit_additions  # noqa: E402

#: Angle pairs to compare. Chosen to make the differential meaningful rather than to
#: cover the catalogue: `ownership` vs `outcome` is the pair most likely to tempt a model
#: into upgrading a verb, and `scope` vs `depth` tells apart "how big" from "how hard".
_ANGLE_ARMS: tuple[tuple[str, ...], ...] = (
    ("ownership", "collaboration"),
    ("outcome", "scope"),
    ("depth", "jd_fit"),
)

#: Two drafts whose bullets overlap above this are telling the same story in the same
#: words, so the angle selection had no effect the user could see. Set from the other
#: side of the calibrated band in `resume_coverage`: a genuine rewrite of the same source
#: retains 0.55-0.9, so two *differently angled* drafts sitting above 0.9 means the angle
#: changed nothing, not merely that both are faithful.
_SAMENESS_CEILING = 0.90


@dataclass
class ArmResult:
    """One generation run under one angle selection."""

    emphases: list[str]
    bullets: list[str] = field(default_factory=list)
    sections: dict[str, Any] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    invariants: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.bullets)


def _bullets(sections: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("experience_blocks", "project_blocks"):
        for block in sections.get(key) or []:
            if isinstance(block, dict):
                out += [b for b in (block.get("bullets") or []) if isinstance(b, str)]
    return out


def _pairwise_sameness(left: list[str], right: list[str]) -> float:
    """How much of `left`'s wording survives in `right`, averaged over bullets.

    Positional rather than best-match on purpose: angles are allowed to re-order, and a
    best-match comparison would call a re-ordered draft identical. What is measured is
    whether the document a user reads top-to-bottom actually reads differently.
    """
    if not left or not right:
        return 0.0
    joined = "\n".join(right)
    return statistics.fmean(containment(b, joined) for b in left)


#: Participation verbs the planted bullet may be built from, longest first so a
#: compound opener is matched before its prefix.
_PLANTABLE_WEAK_VERBS = ("参与", "协助", "配合")


def inflate_ownership(line: str) -> str:
    """Rewrite one participation verb in `line` into an ownership claim.

    Exported and kept pure because it defines what "a known-bad bullet" means for the
    reviewer probe. Only the verb changes: if anything else about the sentence differed,
    a reviewer failure would no longer isolate the ownership rule.
    """
    text = str(line).strip()
    for weak in _PLANTABLE_WEAK_VERBS:
        if text.startswith(weak):
            return "主导" + text[len(weak) :]
    for weak in _PLANTABLE_WEAK_VERBS:
        if weak in text:
            return text.replace(weak, "主导", 1)
    return "主导" + text


async def _load_profile(sample: Path, *, verbose: bool) -> ProfilePayload:
    """Ingest the sample exactly as the product would, including the LLM structurer."""
    service = ProfileIngestService()
    result = await service.parse(
        file_name=sample.name,
        content_type=None,
        raw_bytes=sample.read_bytes(),
    )
    if result.is_degraded:
        raise SystemExit(
            f"FAIL: ingest degraded to `{result.mode}` — the writing evaluation needs a "
            "real structured profile. Check JC_LLM_* credentials and gateway reachability."
        )
    if verbose:
        print(
            f"  ingest mode={result.mode} source={result.extraction_source} "
            f"experiences={len(result.payload.experiences)} "
            f"projects={len(result.payload.projects)}"
        )
    return result.payload


async def _run_arm(
    elevator: ResumeElevator,
    profile: ProfilePayload,
    emphases: tuple[str, ...],
    *,
    role_family: str,
    job_title: str | None,
) -> ArmResult:
    arm = ArmResult(emphases=list(emphases))
    started = time.monotonic()
    try:
        sections, _ = await elevator.build_sections(
            profile,
            elevation_level="elevated",
            locale="zh-CN",
            job_title=job_title,
            role_family=role_family,
            framing_emphases=list(emphases),
        )
    except Exception as exc:  # noqa: BLE001 — a failed arm is a reportable outcome
        arm.error = f"{type(exc).__name__}: {exc}"[:300]
        return arm
    arm.elapsed_ms = int((time.monotonic() - started) * 1000)
    arm.sections = sections
    arm.bullets = _bullets(sections)
    arm.coverage = audit_coverage(sections, profile).to_dict()
    arm.diagnostics = diagnose(sections).to_dict()
    arm.invariants = audit_additions(sections, profile).to_dict()
    if not arm.bullets:
        arm.error = "model returned no bullets"
    return arm


async def _reviewer_blocks_inflation(
    profile: ProfilePayload,
    arm: ArmResult,
) -> dict[str, Any]:
    """Does the reviewer still block an ownership upgrade under an `ownership` angle?

    The angle is the pressure: `framing_emphases` is passed to the reviewer so it does
    not report the user's own ordering choice as a defect, and the risk is that it reads
    the angle as permission. So a known-bad bullet is planted — source says 参与, draft
    says 主导 — and the reviewer must still fail the draft.

    The planted claim is derived from the profile's own text, so the only difference
    between pass and fail is the verb. A synthetic bullet would also test the reviewer's
    tolerance for out-of-place writing, which is a different question.
    """
    source_line = next(
        (
            h
            for exp in profile.experiences
            for h in (exp.highlights or [])
            if any(v in str(h) for v in ("参与", "协助", "配合"))
        ),
        None,
    )
    planted_from = "profile"
    if source_line is None:
        # Nothing in this profile understates ownership, so plant the pair ourselves.
        # The test is about the reviewer's rule, not about this candidate.
        source_line = "参与统一配置中心的建设，负责客户端 SDK 接入"
        planted_from = "synthetic"
        if profile.experiences:
            profile = profile.model_copy(deep=True)
            profile.experiences[0].highlights = [
                *profile.experiences[0].highlights,
                source_line,
            ]
    inflated = inflate_ownership(str(source_line))

    sections = dict(arm.sections)
    blocks = [dict(b) for b in (sections.get("experience_blocks") or [])]
    if not blocks:
        return {"ran": False, "reason": "draft had no experience blocks"}
    blocks[0] = {**blocks[0], "bullets": [inflated, *(blocks[0].get("bullets") or [])]}
    sections["experience_blocks"] = blocks

    result = await ResumeReviewer().review(
        sections=sections,
        source_profile=profile.model_dump(mode="json"),
        role_family=sections.get("role_family"),
    )
    codes = [
        str(i.get("code") or i.get("field") or "")[:60] for i in result.issues
    ]
    return {
        "ran": True,
        "planted_from": planted_from,
        "planted_bullet_excerpt": inflated[:40],
        "status": result.status.value,
        "blocked": result.status.value != "passed",
        "issue_codes": codes[:8],
        # Did the reviewer name the right defect, or fail for an unrelated reason?
        "named_ownership": any(
            "主导" in str(i.get("message") or "")
            or "ownership" in str(i.get("code") or "").lower()
            or "参与" in str(i.get("message") or "")
            for i in result.issues
        ),
    }


async def _reviewer_on_arm(profile: ProfilePayload, arm: ArmResult) -> dict[str, Any]:
    """Run the real reviewer against this arm's actual draft, no planted bullet.

    `_reviewer_blocks_inflation` proves the reviewer's rule works on a case engineered to
    trip it. It says nothing about whether the rule fires on fabrications a model
    produces by itself under normal pressure — which is the failure mode
    `writing_invariants.audit_additions` actually found in production samples (a bullet
    claiming a number absent from the entire profile). This function asks the reviewer to
    judge exactly the draft `audit_additions` already scored, so the two verdicts can be
    compared on the same bullets:

    - `audit_additions` found fabrications the reviewer also flags  -> the prompt rule in
      `evidence.md` ("No evidence -> error") holds on real output, and the deterministic
      check is a backstop, not the only line of defence.
    - `audit_additions` found fabrications the reviewer passed anyway -> the prompt rule
      does not fire reliably on this failure shape, and strengthening the prompt is the
      right next step rather than trusting the model-judged gate alone.
    """
    fabrications = [f for f in arm.invariants.get("findings", []) if f["severity"] == "fabrication"]
    if not arm.sections.get("experience_blocks") and not arm.sections.get("project_blocks"):
        return {"ran": False, "reason": "draft had no blocks to review"}
    result = await ResumeReviewer().review(
        sections=arm.sections,
        source_profile=profile.model_dump(mode="json"),
        role_family=arm.sections.get("role_family"),
    )
    issue_texts = [
        f"{i.get('code', '')} {i.get('field', '')} {i.get('message', '')}" for i in result.issues
    ]
    # A fabrication is "caught" if the reviewer raised *any* issue on the same field path
    # (loose match: the reviewer does not echo `writing_invariants`' field-path format
    # verbatim, so this falls back to substring containment against the draft text that
    # triggered the finding).
    caught = []
    missed = []
    for finding in fabrications:
        field = str(finding.get("field_path") or "")
        excerpt = str(finding.get("draft_text") or "")[:30]
        hit = any(
            (field and field in text) or (excerpt and excerpt in text) for text in issue_texts
        )
        (caught if hit else missed).append(
            {"kind": finding["kind"], "field_path": field, "detail": finding["detail"]}
        )
    return {
        "ran": True,
        "status": result.status.value,
        "available": result.available,
        "fabrications_found_by_invariants": len(fabrications),
        "fabrications_caught_by_reviewer": len(caught),
        "fabrications_missed_by_reviewer": missed,
        "issue_count": len(result.issues),
    }


async def evaluate(
    sample: Path,
    output: Path,
    *,
    job_title: str | None,
    verbose: bool,
) -> int:
    if not settings.jc_llm_enabled or not settings.jc_llm_api_key:
        raise SystemExit(
            "FAIL: this evaluation asserts live model behaviour. Set JC_LLM_ENABLED=true "
            "and JC_LLM_API_KEY, and run it where the gateway is reachable."
        )
    if not sample.is_file():
        raise SystemExit(f"FAIL: sample not found: {sample}")

    print(f"Ingesting {sample.name} ...")
    profile = await _load_profile(sample, verbose=verbose)
    role_family = resolve_role_family(
        override=profile.preferences.role_family,
        job_title=job_title,
        profile_titles=tuple(e.title for e in profile.experiences),
    )
    print(f"  role_family={role_family}")

    elevator = ResumeElevator()
    arms: list[ArmResult] = []
    for emphases in _ANGLE_ARMS:
        print(f"Generating with angles {list(emphases)} ...")
        arm = await _run_arm(
            elevator,
            profile,
            emphases,
            role_family=role_family,
            job_title=job_title,
        )
        if verbose and arm.ok:
            print(f"  {len(arm.bullets)} bullets in {arm.elapsed_ms}ms")
            print(f"  first bullet: {arm.bullets[0][:80]}")
        if arm.error:
            print(f"  ERROR: {arm.error}")
        arms.append(arm)

    usable = [a for a in arms if a.ok]
    failures: list[str] = []
    if len(usable) < 2:
        failures.append(
            f"only {len(usable)} of {len(arms)} generation arms produced a draft; "
            "cannot compare angles"
        )

    # --- variance: do different angles produce a different document? -----------------
    comparisons: list[dict[str, Any]] = []
    for i in range(len(usable)):
        for j in range(i + 1, len(usable)):
            left, right = usable[i], usable[j]
            score = _pairwise_sameness(left.bullets, right.bullets)
            same = score > _SAMENESS_CEILING
            comparisons.append(
                {
                    "left": left.emphases,
                    "right": right.emphases,
                    "sameness": round(score, 3),
                    "indistinguishable": same,
                }
            )
            if same:
                failures.append(
                    f"angles {left.emphases} and {right.emphases} produced near-identical "
                    f"text (sameness {score:.2f} > {_SAMENESS_CEILING}); the angle control "
                    "is not reaching the output"
                )

    # --- invariance: nothing unsupported was added, under any angle ------------------
    for arm in usable:
        fabrications = [
            f for f in arm.invariants.get("findings", []) if f["severity"] == "fabrication"
        ]
        for finding in fabrications:
            failures.append(
                f"angle {arm.emphases} asserted unsupported content "
                f"({finding['kind']}): {finding['detail']}"
            )
        # Project loss is always a generation defect, never a judgement call.
        if arm.coverage.get("projects_missing"):
            failures.append(
                f"angle {arm.emphases} dropped 项目经历 entirely from a profile that has "
                f"{len(profile.projects)} projects"
            )

    # --- reviewer gate under angle pressure ------------------------------------------
    gate: dict[str, Any] = {"ran": False, "reason": "no usable draft"}
    if usable:
        ownership_arm = next(
            (a for a in usable if "ownership" in a.emphases), usable[0]
        )
        print(f"Probing reviewer gate under angles {ownership_arm.emphases} ...")
        gate = await _reviewer_blocks_inflation(profile, ownership_arm)
        gate["under_angles"] = ownership_arm.emphases
        if gate.get("ran") and not gate.get("blocked"):
            failures.append(
                "reviewer passed a draft claiming 主导 where the profile says 参与 — the "
                "export gate does not hold under an `ownership` angle"
            )
        if verbose:
            print(f"  reviewer status={gate.get('status')} codes={gate.get('issue_codes')}")

    # --- reviewer vs. the invariant audit, on each arm's own draft ---------------------
    #
    # Reported, not asserted into `failures`: a miss here means the prompt-based gate
    # needs strengthening, not that this run is broken. Promoting it to a hard failure
    # would make a known reviewer weakness block every future run instead of staying
    # visible in the report where a human reads it.
    reviewer_vs_invariants: list[dict[str, Any]] = []
    for arm in usable:
        if not any(f["severity"] == "fabrication" for f in arm.invariants.get("findings", [])):
            continue
        print(f"Checking whether the reviewer independently catches angle {arm.emphases} ...")
        verdict = await _reviewer_on_arm(profile, arm)
        verdict["angles"] = arm.emphases
        reviewer_vs_invariants.append(verdict)
        if verbose:
            print(
                f"  invariants found {verdict.get('fabrications_found_by_invariants')}, "
                f"reviewer caught {verdict.get('fabrications_caught_by_reviewer')}"
            )

    # --- calibration: reported, never asserted ---------------------------------------
    dropped_samples: list[dict[str, Any]] = []
    for arm in usable:
        for item in arm.coverage.get("dropped", []):
            dropped_samples.append(
                {
                    "angles": arm.emphases,
                    "where": item["where"],
                    "best_match": item["best_match"],
                    # Excerpt only: the report is checked into the repo.
                    "source_excerpt": str(item["text"])[:60],
                }
            )
    near_misses = [d for d in dropped_samples if d["best_match"] >= 0.30]
    calibration = {
        "match_threshold": 0.42,
        "note": (
            "False-positive rate for the coverage threshold. `near_miss` items scored "
            "just under the threshold and are the ones to read: if most flagged items "
            "are near misses the threshold is too strict for real output."
        ),
        "source_highlights": (usable[0].coverage.get("source_highlights") if usable else 0),
        "flagged_total": len(dropped_samples),
        "near_miss_total": len(near_misses),
        "flagged": dropped_samples[:20],
    }

    report = {
        "scope": (
            "live-model writing semantics: angle variance, honesty invariance, reviewer "
            "gate under angle pressure, coverage-threshold calibration. Not a check of "
            "extraction quality, HTTP contracts or rendering."
        ),
        "sample": sample.name,
        "role_family": role_family,
        "job_title": job_title,
        "max_emphases": MAX_EMPHASES,
        "resolved_default_angles": resolve_emphases(None, role_family=role_family),
        "arms": [
            {
                "emphases": a.emphases,
                "ok": a.ok,
                "error": a.error,
                "elapsed_ms": a.elapsed_ms,
                "bullet_count": len(a.bullets),
                "coverage": {
                    k: a.coverage.get(k)
                    for k in ("source_highlights", "covered", "ratio", "projects_missing")
                },
                "estimated_pages": a.diagnostics.get("estimated_pages"),
                "invariants": {
                    "holds": a.invariants.get("holds"),
                    "fabrication_count": a.invariants.get("fabrication_count"),
                    "attributed_bullets": a.invariants.get("attributed_bullets"),
                    "draft_bullets": a.invariants.get("draft_bullets"),
                    "findings": [
                        {
                            k: (str(v)[:80] if k in {"draft_text", "source_text"} else v)
                            for k, v in f.items()
                        }
                        for f in a.invariants.get("findings", [])[:20]
                    ],
                },
            }
            for a in arms
        ],
        "angle_variance": {
            "sameness_ceiling": _SAMENESS_CEILING,
            "comparisons": comparisons,
        },
        "reviewer_gate": gate,
        "reviewer_vs_invariants": reviewer_vs_invariants,
        "coverage_calibration": calibration,
        "failures": failures,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"\nReport: {output}")

    if failures:
        print(f"FAIL: {len(failures)} writing-semantics failure(s)")
        for item in failures:
            print(f"  - {item}")
        return 1
    missed_total = sum(
        len(v.get("fabrications_missed_by_reviewer") or []) for v in reviewer_vs_invariants
    )
    print(
        f"PASS: {len(usable)} angle arms, {len(comparisons)} comparisons, reviewer gate "
        f"{'held' if gate.get('blocked') else 'not probed'}; "
        f"{calibration['flagged_total']} coverage items flagged for human read; "
        f"reviewer-vs-invariants checked on {len(reviewer_vs_invariants)} arm(s) with "
        f"{missed_total} fabrication(s) the reviewer did not independently catch"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Assert live-model writing semantics: angle variance, honesty "
            "invariance, reviewer gate, coverage calibration."
        ),
        epilog="See the module docstring for the assertion strategy and why it is "
        "differential rather than literal.",
    )
    parser.add_argument(
        "sample",
        type=Path,
        help="Resume file to evaluate (PDF/DOCX/image). Treated as PII.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "docs" / "evidence" / "writing-evaluation.json",
    )
    parser.add_argument(
        "--job-title",
        default=None,
        help="Target job title, so role family and jd_fit angle resolve as in product.",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    async def _run() -> int:
        try:
            return await evaluate(
                args.sample,
                args.output,
                job_title=args.job_title,
                verbose=args.verbose,
            )
        finally:
            # Dispose the pooled MySQL connections while the loop that owns
            # them is still running. Without this, idle aiomysql connections
            # get garbage-collected after asyncio.run() tears the loop down,
            # which logs a harmless but noisy "Event loop is closed" error.
            await _db_engine.dispose()

    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
