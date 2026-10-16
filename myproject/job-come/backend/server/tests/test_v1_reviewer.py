from types import SimpleNamespace

import pytest

from jc.models.enums import ReviewerStatus
from jc.services import resume_reviewer as module


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['missing_source', 'invalid_json', 'invalid_issues', 'large_input'])
async def test_reviewer_fails_closed(monkeypatch, kind):
    monkeypatch.setattr(module, 'settings', SimpleNamespace(jc_llm_enabled=True))
    class Router:
        async def acompletion(self, *args, **kwargs):
            return None
        def content_from_response(self, response):
            return '{broken' if kind == 'invalid_json' else '{"status":"passed","issues":["wrong"]}'
    monkeypatch.setattr(module, 'get_llm_router', lambda: Router())
    sections = {'summary': 'x' * 100001} if kind == 'large_input' else {'summary': '工作经历'}
    result = await module.ResumeReviewer().review(sections=sections, source_profile=None if kind == 'missing_source' else {'contact': {'name': '测试'}})
    assert result.status == ReviewerStatus.FAILED
    assert result.issues


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("issues", "expect_passed"),
    [
        ([], True),
        ([{"severity": "warning", "field": "summary", "message": "表述偏空"}], True),
        (
            [
                {"severity": "warning", "field": "summary", "message": "表述偏空"},
                {"severity": "warning", "field": "x", "message": "缺少量化"},
            ],
            True,
        ),
        ([{"severity": "error", "field": "header", "message": "缺少联系方式"}], False),
        (
            [
                {"severity": "warning", "field": "a", "message": "措辞偏弱"},
                {"severity": "error", "field": "b", "message": "档案无此事实"},
            ],
            False,
        ),
        # Unknown or absent severity must fail closed rather than silently pass.
        ([{"field": "c", "message": "未标注严重级别"}], False),
        ([{"severity": "critical", "field": "d", "message": "无法核验"}], False),
    ],
)
async def test_only_error_severity_blocks_export(monkeypatch, issues, expect_passed):
    """Advisory quality warnings must not lock a user out of exporting their resume."""
    import json

    monkeypatch.setattr(module, "settings", SimpleNamespace(jc_llm_enabled=True))

    payload = json.dumps({"status": "passed", "issues": issues, "summary": "ok"})

    class Router:
        async def acompletion(self, *args, **kwargs):
            return None

        def content_from_response(self, response):
            return payload

    monkeypatch.setattr(module, "get_llm_router", lambda: Router())

    result = await module.ResumeReviewer().review(
        sections={"summary": "后端工程师"},
        source_profile={"contact": {"name": "测试"}},
    )

    expected = ReviewerStatus.PASSED if expect_passed else ReviewerStatus.FAILED
    assert result.status == expected
    # Issues are always surfaced to the user, blocking or not.
    assert len(result.issues) == len(issues)
