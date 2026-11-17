"""火山引擎 TOS 私有桶（S3 兼容接口），与 job-come 同一套（libs/agentkit/storage/object_store.py）。

- 虚拟主机风格寻址（TOS 的 S3 接口要求，不能用路径风格）；
- 读取只给预签名 URL（O §5：5 分钟），桶本身保持私有；
- boto3 是同步客户端，调用放到线程里，不阻塞事件循环。

未配置时构造即失败（fail-closed）：不允许在没有真实桶的环境里假装上传成功。
"""

from __future__ import annotations

import asyncio
from typing import Any

import boto3
from botocore.config import Config


class TosNotConfigured(RuntimeError):
    pass


class TosObjectStore:
    def __init__(self, *, endpoint: str, bucket: str, access_key: str, secret_key: str,
                 region: str = "cn-beijing", client: Any | None = None) -> None:
        if not (endpoint and bucket and access_key and secret_key):
            raise TosNotConfigured("TOS endpoint, bucket and credentials are required")
        self._bucket = bucket
        self._client = client or boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(s3={"addressing_style": "virtual"}),
        )

    async def put(self, *, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object, Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    async def get(self, *, key: str) -> bytes:
        """按 key 直接读字节（AK/SK 鉴权，走内网/公网 SDK 调用，不经签名 URL）。

        模型看图和内部转存都走这条：签名 URL 是 bearer secret，进模型请求或日志就等于外泄。
        """
        def _read() -> bytes:
            return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

        return await asyncio.to_thread(_read)

    async def signed_url(self, *, key: str, ttl_seconds: int) -> str:
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=ttl_seconds,
        )

    async def delete(self, *, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)

    def check_bucket(self) -> None:
        """启动自检：HEAD 一次桶。凭据/桶名/端点任一配错都会在这里抛，而不是等第一次上传变 500。

        同步调用（启动阶段，不在事件循环里）；botocore 的重试策略已把真正的鉴权错误直接抛出。
        """
        self._client.head_bucket(Bucket=self._bucket)
