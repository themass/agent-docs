"""The writer must not turn a date range into a stated tenure.

Production, found by the Cursor semantic pass: a profile whose source text
contained no number of years came back from all three elevation levels with
「6 年后端研发经验」. The figure was correct arithmetic on
`2020-01`→`2026-01` — and still a claim the candidate never made.

Why this matters more than it looks: ATS and recruiters read the summary line as
the candidate's own statement, and an interviewer checks it against the dates. A
number the user did not supply is exactly the "虚构" the product principle
forbids, even when the arithmetic is right. The rule now lives in the writer's
structure guidance, so this test reads that file rather than restating it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

STRUCTURE = (
    Path(__file__).resolve().parents[2]
    / "agent"
    / "skills"
    / "public"
    / "resume-writer"
    / "references"
    / "structure.md"
)


@pytest.fixture(scope="module")
def guidance() -> str:
    # Markdown wraps at 90 columns, so a phrase can be split across lines. Collapse
    # whitespace before matching, or these assertions fail on a line break rather
    # than on the rule being absent.
    return " ".join(STRUCTURE.read_text("utf-8").split())


def test_the_structure_guidance_exists(guidance):
    assert guidance.strip()


def test_tenure_is_conditional_on_the_source_stating_it(guidance):
    """The summary's first move may not assume a number is available."""
    summary_section = guidance.split("### 1.")[1].split("### 2.")[0]
    assert "Years only when the profile states them" in summary_section


def test_the_guidance_names_the_failure_that_happened(guidance):
    """A rule with a measurement behind it survives editing; a bare rule does not."""
    assert "6 年后端研发经验" in guidance
    assert "date range is not a statement of tenure" in guidance


def test_it_says_what_to_write_instead(guidance):
    """Refusing without an alternative is how a rule gets quietly dropped."""
    assert "If it does not, open with the role" in guidance
    # And the approximate path, so "helpful" does not become "unspecified".
    assert "约 6 年" in guidance


def test_the_source_still_forbids_inventing_numbers(guidance):
    """Anchor: the broader honesty rule this sits inside must remain present."""
    whole = " ".join(STRUCTURE.read_text("utf-8").split())
    assert "supported" in whole.lower()
