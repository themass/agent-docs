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
