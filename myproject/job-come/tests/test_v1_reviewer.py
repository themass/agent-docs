from types import SimpleNamespace

import pytest

from jobcome.models.enums import ReviewerStatus
from jobcome.services import resume_reviewer as module


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['missing_source', 'invalid_json', 'invalid_issues', 'large_input'])
async def test_reviewer_fails_closed(monkeypatch, kind):
    monkeypatch.setattr(module, 'settings', SimpleNamespace(job_come_llm_enabled=True))
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
