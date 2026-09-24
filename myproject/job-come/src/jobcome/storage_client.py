"""Object storage factory for JobCome."""

from __future__ import annotations

from functools import lru_cache

from agentkit.storage import CdnConfig, CdnUrlSigner, ObjectStore, ObjectStoreConfig

from jobcome.config import settings


@lru_cache
def get_object_store() -> ObjectStore:
    return ObjectStore(
        ObjectStoreConfig(
            endpoint=settings.job_come_s3_endpoint,
            bucket=settings.job_come_s3_bucket,
            access_key=settings.job_come_s3_access_key,
            secret_key=settings.job_come_s3_secret_key,
            region=settings.job_come_s3_region,
            force_path_style=settings.job_come_s3_force_path_style,
        )
    )


@lru_cache
def get_cdn_signer() -> CdnUrlSigner | None:
    if not settings.job_come_cdn_sign_key:
        return None
    return CdnUrlSigner(
        CdnConfig(
            domain=settings.job_come_cdn_domain,
            sign_key=settings.job_come_cdn_sign_key,
            url_ttl_seconds=settings.job_come_download_url_ttl_sec,
        )
    )


def download_url_for_key(storage_key: str, *, ttl_seconds: int | None = None) -> str:
    """Return CDN signed URL for users; fall back to TOS presigned if CDN not configured."""
    signer = get_cdn_signer()
    if signer is not None:
        return signer.sign(storage_key, ttl_seconds=ttl_seconds)
    store = get_object_store()
    return store.presigned_get_url(
        storage_key,
        expires_in=ttl_seconds or settings.job_come_download_url_ttl_sec,
    )
