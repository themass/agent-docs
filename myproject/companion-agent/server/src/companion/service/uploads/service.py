"""上传服务（O §5）：校验 → 处理 → 存私有桶 → 记录。

校验与图片规范化的实现在 ``agentkit.storage.media``（共用，另外几个应用走同一条链路）；
这里只负责「这条记录属于谁」「key 怎么排」「按 id 读回来」。

回合引用 upload_id 时由调用方校验归属（这里提供 get_owned，别人的 id 返回 None）。
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentkit.storage.media import (
    ImageLimits,
    MediaStore,
    Processed,
    UploadRejected,
    check_size,
    detect_type,
    normalize_image,
)

from companion.db.port import UploadRecord
from companion.service.uploads.objects_port import ObjectStore
from companion.agent.util.ids import new_ulid

SIGNED_URL_TTL = 300  # 5 分钟（O §5）


class UploadService:
    def __init__(self, *, objects: ObjectStore, records, normalize=None, clock=lambda: datetime.now(UTC),
                 key_prefix: str = "", limits: ImageLimits = ImageLimits()) -> None:
        self._objects = objects
        # 共用的 TOS 桶：生产用 companion/，测试用 companion-test/
        self._key_prefix = key_prefix.strip("/")
        if self._key_prefix:
            self._key_prefix += "/"
        self._records = records
        # normalize 参数保留给测试注入；正常走共用实现。
        self._normalize = normalize or (lambda raw: normalize_image(raw, limits))
        self._limits = limits
        self._clock = clock

    @property
    def media(self) -> MediaStore:
        """按前缀存取的共用包装（agentkit）。产品侧只在这上面做归属判断。"""
        return MediaStore(self._objects, key_prefix=self._key_prefix)

    async def accept(self, *, owner_id: int, data: bytes) -> UploadRecord:
        check_size(data, self._limits)
        if detect_type(data[:16]) is None:
            raise UploadRejected("unsupported file type")
        upload_id = new_ulid()
        # 统一输出 JPEG，key 不依赖原始扩展名
        key = f"{self._key_prefix}uploads/{owner_id}/{upload_id}.jpg"
        processed: Processed = self._normalize(data)
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

    async def read_bytes(self, *, record: UploadRecord) -> bytes:
        """按记录直接读字节，给模型用（不经签名 URL，见 ``TosObjectStore.get``）。

        调用方**必须**先 ``get_owned`` 过一遍归属；这里拿到的已经是被授权的那条记录。
        """
        return await self._objects.get(key=record.object_key)

    async def delete_object(self, *, key: str) -> None:
        """删对象（不做归属判断——调用方拿着的是账本里的 key，如头像源图的 TTL 清理）。

        与聊天附件的删除不同，这里没有「消息还引用着」的问题：头像结果只在换掉时删、
        源图只在 TTL 到点时删，两边都先确认过没人再要它。
        """
        await self._objects.delete(key=key)

    async def delete_record(self, *, owner_id: int, upload_id: str) -> None:
        """删 ca_upload 行（按归属，别人的 id 删不到）。对象应先删掉再走到这一步。"""
        await self._records.delete_owned(owner_id=owner_id, upload_id=upload_id)
