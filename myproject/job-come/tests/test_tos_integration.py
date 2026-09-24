"""TOS integration — skipped when AK/SK not configured."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from jobcome.config import settings
from jobcome.main import app
from jobcome.storage_client import get_object_store

pytestmark = pytest.mark.skipif(
    not settings.storage_remote_enabled,
    reason="JOB_COME_S3_ACCESS_KEY / SECRET_KEY not set",
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
        store = get_object_store()
        try:
            body = store.get_object_bytes(storage_key)
            assert body.startswith(b"%PDF")
        finally:
            store.delete_object(storage_key)
