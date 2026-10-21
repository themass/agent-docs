"""Framing presets: the user-selectable angle, and its hard boundaries."""

from jc.domain.role_families import PLAYBOOKS
from jc.services.framing_presets import (
    MAX_EMPHASES,
    PRESETS,
    as_prompt_block,
    catalogue,
    get_preset,
    recommended_for,
    resolve_emphases,
)


def test_every_role_family_has_a_recommendation() -> None:
    """A family with no default would silently fall back to the generic pair."""
    for family in PLAYBOOKS:
        rec = recommended_for(family)
        assert rec, family
        assert all(get_preset(p) is not None for p in rec), family


def test_an_empty_selection_falls_back_to_the_role_default() -> None:
    """The writer always had an implicit emphasis; the role's own is better than none."""
    assert resolve_emphases([], role_family="pm") == recommended_for("pm")
    assert resolve_emphases(None, role_family="legal") == recommended_for("legal")


def test_an_all_unknown_selection_does_not_strip_the_document_of_an_angle() -> None:
    assert resolve_emphases(["nonsense", ""], role_family="backend") == recommended_for(
        "backend"
    )


def test_user_order_is_preserved_so_the_first_pick_stays_primary() -> None:
    assert resolve_emphases(["depth", "scope"], role_family="pm") == ["depth", "scope"]


def test_selection_is_capped_because_emphasising_everything_emphasises_nothing() -> None:
    picked = resolve_emphases(
        ["scope", "ownership", "outcome", "depth"], role_family="backend"
    )
    assert len(picked) == MAX_EMPHASES
    assert picked == ["scope", "ownership"]


def test_duplicates_do_not_consume_the_cap() -> None:
    assert resolve_emphases(["scope", "scope", "depth"], role_family="backend") == [
        "scope",
        "depth",
    ]


def test_prompt_block_labels_primary_and_secondary() -> None:
    block = as_prompt_block(["outcome", "depth"])
    assert block.index("Primary") < block.index("Secondary")
    assert "never license a new fact" in block


def test_prompt_block_restates_the_honesty_boundary_every_time() -> None:
    """The angle text travels into the prompt; the limit must travel with it."""
    for preset in PRESETS:
        block = as_prompt_block([preset.id])
        assert "never license a new fact" in block


def test_ownership_angle_forbids_upgrading_the_source_verb() -> None:
    """The one angle a model would most plausibly over-apply."""
    preset = get_preset("ownership")
    assert preset is not None
    assert "Do not upgrade the source's verb" in preset.instruction


def test_jd_fit_angle_forbids_adding_requested_skills() -> None:
    preset = get_preset("jd_fit")
    assert preset is not None
    assert "Never add a skill" in preset.instruction


def test_catalogue_flags_the_recommendations_for_the_resolved_family() -> None:
    items = catalogue("sales")
    flagged = {i["id"] for i in items if i["recommended"]}
    assert flagged == set(recommended_for("sales"))
    assert len(items) == len(PRESETS)


def test_unknown_preset_id_resolves_to_nothing_rather_than_a_default_object() -> None:
    assert get_preset("made-up") is None
    assert get_preset(None) is None
