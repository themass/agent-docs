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
