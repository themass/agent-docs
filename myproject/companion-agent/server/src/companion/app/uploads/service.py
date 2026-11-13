"""上传服务（O §5）：校验 → 处理 → 存私有桶 → 记录。

回合引用 upload_id 时由调用方校验归属（这里提供 get_owned，别人的 id 返回 None）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from companion.chat.ids import new_ulid
from companion.domain.uploads.policy import UploadRejected, check_size, detect_type
from companion.ports.objects import ObjectStore

SIGNED_URL_TTL = 300  # 5 分钟（O §5）


@dataclass(frozen=True)
class UploadRecord:
    id: str
    owner_id: int
    object_key: str
    mime: str
    size: int
    width: int
    height: int
    referenced: bool
    created_at: datetime


class UploadService:
    def __init__(self, *, objects: ObjectStore, records, normalize, clock=lambda: datetime.now(UTC),
                 key_prefix: str = "") -> None:
        self._objects = objects
        self._key_prefix = key_prefix  # 共用的 TOS 桶：生产用 companion/，测试用 companion-test/
        self._records = records
        self._normalize = normalize
        self._clock = clock

    async def accept(self, *, owner_id: int, data: bytes) -> UploadRecord:
        check_size(data)
        mime = detect_type(data[:16])
        if mime is None:
            raise UploadRejected("unsupported file type")
        processed = self._normalize(data)
        upload_id = new_ulid()
        key = f"{self._key_prefix}uploads/{owner_id}/{upload_id}.jpg"  # 统一输出 JPEG，key 不依赖原始扩展名
        await self._objects.put(key=key, data=processed.data, content_type="image/jpeg")
        record = UploadRecord(id=upload_id, owner_id=owner_id, object_key=key, mime="image/jpeg",
                              size=len(processed.data), width=processed.width, height=processed.height,
                              referenced=False, created_at=self._clock())
        await self._records.create(record)
        return record

    async def get_owned(self, *, owner_id: int, upload_id: str) -> UploadRecord | None:
        return await self._records.get_owned(owner_id=owner_id, upload_id=upload_id)

    async def read_url(self, *, owner_id: int, upload_id: str) -> str | None:
        record = await self.get_owned(owner_id=owner_id, upload_id=upload_id)
        if record is None:
            return None
        return await self._objects.signed_url(key=record.object_key, ttl_seconds=SIGNED_URL_TTL)
