"""Skill packages: loading, fragment selection, and the reachability guarantee."""

from __future__ import annotations

import pytest

from jc.domain.role_families import PLAYBOOKS, get_playbook
from jc.skills import loader
from jc.skills.composer import compose_writing_prompt
from jc.skills.loader import all_skill_ids, get_skill, require_skill


@pytest.fixture
def temp_skills(monkeypatch, tmp_path):
    """Point the loader at a temp skill root and drop its cache around the test."""

    def build(packages: dict[str, dict[str, str]]) -> None:
        for skill_id, files in packages.items():
            skill_dir = tmp_path / "public" / skill_id
            (skill_dir / "references").mkdir(parents=True, exist_ok=True)
            for name, text in files.items():
                if name == "SKILL.md":
                    (skill_dir / name).write_text(text, encoding="utf-8")
                else:
                    target = skill_dir / "references" / f"{name}.md"
                    target.write_text(text, encoding="utf-8")
        monkeypatch.setattr(loader.settings, "jc_skills_root", str(tmp_path))
        loader.reload_skills()

    yield build
    loader.reload_skills()


def test_frontmatter_is_stripped_but_the_description_is_kept(temp_skills) -> None:
    temp_skills(
        {"probe": {"SKILL.md": "---\nname: probe\ndescription: 一句话\n---\n\nBODY TEXT\n"}}
    )

    skill = require_skill("probe")

    assert skill.description == "一句话"
    assert skill.body == "BODY TEXT"
    assert "---" not in skill.body


def test_a_file_without_frontmatter_keeps_all_of_its_content(temp_skills) -> None:
    """Losing a body over a missing fence would silently drop the methodology."""
    temp_skills({"probe": {"SKILL.md": "BODY ONLY\n"}})

    assert require_skill("probe").body == "BODY ONLY"


def test_unterminated_frontmatter_keeps_the_body_rather_than_dropping_it(temp_skills) -> None:
    temp_skills({"probe": {"SKILL.md": "---\ndescription: x\n\nBODY\n"}})

    assert "BODY" in require_skill("probe").body


def test_a_missing_reference_is_empty_not_an_error(temp_skills) -> None:
    """Reference sets differ per skill on purpose; asking for all of them is normal."""
    temp_skills({"probe": {"SKILL.md": "B", "method": "M"}})

    skill = require_skill("probe")

    assert skill.reference("method") == "M"
    assert skill.reference("structure") == ""


def test_a_missing_skill_raises_rather_than_degrading(temp_skills) -> None:
    """A writer that silently loses its methodology still returns a resume.

    That failure would reach the user as a quietly worse document rather than as
    an error anyone notices, so the lookup is strict.
    """
    temp_skills({"probe": {"SKILL.md": "B"}})

    assert get_skill("absent") is None
    with pytest.raises(LookupError):
        require_skill("absent")


def test_reload_picks_up_a_changed_package(temp_skills) -> None:
    temp_skills({"probe": {"SKILL.md": "FIRST"}})
    assert require_skill("probe").body == "FIRST"

    temp_skills({"probe": {"SKILL.md": "SECOND"}})
    assert require_skill("probe").body == "SECOND"


# --- composition ----------------------------------------------------------------------


def test_layers_are_ordered_from_universal_to_specific(temp_skills) -> None:
    """Order is the contract: the honesty rules are read before any relaxation."""
    temp_skills(
        {
            "resume-writer": {
                "SKILL.md": "BASE",
                "structure": "STRUCTURE",
                "method": "METHOD",
                "targeting": "TARGETING",
                "family-backend": "FAMILY",
            }
        }
    )

    composed = compose_writing_prompt(
        skill_id="resume-writer",
        playbook=get_playbook("backend"),
        document_contract="CONTRACT",
    )

    order = ("BASE", "STRUCTURE", "METHOD", "TARGETING", "FAMILY", "CONTRACT")
    positions = [composed.text.index(name) for name in order]
    assert positions == sorted(positions)
    assert composed.layers == (
        "resume-writer:base",
        "resume-writer:structure",
        "resume-writer:method",
        "resume-writer:targeting",
        "resume-writer:family-backend",
        "playbook:backend",
        "blueprint",
    )


def test_the_qualitative_fragment_follows_the_playbook_not_a_second_list(temp_skills) -> None:
    """The writer and the reviewer must not disagree about who owes a number.

    `quantification_optional` is the same flag the reviewer reads, so a second
    hand-maintained list of "qualitative families" could drift from it.
    """
    temp_skills(
        {"resume-writer": {"SKILL.md": "BASE", "qualitative-outcomes": "QUALITATIVE"}}
    )

    assert get_playbook("legal").quantification_optional is True
    assert get_playbook("backend").quantification_optional is False

    assert "QUALITATIVE" in compose_writing_prompt(
        skill_id="resume-writer", playbook=get_playbook("legal")
    ).text
    assert "QUALITATIVE" not in compose_writing_prompt(
        skill_id="resume-writer", playbook=get_playbook("backend")
    ).text


def test_an_empty_extra_section_does_not_leave_a_dangling_header(temp_skills) -> None:
    temp_skills({"resume-writer": {"SKILL.md": "BASE"}})

    composed = compose_writing_prompt(
        skill_id="resume-writer",
        playbook=get_playbook("backend"),
        extra_sections=(("Angles", ""), ("Kept", "TEXT")),
    )

    assert "## Angles" not in composed.text
    assert "## Kept" in composed.text


def test_a_family_with_no_fragment_does_not_borrow_another_familys(temp_skills) -> None:
    """Being written to the wrong audience's standard is worse than to a neutral one."""
    temp_skills(
        {"resume-writer": {"SKILL.md": "BASE", "family-backend": "BACKEND ONLY"}}
    )

    composed = compose_writing_prompt(
        skill_id="resume-writer", playbook=get_playbook("sales")
    )

    assert "BACKEND ONLY" not in composed.text
    assert "BASE" in composed.text


# --- the guarantee that made this module necessary ------------------------------------


def test_every_role_family_resolves_to_a_real_writer_fragment_or_the_baseline() -> None:
    """Runs against the shipped packages, not a fixture.

    A family id that names a fragment file nobody wrote is invisible at runtime —
    composition succeeds and that role quietly gets the generic methodology. This
    is the check that a new family in `role_families.py` cannot ship half-wired.
    """
    writer = require_skill("resume-writer")
    reviewer = require_skill("resume-reviewer")

    missing_writer = sorted(
        family for family in PLAYBOOKS if family != "general"
        and not writer.reference(f"family-{family}")
    )
    missing_reviewer = sorted(
        family for family in PLAYBOOKS if family != "general"
        and not reviewer.reference(f"family-{family}")
    )

    assert missing_writer == []
    assert missing_reviewer == []


def test_the_shipped_writer_skill_carries_the_methodology_not_a_stub() -> None:
    """The stub state this module was written to end: 10 lines of description.

    Asserted on content rather than length so padding the file cannot satisfy it.
    """
    writer = require_skill("resume-writer")

    assert "experience_blocks" in writer.body
    assert "Never invent" in writer.body
    assert "Action + Object + Outcome" in writer.reference("method")
    assert "结论先行" in writer.reference("structure")


def test_the_writer_and_the_reviewer_are_separate_packages() -> None:
    """Per-role packages are the point: each agent reads only its own methodology."""
    assert "resume-writer" in all_skill_ids()
    assert "resume-reviewer" in all_skill_ids()

    writer_body = require_skill("resume-writer").body
    reviewer_body = require_skill("resume-reviewer").body

    assert "resume writer" in writer_body.lower()
    assert "export reviewer" in reviewer_body.lower()
    assert writer_body != reviewer_body


def test_the_interview_skill_ships_and_is_distinct_from_the_coach() -> None:
    """Two roles, two packages: one asks for material, the other edits what exists."""
    assert "profile-interview" in all_skill_ids()

    interview = require_skill("profile-interview")
    coach = require_skill("resume-coach")

    assert "把简历问出来" in interview.body
    assert interview.body != coach.body
    # Its own method fragment, written for asking rather than rewriting.
    assert "追问" in interview.reference("method")
    assert "没什么好说的" in interview.reference("method")


def test_the_interview_skill_carries_the_same_honesty_rule() -> None:
    """The one rule no fragment may relax has to hold in the asking path too."""
    body = require_skill("profile-interview").body

    assert "不要编公司、学校、日期、职级、数字" in body
