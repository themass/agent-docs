"""Agent message content builder tests."""

from __future__ import annotations

from jobcome.agent.message_content import build_user_message_content, message_has_images
from jobcome.agent.reply_locale import normalize_reply_locale, reply_language_instruction
from jobcome.schemas.agent import AgentAttachment


def test_build_text_only_message() -> None:
    content = build_user_message_content("hello", [])
    assert content == "hello"


def test_build_multimodal_message() -> None:
    content = build_user_message_content(
        "see image",
        [
            AgentAttachment(
                kind="image",
                name="jd.png",
                data_url="data:image/png;base64,abc",
            )
        ],
    )
    assert isinstance(content, list)
    assert message_has_images(content)
    assert content[0]["type"] == "text"


def test_reply_locale_defaults_to_chinese() -> None:
    assert normalize_reply_locale(None) == "zh-CN"
    assert "简体中文" in reply_language_instruction("zh-CN")
    assert "禁止用英文自我介绍" in reply_language_instruction("zh-CN")
    assert "English" in reply_language_instruction("en-US")
