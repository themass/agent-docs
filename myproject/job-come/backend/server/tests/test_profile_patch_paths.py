"""The exact path-shaped edits in the reported trace must survive validation."""

from __future__ import annotations

import pytest

from jc.exceptions import AppError
from jc.services.profile_patch_ops import apply_profile_patch


def source():
    return {
        "contact": {"name": "A"},
        "experiences": [
            {
                "id": "exp_1",
                "company": "腾讯",
                "title": "T11",
                "start_date": "2020-05",
                "highlights": ["原文一", "原文二", "保留", "原文四"],
            }
        ],
    }


def test_flat_paths_change_exact_bullets_preserving_siblings():
    before = source()
    payload = apply_profile_patch(
        before,
        {
            "experiences[0].highlights[0]": "修改一",
            "experiences[0].highlights[1]": "修改二",
            "experiences[0].highlights[3]": "修改三",
        },
    )
    assert payload.experiences[0].highlights == ["修改一", "修改二", "保留", "修改三"]
    assert before == source()
    assert not any("[" in k for k in payload.model_dump())


def test_nested_merge_and_source_language_cache_are_updated():
    before = source()
    before["i18n"] = {"zh-CN": {"summary": "过期摘要"}, "en-US": {"summary": "old"}}
    before["meta"] = {"source_locale": "zh-CN", "i18n_status": {"en-US": "ready"}}
    payload = apply_profile_patch(before, {"summary": "新摘要", "contact": {"location": "北京"}})
    assert payload.contact.name == "A" and payload.contact.location == "北京"
    assert payload.i18n["zh-CN"].summary == "新摘要"
    assert payload.meta.i18n_status["en-US"] == "stale"


@pytest.mark.parametrize(
    "patch",
    [
        {},
        {"unknown": "ignored"},
        {"contact": {"unknown": "ignored"}},
        {"experiences[99].highlights[0]": "x"},
        {"experiences[-1].highlights[0]": "x"},
        {"experiences[0].unknown": "x"},
        {"experiences": source()["experiences"], "experiences[0].title": "x"},
        {"contact.name": "A"},
        {"meta": {"source_locale": "en-US"}},
    ],
)
def test_invalid_unknown_ambiguous_and_noop_edits_fail_before_confirmation(patch):
    with pytest.raises(AppError):
        apply_profile_patch(source(), patch)


def test_source_language_overlay_cannot_revert_facts():
    from jc.schemas.profile_payload import ProfilePayload
    from jc.services.profile_i18n import overlay_profile

    base = source()
    base["meta"] = {"source_locale": "zh-CN", "i18n_status": {"en-US": "stale"}}
    base["i18n"] = {
        "zh-CN": {"experiences": [{"id": "exp_1", "highlights": ["过期原文"]}]},
        "en-US": {"experiences": [{"id": "exp_1", "highlights": ["old translation"]}]},
    }
    payload = ProfilePayload.model_validate(base)
    assert overlay_profile(payload, "zh-CN").experiences[0].highlights[0] == "原文一"
    assert overlay_profile(payload, "en-US").experiences[0].highlights[0] == "原文一"
