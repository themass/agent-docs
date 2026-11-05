"""The sheet sent to domain experts is what the model is told, for every family."""

from __future__ import annotations

from jc.coach.family_review import render_review_sheet
from jc.domain.role_families import PLAYBOOKS


def test_every_family_with_guidance_has_a_section_with_all_its_angles():
    sheet = render_review_sheet()
    for family in PLAYBOOKS.values():
        if family.id == "general":
            continue
        assert f"## {family.label}（`{family.id}`）" in sheet
        for angle in family.probe_angles:
            assert angle in sheet


def test_the_neutral_family_is_left_out_because_it_has_nothing_to_review():
    assert PLAYBOOKS["general"].probe_angles == ()
    assert "`general`）" not in render_review_sheet().split("## ", 1)[1]


def test_every_section_asks_the_reviewer_the_same_questions():
    sheet = render_review_sheet()
    sections = sheet.split("\n## ")[1:]
    assert len(sections) == len(PLAYBOOKS) - 1
    assert all(section.count("| 问题 | 你的意见 |") == 1 for section in sections)


def test_the_committed_sheet_is_the_one_the_code_produces():
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "docs" / "operations" / "REVIEW-ROLE-FAMILIES.md"
    committed = path.read_text(encoding="utf-8")
    assert committed.rstrip("\n") == render_review_sheet().rstrip("\n"), (
        "regenerate: python -m jc.coach.family_review > docs/operations/REVIEW-ROLE-FAMILIES.md"
    )
