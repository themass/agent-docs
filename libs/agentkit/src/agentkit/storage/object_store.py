"""S3-compatible object storage (Volcengine TOS, Aliyun OSS, MinIO)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO

import boto3
from botocore.client import BaseClient, Config


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
