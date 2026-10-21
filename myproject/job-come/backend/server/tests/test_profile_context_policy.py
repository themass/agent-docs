import copy
import json
from unittest.mock import AsyncMock

import pytest

from jc.domain.profile_context import material_profile, read_profile_section, turn_profile_context
from jc.schemas.profile_payload import ProfilePayload


def profile():
    return ProfilePayload.model_validate(
        {
            "contact": {"name": "张三", "photo": {"storage_key": "secret.jpg"}},
            "experiences": [
                {
                    "id": "e1",
                    "company": "公司",
                    "title": "开发",
                    "start_date": "2020",
                    "highlights": ["事实" * 300] * 30,
                }
            ],
            "i18n": {},
        }
    )


def test_turn_index_is_small_and_does_not_repeat_career():
    source = profile()
    before = copy.deepcopy(source)
    value = json.loads(turn_profile_context(source))
    assert value["data"]["sections"]["experiences"]["count"] == 1
    assert value["complete"] is False
    assert "事实" not in json.dumps(value, ensure_ascii=False)
    assert "secret.jpg" not in json.dumps(value)
    assert len(turn_profile_context(source)) < 2000
    assert source == before


def test_focused_fact_is_exact_not_truncated():
    source = profile()
    result = json.loads(turn_profile_context(source, focus_path="experiences[0].highlights[2]"))
    assert result["focus"]["data"] == source.experiences[0].highlights[2]
    large = json.loads(turn_profile_context(source, focus_path="experiences[0]"))
    assert "focus" not in large
    assert large["focus_read_required"] == "experiences[0]"


def test_page_metadata_discloses_unread_facts():
    payload = {"skills": [{"name": str(i)} for i in range(9)]}
    first = read_profile_section(payload, section="skills", limit=5)
    second = read_profile_section(payload, section="skills", offset=first["next_offset"])
    assert first["complete"] is False and second["complete"] is False
    assert first["total"] == 9 and second["next_offset"] is None
    assert first["data"] + second["data"] == payload["skills"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"section": "i18n"},
        {"section": "skills", "offset": -1},
        {"section": "skills", "limit": 21},
        {"section": "skills", "limit": True},
        {"section": "skills", "field_path": "contact.name"},
        {"section": "skills", "field_path": "skills[-1]"},
    ],
)
def test_invalid_reads_fail_explicitly(kwargs):
    with pytest.raises(ValueError):
        read_profile_section({}, **kwargs)


def test_oversized_read_fails_instead_of_slicing_fact():
    with pytest.raises(ValueError, match="narrow"):
        read_profile_section({"summary": "字" * 7000}, section="summary")


def test_material_profile_keeps_facts_and_constraints_but_drops_render_data():
    source = profile()
    data = material_profile(source)
    assert data["experiences"][0]["highlights"] == source.experiences[0].highlights
    assert "photo" not in data["contact"] and "i18n" not in data and "meta" not in data
    assert "constraints" in data


@pytest.mark.asyncio
async def test_mcp_dispatch_passes_read_options(monkeypatch):
    from jc.mcp import handlers

    handler = AsyncMock(return_value={})
    monkeypatch.setitem(handlers.TOOL_HANDLERS, "jc_profile_get", handler)
    await handlers.dispatch_tool(
        None,
        "jc_profile_get",
        {
            "section": "experiences",
            "field_path": "experiences[0].highlights[0]",
            "limit": 1,
        },
    )
    assert handler.call_args.kwargs == {
        "section": "experiences",
        "field_path": "experiences[0].highlights[0]",
        "limit": 1,
    }


def test_long_source_string_can_be_read_in_explicit_complete_pages():
    text = "字" * 9000 + "结尾不能丢"
    offset, chunks = 0, []
    while offset is not None:
        page = read_profile_section(
            {"summary": text},
            section="summary",
            field_path="summary",
            text_offset=offset,
        )
        assert page["complete"] is False and page["total_chars"] == len(text)
        chunks.append(page["data"])
        offset = page["next_text_offset"]
    assert "".join(chunks) == text


@pytest.mark.asyncio
async def test_model_default_read_is_index_not_full_profile(monkeypatch):
    from jc.mcp import handlers

    handler = AsyncMock(return_value={})
    monkeypatch.setitem(handlers.TOOL_HANDLERS, "jc_profile_get", handler)
    await handlers.dispatch_tool(None, "jc_profile_get", {})
    assert handler.call_args.kwargs == {"section": "overview"}


def test_nested_highlights_support_paging_not_just_top_level_entities():
    value = profile().model_dump(mode="json")
    result = read_profile_section(
        value,
        section="experiences",
        field_path="experiences[0].highlights",
        offset=2,
        limit=1,
    )
    assert result["data"] == [value["experiences"][0]["highlights"][2]]
    assert result["total"] == 30 and result["next_offset"] == 3
    assert result["complete"] is False


def test_overview_heading_index_is_explicitly_partial():
    value = profile().model_dump(mode="json")
    value["experiences"] *= 7
    report = read_profile_section(value, section="overview")
    index = report["data"]["sections"]["experiences"]
    assert index["count"] == 7 and index["next_offset"] == 5
    assert index["entries"][0]["path"] == "experiences[0]"
    assert index["entries"][0]["label_preview"] == "公司 · 开发"
    assert report["complete"] is False
