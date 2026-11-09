"""内存对象存储：仅用于开发与测试。签名 URL 是占位格式，不可公开访问。"""

from __future__ import annotations


class InMemoryObjectStore:
    def __init__(self) -> None:
        self._blobs: dict[str, tuple[bytes, str]] = {}

    async def put(self, *, key: str, data: bytes, content_type: str) -> None:
        self._blobs[key] = (data, content_type)

    async def signed_url(self, *, key: str, ttl_seconds: int) -> str:
        if key not in self._blobs:
            raise KeyError(key)
        return f"memory://{key}?ttl={ttl_seconds}"

    async def delete(self, *, key: str) -> None:
        self._blobs.pop(key, None)

    def get(self, key: str) -> tuple[bytes, str] | None:
        return self._blobs.get(key)
