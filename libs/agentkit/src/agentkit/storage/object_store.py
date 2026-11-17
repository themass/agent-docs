"""S3-compatible object storage (Volcengine TOS, Aliyun OSS, MinIO)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO

import boto3
from botocore.client import BaseClient, Config
from botocore.exceptions import ClientError


@dataclass(frozen=True, slots=True)
class ObjectStoreConfig:
    endpoint: str
    bucket: str
    access_key: str
    secret_key: str
    region: str = "cn-beijing"
    force_path_style: bool = False


class ObjectStore:
    """Thin wrapper around boto3 S3 client for uploads and internal reads."""

    def __init__(self, config: ObjectStoreConfig) -> None:
        self._config = config
        addressing = "path" if config.force_path_style else "virtual"
        self._client: BaseClient = boto3.client(
            "s3",
            endpoint_url=config.endpoint,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            region_name=config.region,
            config=Config(s3={"addressing_style": addressing}),
        )

    @property
    def bucket(self) -> str:
        return self._config.bucket

    def put_object(
        self,
        key: str,
        body: bytes | BinaryIO,
        *,
        content_type: str | None = None,
    ) -> str:
        extra: dict[str, str] = {}
        if content_type:
            extra["ContentType"] = content_type
        self._client.put_object(Bucket=self._config.bucket, Key=key, Body=body, **extra)
        return key

    def get_object_bytes(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._config.bucket, Key=key)
        return response["Body"].read()

    def delete_object(self, key: str) -> None:
        self._client.delete_object(Bucket=self._config.bucket, Key=key)

    def presigned_get_url(self, key: str, *, expires_in: int = 900) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._config.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def presigned_put_url(
        self,
        key: str,
        *,
        content_type: str | None = None,
        expires_in: int = 600,
    ) -> str:
        """客户端直传用的 PUT 签名。

        只签一个 key、只给写权限：拿到 URL 的人不能 list、不能读、不能写别的 key。
        客户端必须原样带 ``Content-Type``（如果这里传了），因为它算进了签名。

        注意 S3 兼容签名**约束不了 Content-Length**：单文件上限要在业务侧校验，
        入口拦不住（见 shared-media-upload-and-storage.md §10）。
        """
        params: dict[str, str] = {"Bucket": self._config.bucket, "Key": key}
        if content_type:
            params["ContentType"] = content_type
        return self._client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    def head_object_size(self, key: str) -> int | None:
        """对象实际字节数；key 不存在返回 ``None``。

        业务侧用它做绑定时的"真的传上来了吗 + 多大"复核：presigned PUT 约束不了
        Content-Length，声明值只能在签发时当上限提示，权威值只有 HEAD 拿得到。
        """
        try:
            response = self._client.head_object(Bucket=self._config.bucket, Key=key)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound", "404 Not Found"}:
                return None
            raise
        return int(response["ContentLength"])

    def list_object_keys(
        self,
        prefix: str,
        *,
        max_keys: int = 1000,
        page_size: int = 1000,
    ) -> list[tuple[str, object]]:
        """列出 ``prefix`` 下最多 ``max_keys`` 个对象，返回 ``(key, last_modified)``。

        给对账 GC 用：只按前缀分页（S3 list 的原生形状），不做递归遍历之外的任何
        语义——哪些 key 该删是业务侧的事。
        """
        keys: list[tuple[str, object]] = []
        token: str | None = None
        while len(keys) < max_keys:
            kwargs: dict[str, object] = {
                "Bucket": self._config.bucket,
                "Prefix": prefix,
                "MaxKeys": min(page_size, max_keys - len(keys)),
            }
            if token:
                kwargs["ContinuationToken"] = token
            response = self._client.list_objects_v2(**kwargs)
            for entry in response.get("Contents", []):
                keys.append((entry["Key"], entry.get("LastModified")))
            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")
            if not token:
                break
        return keys
