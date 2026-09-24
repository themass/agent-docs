"""Agent turn finalization — assistant bubble must survive tool-only turns."""

from __future__ import annotations

from jobcome.adapters.deerflow_harness_client import _extract_text
from jobcome.services.agent_service import _finalize_assistant_content


def test_extract_text_from_blocks() -> None:
    assert _extract_text([{"type": "text", "text": "你好"}]) == "你好"
    assert _extract_text([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "ab"


def test_finalize_prefers_streamed_tokens() -> None:
    assert _finalize_assistant_content(["我是", "助手"], True) == "我是助手"


def test_finalize_tool_only_turn_gets_placeholder() -> None:
    assert _finalize_assistant_content([], True) == "处理完成。如需继续，请描述下一步需求。"


def test_finalize_empty_turn_returns_none() -> None:
    assert _finalize_assistant_content([], False) is None
