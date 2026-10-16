"""TOS integration — skipped when AK/SK not configured."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from jc.config import settings
from jc.main import app
from jc.storage_client import get_object_store

pytestmark = pytest.mark.skipif(
    os.environ.get("JC_RUN_REMOTE_TESTS") != "1" or not settings.storage_remote_enabled,
    reason="Requires explicit JC_RUN_REMOTE_TESTS=1 and dedicated integration resources",
)


@pytest.mark.asyncio
async def test_profile_upload_stores_object_in_tos() -> None:
    get_object_store.cache_clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("resume_test.pdf", b"%PDF-1.4 integration", "application/pdf")}
        response = await client.post("/api/v1/profiles/upload", files=files)
        assert response.status_code == 200
        payload = response.json()
        storage_key = payload["sources"][0]["storage_key"]
        assert storage_key.startswith("jc/dev/profiles/")
        store = get_object_store()
        try:
            body = store.get_object_bytes(storage_key)
            assert body.startswith(b"%PDF")
        finally:
            store.delete_object(storage_key)
