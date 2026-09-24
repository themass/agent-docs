"""Object storage — TOS when configured, local filesystem fallback for dev."""

from __future__ import annotations

from pathlib import Path

from jobcome.config import settings
from jobcome.storage_client import get_object_store


class StorageBackend:
    """Upload and read blobs by storage key."""

    def __init__(self) -> None:
        self._remote = settings.storage_remote_enabled
        if not self._remote:
            self._local_root = Path(settings.job_come_storage_local_dir).resolve()
            self._local_root.mkdir(parents=True, exist_ok=True)

    def put_object(self, key: str, body: bytes, *, content_type: str | None = None) -> str:
        if self._remote:
            return get_object_store().put_object(key, body, content_type=content_type)
        path = self._local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return key

    def get_object_bytes(self, key: str) -> bytes:
        if self._remote:
            return get_object_store().get_object_bytes(key)
        return self._local_path(key).read_bytes()

    def _local_path(self, key: str) -> Path:
        safe = key.lstrip("/").replace("..", "")
        return self._local_root / safe


_backend: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    global _backend
    if _backend is None:
        _backend = StorageBackend()
    return _backend
