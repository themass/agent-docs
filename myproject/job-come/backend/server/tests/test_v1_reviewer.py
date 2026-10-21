"""The pre-export reviewer: a verdict, or an honest absence of one.

Driven through a real `litellm.Router` with only the gateway faked, because the
thing most worth protecting here is the boundary between "the model found a
problem with the draft" and "we never got an answer" - and that boundary is
decided inside the call, by the response validator failing the chain over.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import fake_gateway, gateway_error, install_routing
from jc.models.enums import ReviewerStatus
from jc.services import resume_reviewer as module

#: The scenario the reviewer calls. Named here so a routing change that renames
#: it fails these tests rather than silently testing a scenario nobody uses.
_SCENARIO = "flash"


@pytest.fixture
def reviewer_chain(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> object:
    """Enable the reviewer and give its scenario a two-endpoint chain."""
    monkeypatch.setattr(module, "settings", SimpleNamespace(jc_llm_enabled=True))
    return install_routing(
        monkeypatch, tmp_path, _SCENARIO, ["openai/first", "openai/second"]
    )


def verdict(status: str, issues: list[dict[str, str]], summary: str = "ok") -> str:
    return json.dumps({"status": status, "issues": issues, "summary": summary})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "answer"),
    [
        # Unparseable: not JSON at all.
        ("invalid_json", "{broken"),
        # Parseable JSON in the wrong shape: `issues` must be a list of objects.
        ("invalid_issues", '{"status":"passed","issues":["wrong"]}'),
        # A status outside the contract is not a verdict we can act on.
        ("invalid_status", '{"status":"maybe","issues":[]}'),
        # Empty body behind a 200.
        ("empty", ""),
    ],
)
async def test_an_unreadable_answer_is_no_verdict_not_a_failed_resume(
    reviewer_chain, kind, answer
):
    """A response we cannot read says nothing about the draft, so it may not accuse it.

    Reporting these as FAILED told the user their resume had been rejected and --
    back when the verdict gated the download -- took the file away over a problem
    they did not cause and could not fix.

    Every endpoint is given the same bad answer, so this is also the assertion
    that a bad shape costs the *whole chain* before it becomes "no verdict":
    one endpoint answering badly must only cost that endpoint.
    """
    with fake_gateway({"first": answer, "second": answer}) as called:
        result = await module.ResumeReviewer().review(
            sections={"summary": "工作经历"},
            source_profile={"contact": {"name": "测试"}},
        )

    # The contract is checked inside the call, so a bad shape fails over.
    assert called == ["openai/first", "openai/second"]
    assert result.available is False
    assert result.status == ReviewerStatus.PENDING
    assert result.issues
    # Advisory only: a non-verdict must never be counted as a blocking finding.
    assert all(i.get("severity") == "warning" for i in result.issues)
    # The user is told what happened in their own language, not given a stack trace.
    assert result.notes and "质检" in result.notes


@pytest.mark.asyncio
async def test_one_bad_answer_costs_one_endpoint_not_the_review(reviewer_chain):
    """The reason the contract is checked inside the call rather than after it."""
    good = verdict("passed", [])
    with fake_gateway({"first": "{broken", "second": good}) as called:
        result = await module.ResumeReviewer().review(
            sections={"summary": "工作经历"},
            source_profile={"contact": {"name": "测试"}},
        )

    assert called == ["openai/first", "openai/second"]
    assert result.available is True
    assert result.status == ReviewerStatus.PASSED


@pytest.mark.asyncio
async def test_an_unreachable_gateway_is_no_verdict(reviewer_chain):
    """An outage is an ops problem; it must not be reported as a resume defect."""
    error = gateway_error("timeout")
    with fake_gateway({"first": error, "second": error}):
        result = await module.ResumeReviewer().review(
            sections={"summary": "工作经历"},
            source_profile={"contact": {"name": "测试"}},
        )

    assert result.available is False
    assert result.status == ReviewerStatus.PENDING
    assert all(i.get("severity") == "warning" for i in result.issues)
    assert result.notes and "质检" in result.notes


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["missing_source", "large_input"])
async def test_the_reviewer_declines_before_calling_when_it_cannot_judge(
    monkeypatch, kind
):
    """No facts to check against, or too much to check: decline, do not guess.

    Asserted without a chain installed, because the point is that no call is
    made at all - a model asked to verify a draft against nothing would invent
    findings.
    """
    monkeypatch.setattr(module, "settings", SimpleNamespace(jc_llm_enabled=True))

    def must_not_be_called() -> object:
        raise AssertionError("the reviewer must not call a model in this case")

    monkeypatch.setattr(module, "get_llm_router", must_not_be_called)

    sections = {"summary": "x" * 100001} if kind == "large_input" else {"summary": "工作经历"}
    result = await module.ResumeReviewer().review(
        sections=sections,
        source_profile=None if kind == "missing_source" else {"contact": {"name": "测试"}},
    )

    assert result.available is False
    assert result.status == ReviewerStatus.PENDING
    assert all(i.get("severity") == "warning" for i in result.issues)
    assert result.notes and "质检" in result.notes


@pytest.mark.asyncio
async def test_llm_disabled_is_not_a_verdict(monkeypatch):
    monkeypatch.setattr(module, "settings", SimpleNamespace(jc_llm_enabled=False))
    result = await module.ResumeReviewer().review(
        sections={"summary": "后端工程师"}, source_profile={"contact": {"name": "测试"}}
    )
    assert result.available is False
    assert result.status == ReviewerStatus.PENDING


@pytest.mark.asyncio
async def test_a_real_verdict_is_marked_available(reviewer_chain):
    """The flag must actually distinguish; a constant False would pass the tests above."""
    payload = verdict(
        "failed",
        [{"severity": "error", "field": "summary", "message": "档案无此事实"}],
        summary="有问题",
    )
    with fake_gateway({"first": payload}):
        result = await module.ResumeReviewer().review(
            sections={"summary": "后端工程师"},
            source_profile={"contact": {"name": "测试"}},
        )

    assert result.available is True
    assert result.status == ReviewerStatus.FAILED
    assert result.notes == "有问题"
    assert result.issues[0]["field"] == "summary"


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
async def test_only_error_severity_blocks_export(reviewer_chain, issues, expect_passed):
    """Advisory quality warnings must not lock a user out of exporting their resume."""
    with fake_gateway({"first": verdict("passed", issues)}):
        result = await module.ResumeReviewer().review(
            sections={"summary": "后端工程师"},
            source_profile={"contact": {"name": "测试"}},
        )

    expected = ReviewerStatus.PASSED if expect_passed else ReviewerStatus.FAILED
    assert result.status == expected
    # A real verdict either way: severity decides blocking, not availability.
    assert result.available is True
    # Issues are always surfaced to the user, blocking or not.
    assert len(result.issues) == len(issues)


@pytest.mark.asyncio
async def test_reviewer_omits_render_data_without_changing_facts_or_source(monkeypatch):
    import copy
    from unittest.mock import AsyncMock

    monkeypatch.setattr(module.settings, "jc_llm_enabled", True)
    router = SimpleNamespace(acompletion=AsyncMock(return_value={"status": "passed", "issues": []}),
                             chain_for=lambda scenario: [1, 2, 3])
    monkeypatch.setattr(module, "get_llm_router", lambda: router)
    sections = {"summary": "交付周期从25天缩短至8天", "header": {"photo_data_uri": "IMAGE"},
                "generation": {"debug": "INTERNAL"}}
    source = {"summary": "交付周期从25天缩短至8天", "contact": {"name": "张三", "photo": "IMAGE"},
              "meta": {"raw_text": "DUPLICATE"}}
    original = copy.deepcopy((sections, source))
    result = await module.ResumeReviewer().review(sections=sections, source_profile=source)
    assert result.available
    kwargs = router.acompletion.call_args.kwargs
    text = kwargs["messages"][1]["content"]
    assert all(value not in text for value in ["IMAGE", "INTERNAL", "DUPLICATE"])
    assert "交付周期从25天缩短至8天" in text and "张三" in text
    assert (sections, source) == original
    assert 0 < kwargs["timeout_seconds"] <= 25
    assert "max_tokens" not in kwargs  # Inherit the shared routing policy.


@pytest.mark.asyncio
async def test_reviewer_deadline_bounds_sdk_retries_and_cancels_call(monkeypatch):
    import asyncio

    monkeypatch.setattr(module, "settings", SimpleNamespace(
        jc_llm_enabled=True, jc_export_review_timeout_seconds=0.01,
        jc_export_review_attempt_timeout_seconds=0.005,
    ))
    stopped = asyncio.Event()

    async def hanging_call(*args, **kwargs):
        try:
            await asyncio.sleep(10)
        finally:
            stopped.set()

    monkeypatch.setattr(module, "get_llm_router", lambda: SimpleNamespace(
        acompletion=hanging_call, chain_for=lambda _: [1],
    ))
    result = await asyncio.wait_for(module.ResumeReviewer().review(
        sections={"summary": "工作经历"}, source_profile={"contact": {"name": "测试"}},
    ), 1)
    assert stopped.is_set()
    assert result.available is False
    assert result.status == ReviewerStatus.PENDING
    assert result.issues[0]["code"] == "reviewer_timeout"
