"""Object storage factory for JC."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote

from agentkit.storage import CdnConfig, CdnUrlSigner, ObjectStore, ObjectStoreConfig

from jc.config import settings


def api_storage_object_url(storage_key: str) -> str:
    """Same-origin URL for authenticated download when blobs live on local disk."""
    prefix = settings.jc_api_prefix.rstrip("/")
    safe_key = quote(storage_key.lstrip("/"), safe="/")
    return f"{prefix}/storage/objects/{safe_key}"


@lru_cache
def get_object_store() -> ObjectStore:
    return ObjectStore(
        ObjectStoreConfig(
            endpoint=settings.jc_s3_endpoint,
            bucket=settings.jc_s3_bucket,
            access_key=settings.jc_s3_access_key,
            secret_key=settings.jc_s3_secret_key,
            region=settings.jc_s3_region,
            force_path_style=settings.jc_s3_force_path_style,
        )
    )


@lru_cache
def get_cdn_signer() -> CdnUrlSigner | None:
    if not settings.jc_cdn_sign_key:
        return None
    return CdnUrlSigner(
        CdnConfig(
            domain=settings.jc_cdn_domain,
            sign_key=settings.jc_cdn_sign_key,
            url_ttl_seconds=settings.jc_download_url_ttl_sec,
        )
    )


def download_url_for_key(storage_key: str, *, ttl_seconds: int | None = None) -> str:
    """Return a user-fetchable URL: CDN/TOS when remote storage is on, else same-origin API."""
    if not settings.storage_remote_enabled:
        return api_storage_object_url(storage_key)
    signer = get_cdn_signer()
    if signer is not None:
        return signer.sign(storage_key, ttl_seconds=ttl_seconds)
    store = get_object_store()
    return store.presigned_get_url(
        storage_key,
        expires_in=ttl_seconds or settings.jc_download_url_ttl_sec,
    )
