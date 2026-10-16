"""Legacy DB parse_error values must not reach the API client."""

from jc.services.ingest_user_messages import (
    USER_LLM_PARSE_UNAVAILABLE,
    public_parse_error,
)


def test_legacy_technical_error_is_sanitized() -> None:
    raw = (
        "LLM 解析全部失败，已回退占位数据。请检查 YUAI_API_KEY / 模型路由。详情："
        "文本结构化失败: All models failed for scenario ingest_fast: litellm.Bad"
    )
    assert public_parse_error(raw, ingest_mode="mock_fallback") == USER_LLM_PARSE_UNAVAILABLE


def test_known_message_passes_through() -> None:
    assert public_parse_error(USER_LLM_PARSE_UNAVAILABLE) == USER_LLM_PARSE_UNAVAILABLE
