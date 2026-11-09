"""对象存储端口（O §5）：私有桶，只通过签名 URL 读取。"""

from __future__ import annotations

from typing import Protocol


class ObjectStore(Protocol):
    async def put(self, *, key: str, data: bytes, content_type: str) -> None: ...
    async def signed_url(self, *, key: str, ttl_seconds: int) -> str: ...
    async def delete(self, *, key: str) -> None: ...
