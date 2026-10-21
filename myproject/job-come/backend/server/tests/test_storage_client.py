"""Storage URL construction for local vs remote backends."""

from __future__ import annotations

from jc.storage_client import api_storage_object_url, download_url_for_key


def test_local_storage_uses_same_origin_api_url(monkeypatch) -> None:
    from jc import storage_client

    monkeypatch.setattr(storage_client.settings, "jc_s3_access_key", "")
    monkeypatch.setattr(storage_client.settings, "jc_s3_secret_key", "")
    monkeypatch.setattr(storage_client.settings, "jc_api_prefix", "/api/v1")

    key = "jc/dev/profiles/prof_1/export/expj_1.pdf"
    assert download_url_for_key(key) == api_storage_object_url(key)
    assert download_url_for_key(key).startswith("/api/v1/storage/objects/")
