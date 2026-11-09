"""阿里云 OSS 私有桶适配（O §5）。

SDK 与真实桶尚未接入，这里只声明接口并明确失败，避免在没有配置的环境里假装上传成功。
接入时实现 put / signed_url / delete，其余代码不变。
"""

from __future__ import annotations


class OssNotConfigured(RuntimeError):
    pass


class OssObjectStore:
    def __init__(self, *, bucket: str, endpoint: str, access_key_env: str) -> None:
        self._bucket = bucket
        self._endpoint = endpoint
        self._access_key_env = access_key_env

    async def put(self, *, key: str, data: bytes, content_type: str) -> None:
        raise OssNotConfigured("OSS adapter is not wired yet")

    async def signed_url(self, *, key: str, ttl_seconds: int) -> str:
        raise OssNotConfigured("OSS adapter is not wired yet")

    async def delete(self, *, key: str) -> None:
        raise OssNotConfigured("OSS adapter is not wired yet")
