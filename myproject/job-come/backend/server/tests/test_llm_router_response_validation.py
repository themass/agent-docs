"""LLM router retries another endpoint when a successful HTTP response is unusable."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from jc.llm.router import LLMRouter


@pytest.mark.asyncio
async def test_response_validator_triggers_scenario_failover(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    config = tmp_path / "routing.yaml"
    config.write_text(
        """
scenarios:
  ingest:
    - model: openai/first
    - model: openai/second
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("JC_LLM_API_KEY", "test-key")
    calls: list[str] = []

    async def acompletion(**kwargs: object) -> object:
        model = str(kwargs["model"])
        calls.append(model)
        content = "" if model.endswith("first") else '{"ok": true}'
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=acompletion))
    router = LLMRouter(config)

    def parse(response: object) -> dict[str, bool]:
        content = router.content_from_response(response)
        if not content:
            raise ValueError("empty_model_response")
        return {"ok": True}

    assert await router.acompletion("ingest", messages=[], response_validator=parse) == {"ok": True}
    assert calls == ["openai/first", "openai/second"]


def test_content_from_response_handles_missing_and_block_content(tmp_path: Path) -> None:
    config = tmp_path / "routing.yaml"
    config.write_text("scenarios: {}\n", encoding="utf-8")
    router = LLMRouter(config)
    assert router.content_from_response(SimpleNamespace(choices=[])) == ""
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=[{"text": "{"}, {"text": "}"}]))]
    )
    assert router.content_from_response(response) == "{}"
