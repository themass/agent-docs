"""Regression coverage for controlled LLM profile-structure failures."""


import pytest

from jc.services.profile_structurer import ProfileStructureError, parse_profile_json


def test_parse_profile_json_accepts_markdown_fence() -> None:
    assert parse_profile_json("```json\n{\"contact\": {}}\n```") == {"contact": {}}



@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ("", "empty_model_response"),
        ("\n  \t", "empty_model_response"),
        ("not valid json", "invalid_json_response"),
        ("[]", "invalid_json_object"),
    ],
)
def test_parse_profile_json_returns_safe_failure_codes(content: str, reason: str) -> None:
    with pytest.raises(ProfileStructureError, match=reason):
        parse_profile_json(content)


@pytest.mark.asyncio
async def test_profile_structurer_normalizes_unknown_required_text_to_empty(monkeypatch):
    from jc.config import settings
    from jc.services.profile_structurer import ProfileStructurer

    class Router:
        def content_from_response(self, response):
            return (
                '{"experiences":[{"id":"e","company":"公司",'
                '"title":null,"start_date":"2020-01"}]}'
            )

        async def acompletion(self, *args, **kwargs):
            return kwargs["response_validator"](object())

    monkeypatch.setattr(settings, "jc_llm_enabled", True)
    monkeypatch.setattr("jc.services.profile_structurer.get_llm_router", lambda: Router())
    profile = await ProfileStructurer().structure(text="真实简历文字", source_file="resume.pdf")
    assert profile.experiences[0].title == ""


def test_profile_structure_error_does_not_contain_resume_content() -> None:
    secret_resume_line = "private@example.com"
    with pytest.raises(ProfileStructureError) as caught:
        parse_profile_json(secret_resume_line)
    assert secret_resume_line not in str(caught.value)


@pytest.mark.asyncio
async def test_profile_structurer_rejects_invalid_schema_without_exposing_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jc.config import settings
    from jc.services.profile_structurer import ProfileStructurer

    class Router:
        def content_from_response(self, response: object) -> str:
            return "{}"

        async def acompletion(self, *args: object, **kwargs: object) -> object:
            validator = kwargs["response_validator"]
            return validator(object())

    monkeypatch.setattr(settings, "jc_llm_enabled", True)
    monkeypatch.setattr("jc.services.profile_structurer.get_llm_router", lambda: Router())

    # An empty profile is valid today, so provide an invalid enum to force schema validation.
    class InvalidRouter(Router):
        def content_from_response(self, response: object) -> str:
            return (
                '{"experiences":[{"id":"e","company":"c","title":"t",'
                '"start_date":"2020-01","confidence":"bad"}]}'
            )

    monkeypatch.setattr("jc.services.profile_structurer.get_llm_router", lambda: InvalidRouter())
    with pytest.raises(ProfileStructureError, match="invalid_profile_schema"):
        await ProfileStructurer().structure(text="Candidate text", source_file="resume.docx")


@pytest.mark.asyncio
async def test_profile_structurer_reports_transport_failure_distinctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fallback-chain exhaustion (network/timeout/auth) is not a schema problem.

    Collapsing both into "invalid_profile_schema" sends debugging effort at the
    prompt when the real fault is the gateway being unreachable.
    """
    from jc.config import settings
    from jc.services.profile_structurer import ProfileStructurer

    class FailingRouter:
        def content_from_response(self, response: object) -> str:
            raise AssertionError("should not be called when acompletion itself fails")

        async def acompletion(self, *args: object, **kwargs: object) -> object:
            raise RuntimeError("connection error: every endpoint in the chain failed")

    monkeypatch.setattr(settings, "jc_llm_enabled", True)
    monkeypatch.setattr("jc.services.profile_structurer.get_llm_router", lambda: FailingRouter())

    with pytest.raises(ProfileStructureError, match="llm_call_failed"):
        await ProfileStructurer().structure(text="Candidate text", source_file="resume.docx")


@pytest.mark.asyncio
async def test_profile_structurer_uses_buffered_stream_and_rejects_empty_profile(monkeypatch):
    from jc.config import settings
    from jc.services.profile_structurer import ProfileStructurer

    class EmptyRouter:
        def content_from_response(self, response):
            return "{}"

        async def acompletion(self, *args, **kwargs):
            assert kwargs["buffered_stream"] is True
            return kwargs["response_validator"](object())

    monkeypatch.setattr(settings, "jc_llm_enabled", True)
    monkeypatch.setattr("jc.services.profile_structurer.get_llm_router", lambda: EmptyRouter())
    with pytest.raises(ProfileStructureError, match="empty_profile_response"):
        await ProfileStructurer().structure(text="真实简历文字", source_file="resume.pdf")


@pytest.mark.asyncio
async def test_profile_structurer_preserves_timeout_category(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from jc.config import settings
    from jc.services.profile_structurer import ProfileStructurer

    monkeypatch.setattr(settings, "jc_llm_enabled", True)
    monkeypatch.setattr("jc.services.profile_structurer.get_llm_router", lambda: SimpleNamespace(
        acompletion=AsyncMock(side_effect=TimeoutError()),
    ))
    with pytest.raises(ProfileStructureError, match="llm_timeout"):
        await ProfileStructurer().structure(text="真实简历文字", source_file="resume.pdf")


@pytest.mark.asyncio
async def test_text_generation_budget_is_separate_from_idle_budget(monkeypatch):
    from jc.config import settings
    from jc.services.profile_structurer import ProfileStructurer

    class Router:
        @staticmethod
        def content_from_response(response):
            return '{"contact":{"name":"测试"}}'

        async def acompletion(self, *args, **kwargs):
            assert kwargs["timeout_seconds"] == 25
            assert kwargs["stream_attempt_timeout_seconds"] == 30
            return kwargs["response_validator"](object())

    monkeypatch.setattr(settings, "jc_llm_enabled", True)
    monkeypatch.setattr(settings, "jc_ingest_attempt_timeout_seconds", 25)
    monkeypatch.setattr(settings, "jc_ingest_stream_attempt_seconds", 30)
    monkeypatch.setattr("jc.services.profile_structurer.get_llm_router", lambda: Router())
    profile = await ProfileStructurer().structure(text="真实文字", source_file="a.pdf")
    assert profile.contact.name == "测试"
