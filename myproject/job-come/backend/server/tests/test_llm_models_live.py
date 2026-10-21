"""Live ping of configured LLM gateway models.

Run: `JC_LLM_LIVE=1 pytest -q tests/test_llm_models_live.py`
"""

from __future__ import annotations

import os
import time

import httpx
import pytest

from jc.config import settings
from jc.llm.router import LLMRouter
from jc.paths import agent_file

TEXT_MODELS = [
    "deepseek-v4-flash",
    "claude-haiku-5-5",
    "gpt-6-1-sol",
]

VISION_MODELS = [
    "qwen-vl-ocr",
]


@pytest.mark.skipif(
    os.environ.get("JC_LLM_LIVE") != "1", reason="set JC_LLM_LIVE=1 to probe gateway"
)
@pytest.mark.parametrize("slug", TEXT_MODELS)
def test_llm_gateway_chat_completion(slug: str) -> None:
    base = settings.jc_llm_api_base.rstrip("/")
    started = time.monotonic()
    with httpx.Client(timeout=90.0) as client:
        response = client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {settings.jc_llm_api_key}"},
            json={
                "model": slug,
                "messages": [{"role": "user", "content": "Reply with exactly OK"}],
                "max_tokens": 64,
            },
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    body = response.text[:400]
    assert response.status_code == 200, f"{slug} HTTP {response.status_code} {elapsed_ms}ms {body}"
    data = response.json()
    content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
    used = data.get("model") or slug
    print(f"OK {slug} via={used} {elapsed_ms}ms {content.strip()[:80]!r}")
    assert content.strip(), f"{slug} empty content {elapsed_ms}ms"


@pytest.mark.skipif(
    os.environ.get("JC_LLM_LIVE") != "1", reason="set JC_LLM_LIVE=1 to probe gateway"
)
@pytest.mark.parametrize("slug", VISION_MODELS)
def test_llm_gateway_vision_model_listed(slug: str) -> None:
    key = settings.jc_llm_vision_api_key or settings.jc_llm_api_key
    base = (settings.jc_llm_vision_api_base or settings.jc_llm_api_base).rstrip("/")
    assert key, "set JC_LLM_VISION_API_KEY or JC_LLM_API_KEY"
    with httpx.Client(timeout=90.0) as client:
        response = client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": slug,
                "messages": [{"role": "user", "content": "Reply with exactly OK"}],
                "max_tokens": 64,
            },
        )
    assert response.status_code == 200, response.text[:400]


@pytest.mark.skipif(
    os.environ.get("JC_LLM_LIVE") != "1", reason="set JC_LLM_LIVE=1 to probe gateway"
)
@pytest.mark.asyncio
async def test_router_flash_scenario() -> None:
    router = LLMRouter(agent_file("llm", "routing.yaml"))
    response = await router.acompletion(
        "flash",
        messages=[{"role": "user", "content": "Reply with exactly OK"}],
        max_tokens=64,
    )
    text = router.content_from_response(response)
    assert text.strip()
