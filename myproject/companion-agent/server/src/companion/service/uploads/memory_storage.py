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

    async def presigned_put(self, *, key: str, content_type: str, ttl_seconds: int) -> str:
        # 占位格式；put_via_presigned 只认这个前缀（同 signed_url 的待遇）
        return f"memory-put://{key}?ttl={ttl_seconds}"

    async def put_via_presigned(self, *, url: str, data: bytes, content_type: str) -> bool:
        key = url.removeprefix("memory-put://").split("?", 1)[0]
        self._blobs[key] = (data, content_type)
        return True

    async def head_size(self, *, key: str) -> int | None:
        blob = self._blobs.get(key)
        return len(blob[0]) if blob else None

    async def delete(self, *, key: str) -> None:
        self._blobs.pop(key, None)

    async def get(self, *, key: str) -> bytes:
        """字节读取：与 ``ObjectStore`` 协议 / ``TosObjectStore.get`` 同签名。

        以前是个同步的 ``get(key) -> (bytes, str) | None`` 调试口——没有任何调用方
        用它，所以协议漂移一直没暴露；头像生成第一次走 ``UploadService.read_bytes``
        就会撞上。缺失抛 ``KeyError``（与 signed_url 同待遇）。
        """
        blob = self._blobs.get(key)
        if blob is None:
            raise KeyError(key)
        return blob[0]
