"""Metric candidates: clickable ways to quantify a bullet, with no values attached."""

import pytest

from jc.domain.role_families import PLAYBOOKS, get_playbook
from jc.services.metric_prompts import (
    BLANK,
    candidates_for,
    candidates_for_kind,
)

_DIGITS = set("0123456789")


@pytest.mark.parametrize("family", sorted(PLAYBOOKS))
def test_no_candidate_ever_carries_a_number(family: str) -> None:
    """The product contract: we supply the sentence shape, the user supplies the facts.

    A pre-filled figure is the one failure mode this whole feature has to avoid. It would
    be accepted precisely because it looks plausible, reach a real recruiter, and then
    collapse in the interview with the cost entirely on the candidate.
    """
    for candidate in candidates_for(get_playbook(family)):
        # Any digit in the skeleton may only have come from the dimension's own name
        # (`P99 延迟`), never from a value we chose.
        for ch in candidate.skeleton:
            if ch in _DIGITS:
                assert ch in candidate.dimension, (
                    f"{family}: skeleton {candidate.skeleton!r} introduced a digit that "
                    "is not part of the metric's name"
                )


@pytest.mark.parametrize("family", sorted(PLAYBOOKS))
def test_every_skeleton_has_a_blank_to_fill(family: str) -> None:
    """A skeleton with nowhere to type is a label, and the panel already had labels."""
    for candidate in candidates_for(get_playbook(family)):
        assert BLANK in candidate.skeleton


def test_a_metric_that_should_fall_is_not_told_to_rise() -> None:
    """A confidently wrong hint is worse than no hint.

    Keyword classification is the risk here: an early generic `率` rule would catch
    `错误率` and tell the user their error rate was supposed to go up.
    """
    general = {c.dimension: c for c in candidates_for(get_playbook("general"))}
    assert general["质量与差错率"].direction == "down"

    ios = {c.dimension: c for c in candidates_for(get_playbook("ios"))}
    assert ios["崩溃率"].direction == "down"
    assert ios["启动耗时"].direction == "down"


def test_a_name_that_already_states_its_direction_is_not_made_to_contradict_itself() -> None:
    """`风险敞口下降从 ___ 降到 ___` says the same thing twice and reads as broken."""
    legal = {c.dimension: c for c in candidates_for(get_playbook("legal"))}
    exposure = legal["风险敞口下降"]
    assert exposure.direction == "self"
    assert "降到" not in exposure.skeleton
    assert exposure.skeleton.endswith(BLANK)


def test_an_unrecognised_dimension_degrades_to_a_neutral_ask() -> None:
    """We have no basis for claiming a direction, so we claim none.

    Dropping the dimension entirely would be worse: a blank the user can fill is more
    use than an omission, and the playbook listed it for a reason.
    """
    management = {c.dimension: c for c in candidates_for(get_playbook("management"))}
    unknown = management["业务目标达成"]
    assert unknown.direction in ("unknown", "self")
    assert BLANK in unknown.skeleton
    assert "提升到" not in unknown.skeleton


def test_a_cjk_latin_boundary_gets_its_space() -> None:
    """`QPS从 ___` runs two scripts together and reads as a typo."""
    backend = {c.dimension: c for c in candidates_for(get_playbook("backend"))}
    assert "QPS 从" in backend["QPS"].skeleton


def test_alternate_spellings_of_one_metric_collapse_to_one_candidate() -> None:
    """`P99/P95 延迟` is one choice, not two: offering both adds length, not options."""
    backend = candidates_for(get_playbook("backend"))
    dimensions = [c.dimension for c in backend]
    assert "P99 延迟" in dimensions
    assert not any("P95" in d for d in dimensions)
    assert len(dimensions) == len(set(dimensions))


def test_only_the_gap_kinds_that_ask_for_a_figure_get_skeletons() -> None:
    """`weak_ownership` asks how far the user's ownership went, not for a number.

    Attaching 「P99 延迟从 ___ 降到 ___」to that question tells the user we want a metric
    when we want a sentence, and those kinds already carry their own examples.
    """
    playbook = get_playbook("backend")
    assert candidates_for_kind(playbook, "missing_outcome")
    assert candidates_for_kind(playbook, "unquantified_outcome")
    assert candidates_for_kind(playbook, "vague_quantity")
    assert candidates_for_kind(playbook, "weak_ownership") == []
    assert candidates_for_kind(playbook, "empty_experience") == []
    assert candidates_for_kind(playbook, "missing_must_have") == []


def test_candidates_follow_the_playbook_order() -> None:
    """The playbook's order is already 'strongest evidence first' for the family, and a
    second ranking here would be a second opinion about the same question."""
    playbook = get_playbook("devops")
    first = candidates_for(playbook, limit=2)
    assert [c.dimension for c in first] == ["MTTR", "变更成功率"]


def test_a_quantification_optional_family_still_gets_skeletons_when_asked() -> None:
    """`quantification_optional` decides whether the *question* is asked at all. Once it
    has been asked, the answer is still a figure and still worth making clickable."""
    assert get_playbook("legal").quantification_optional
    assert candidates_for_kind(get_playbook("legal"), "missing_outcome")
