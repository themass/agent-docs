"""Source units are semantic paragraphs, not punctuation-delimited accomplishments."""

from copy import deepcopy

import pytest

from jc.schemas.profile_payload import ProfilePayload
from jc.services.resume_draft_builder import ResumeDraftBuilder
from jc.services.resume_elevator import ResumeElevator
from jc.services.resume_structure import compose_document

PROJECT = "订单改造：面向多车型派单；重构路由与重试机制；上线后成功率提升1.5个百分点。"


def test_normalization_preserves_project_paragraph_with_semicolons_and_line_wraps():
    paragraph = PROJECT + "\n持续跟进灰度反馈，完成回滚预案。"
    sections = {"project_blocks": [{"name": "订单改造", "bullets": [paragraph]}]}
    assert ResumeElevator._normalize_sections(sections)["project_blocks"][0]["bullets"] == [
        paragraph
    ]


def test_composition_does_not_move_project_result_ahead_of_its_context():
    bullets = [
        "背景：旧配置系统无法覆盖多个区域",
        "实施：统一配置与灰度发布流程",
        "成果：覆盖120个服务，事故下降70%",
    ]
    sections = {"project_blocks": [{"name": "配置中心", "bullets": list(bullets)}]}
    report = compose_document(sections, role_family="backend")
    assert sections["project_blocks"][0]["bullets"] == bullets
    assert not report.moves


def baseline():
    profile = ProfilePayload.model_validate(
        {
            "experiences": [
                {
                    "id": "e1",
                    "company": "示例公司",
                    "title": "工程师",
                    "start_date": "2020-01",
                    "highlights": [PROJECT],
                }
            ],
            "projects": [
                {
                    "id": "p1",
                    "name": "订单改造",
                    "description": "完整项目背景；多车型订单的派单改造",
                    "highlights": [PROJECT],
                }
            ],
        }
    )
    return ResumeDraftBuilder().build(
        profile, elevation_level="conservative", role_family="backend"
    )[0]


def test_writer_expansion_restores_source_unit_instead_of_shipping_fragmented_project():
    original = baseline()
    written = deepcopy(original)
    written["project_blocks"][0]["bullets"] = [
        "面向多车型派单",
        "重构路由与重试机制",
        "成功率提升1.5个百分点",
    ]
    warnings = ResumeElevator._preserve_source_units(written, original)
    assert written["project_blocks"][0] == original["project_blocks"][0]
    assert warnings == ["project_blocks[0]"]
    assert written["experience_blocks"] == original["experience_blocks"]


def test_writer_cannot_merge_or_duplicate_source_projects():
    original = baseline()
    written = deepcopy(original)
    written["project_blocks"] *= 2
    warnings = ResumeElevator._preserve_source_units(written, original)
    assert written["project_blocks"] == original["project_blocks"]
    assert warnings


def test_one_to_one_rewrite_and_original_source_order_are_kept():
    original = baseline()
    written = deepcopy(original)
    written["experience_blocks"][0]["bullets"] = ["优化后的完整陈述，保留项目背景、实施和成果。"]
    assert ResumeElevator._preserve_source_units(written, original) == []
    assert written["experience_blocks"][0]["bullets"] == [
        "优化后的完整陈述，保留项目背景、实施和成果。"
    ]


@pytest.mark.asyncio
async def test_production_writer_path_guards_fragmentation_and_reports_source_fallback(monkeypatch):
    from jc.config import settings

    profile = ProfilePayload.model_validate(
        {
            "experiences": [
                {
                    "id": "e1",
                    "company": "示例公司",
                    "title": "工程师",
                    "start_date": "2020-01",
                    "highlights": [PROJECT],
                }
            ]
        }
    )
    source, _ = ResumeDraftBuilder().build(
        profile, elevation_level="conservative", role_family="backend"
    )

    class Router:
        async def acompletion(self, *args, **kwargs):
            result = deepcopy(source)
            result["experience_blocks"][0]["bullets"] = ["面向多车型派单", "成功率提升1.5个百分点"]
            return result

    monkeypatch.setattr(settings, "jc_llm_enabled", True)
    monkeypatch.setattr("jc.services.resume_elevator.get_llm_router", lambda: Router())
    result, _ = await ResumeElevator().build_sections(
        profile, elevation_level="standard", role_family="backend"
    )
    assert result["experience_blocks"][0]["bullets"] == [PROJECT]
    assert result["generation"]["mode"] == "structure_guarded"
    assert "原文" in result["generation"]["warning"]


def test_project_identity_not_array_position_keeps_reordered_entities_attached():
    original = baseline()
    second = deepcopy(original["project_blocks"][0])
    second.update(id="p2", name="数据治理", bullets=["治理数据质量，统一字段校验。"])
    original["project_blocks"].append(second)
    written = deepcopy(original)
    written["project_blocks"].reverse()
    assert ResumeElevator._preserve_source_units(written, original) == []
    assert [b["id"] for b in written["project_blocks"]] == ["p1", "p2"]
    assert written["project_blocks"][0]["bullets"] == [PROJECT]


def test_ambiguous_legacy_project_names_do_not_guess_ownership():
    original = baseline()
    second = deepcopy(original["project_blocks"][0])
    second["id"] = "p2"
    original["project_blocks"].append(second)
    written = deepcopy(original)
    for block in written["project_blocks"]:
        block.pop("id")
    assert ResumeElevator._preserve_source_units(written, original) == ["project_blocks"]
    assert written["project_blocks"] == original["project_blocks"]


def test_ingest_and_composed_skills_no_longer_instruct_destructive_splitting():
    from jc.domain.role_families import get_playbook
    from jc.services.profile_structurer import ProfileStructurer
    from jc.services.profile_vision import ProfileVisionExtractor

    for prompt in (ProfileStructurer()._system_prompt, ProfileVisionExtractor()._system_prompt):
        assert "One accomplishment per" not in prompt
        assert "Do not split" in prompt
    prompt = ResumeElevator._compose_system_prompt(get_playbook("backend"), []).lower()
    assert "source units" in prompt
    assert "re-word, re-order, split or merge" not in prompt
    assert "re-rank bullets" not in prompt
    assert "split those apart" not in prompt


@pytest.mark.asyncio
async def test_text_ingest_validator_preserves_original_project_unit(monkeypatch):
    import json

    from jc.config import settings
    from jc.services.profile_structurer import ProfileStructurer

    class Router:
        def content_from_response(self, response):
            return json.dumps(
                {"projects": [{"id": "p1", "name": "订单改造", "highlights": [PROJECT]}]}
            )

        async def acompletion(self, *args, **kwargs):
            assert "Do not split" in kwargs["messages"][0]["content"]
            return kwargs["response_validator"](object())

    monkeypatch.setattr(settings, "jc_llm_enabled", True)
    monkeypatch.setattr("jc.services.profile_structurer.get_llm_router", lambda: Router())
    result = await ProfileStructurer().structure(text=PROJECT, source_file="fixture.txt")
    assert len(result.projects) == 1
    assert result.projects[0].highlights == [PROJECT]
