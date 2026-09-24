"""Live ping of configured YuAI text models. Run: JOB_COME_LLM_LIVE=1 pytest -q tests/test_llm_models_live.py"""

from __future__ import annotations

import os
import time

import httpx
import pytest

from jobcome.config import settings
from jobcome.llm.router import LLMRouter

MODELS = [
    "bt-deepseek-v4-flash",
    "bt-deepseek-v4-pro",
    "mt-gpt-5-6-terra",
    "mt-gpt-6-astra",
]


@pytest.mark.skipif(os.environ.get("JOB_COME_LLM_LIVE") != "1", reason="set JOB_COME_LLM_LIVE=1 to probe YuAI")
@pytest.mark.parametrize("slug", MODELS)
def test_yuai_chat_completion(slug: str) -> None:
    base = settings.yuai_api_base.rstrip("/")
    started = time.monotonic()
    with httpx.Client(timeout=90.0) as client:
        response = client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {settings.yuai_api_key}"},
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


@pytest.mark.skipif(os.environ.get("JOB_COME_LLM_LIVE") != "1", reason="set JOB_COME_LLM_LIVE=1 to probe YuAI")
@pytest.mark.asyncio
async def test_router_flash_scenario() -> None:
    from pathlib import Path

    router = LLMRouter(Path(__file__).resolve().parents[1] / "deploy" / "llm" / "routing.yaml")
    response = await router.acompletion(
        "flash",
        messages=[{"role": "user", "content": "Reply with exactly OK"}],
        max_tokens=64,
    )
    text = router.content_from_response(response)
    assert text.strip()
