"""Preparing an artifact is not evidence of an actual application submission."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from agentkit.web.auth import UserActor
from pydantic import ValidationError

from jc.schemas.job import ApplyPipelineRequest, FitScoreResponse
from jc.services.apply_pipeline_service import ApplyPipelineService


def test_request_never_assumes_submission_and_requires_a_boolean():
    assert ApplyPipelineRequest(job_id="j").create_application is False
    assert ApplyPipelineRequest(job_id="j", create_application=True).create_application is True
    with pytest.raises(ValidationError):
        ApplyPipelineRequest(job_id="j", create_application="false")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "confirmed,status,expected",
    [(False, "done", False), (True, "done", True), (True, "failed", False)],
)
async def test_only_explicit_submission_and_success_register_application(
    confirmed, status, expected
):
    service = object.__new__(ApplyPipelineService)
    service._db = SimpleNamespace(commit=AsyncMock())
    service._jobs = SimpleNamespace(
        fit_score=AsyncMock(
            return_value=FitScoreResponse(
                job_id="j", score=80, recommendation="go", gaps=[], blockers=[]
            )
        )
    )
    service._resumes = SimpleNamespace(
        elevate=AsyncMock(
            return_value=SimpleNamespace(id="d", model_dump=Mock(return_value={"id": "d"}))
        ),
        export=AsyncMock(
            return_value=SimpleNamespace(
                id="e", status=status, model_dump=Mock(return_value={"id": "e", "status": status})
            )
        ),
    )
    service._applications = SimpleNamespace(
        mark_applied=AsyncMock(return_value=SimpleNamespace(id="a"))
    )
    service._job_store = SimpleNamespace(get_by_id=AsyncMock(return_value=None), save=AsyncMock())
    result = await service.run(
        "p",
        actor=UserActor(user_id="u", session_id="s"),
        body=ApplyPipelineRequest(job_id="j", create_application=confirmed),
    )
    assert result.application_id == ("a" if expected else None)
    assert service._applications.mark_applied.await_count == int(expected)
    assert service._db.commit.await_count == int(expected)
    if expected:
        assert service._applications.mark_applied.call_args.kwargs["resume_variant_id"] == "d"


@pytest.mark.asyncio
async def test_export_exception_never_registers_application():
    service = object.__new__(ApplyPipelineService)
    service._jobs = SimpleNamespace(
        fit_score=AsyncMock(
            return_value=FitScoreResponse(
                job_id="j", score=80, recommendation="go", gaps=[], blockers=[]
            )
        )
    )
    service._resumes = SimpleNamespace(
        elevate=AsyncMock(return_value=SimpleNamespace(id="d")),
        export=AsyncMock(side_effect=RuntimeError("render failed")),
    )
    service._applications = SimpleNamespace(mark_applied=AsyncMock())
    with pytest.raises(RuntimeError, match="render failed"):
        await service.run(
            "p",
            actor=UserActor(user_id="u", session_id="s"),
            body=ApplyPipelineRequest(job_id="j", create_application=True),
        )
    service._applications.mark_applied.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments,expected",
    [({}, False), ({"create_application": False}, False), ({"create_application": True}, True)],
)
async def test_mcp_dispatch_preserves_explicit_intent(monkeypatch, arguments, expected):
    from jc.mcp import handlers

    handler = AsyncMock(return_value={})
    monkeypatch.setitem(handlers.TOOL_HANDLERS, "jc_apply_pipeline", handler)
    await handlers.dispatch_tool(None, "jc_apply_pipeline", arguments)
    assert handler.call_args.kwargs["create_application"] is expected


def test_tool_and_handler_defaults_match_http_contract():
    import inspect

    from jc.agent.tool_catalog import tools_for_skill
    from jc.mcp.handlers import apply_pipeline

    tool = next(
        t["function"]
        for t in tools_for_skill("apply-pipeline")
        if t["function"]["name"] == "jc_apply_pipeline"
    )
    assert tool["parameters"]["properties"]["create_application"]["default"] is False
    assert inspect.signature(apply_pipeline).parameters["create_application"].default is False


@pytest.mark.asyncio
@pytest.mark.parametrize("archive_flag", [False, True])
async def test_mcp_review_is_advisory_like_http_export(archive_flag):
    from jc.mcp import interceptors

    request = SimpleNamespace(
        name="jc_apply_pipeline",
        args={
            "jc_profile_id": "p",
            "create_application": archive_flag,
        },
    )
    handler = AsyncMock(return_value={"export": {"status": "done"}})
    result = await interceptors.build_apply_pipeline_review_interceptor()(request, handler)
    assert result == {"export": {"status": "done"}}
    handler.assert_awaited_once_with(request)
