"""客户端直传（ADR-011 同款）：签发、绑定、分流。

覆盖 job-come 同名方案的测试口径：归属 404 / 重复绑定 409 / 过期 410 / 未 PUT 412 /
超限 413，以及「中转通道的行不走直传状态机」。key 必须按 owner 分区、绑定后 size=实际值。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from companion.db.port import UploadRecord
from companion.service.uploads.direct import (
    MAX_BYTES_CHAT_IMAGE,
    DirectRejected,
    DirectUploadService,
)
from companion.service.uploads.memory_storage import InMemoryObjectStore

NOW = datetime(2026, 11, 18, 10, 0, tzinfo=UTC)


class MemoryUploadStore:
    """ca_upload 的内存替身：语义对齐 SqlUploadStore 的三个方法。"""

    def __init__(self) -> None:
        self.rows: dict[str, UploadRecord] = {}

    async def create(self, record: UploadRecord) -> None:
        self.rows[record.id] = record

    async def get_owned(self, *, owner_id: int, upload_id: str) -> UploadRecord | None:
        row = self.rows.get(upload_id)
        return row if row and row.owner_id == owner_id else None

    async def mark_bound(self, *, upload_id: str, actual_size: int) -> None:
        row = self.rows[upload_id]
        self.rows[upload_id] = UploadRecord(**{**row.__dict__, "size": actual_size, "referenced": True})


def _service() -> tuple[DirectUploadService, MemoryUploadStore, InMemoryObjectStore]:
    store = MemoryUploadStore()
    objects = InMemoryObjectStore()
    service = DirectUploadService(objects=objects, records=store, clock=lambda: NOW,
                                  key_prefix="companion-qa")
    return service, store, objects


async def _signed(service: DirectUploadService, owner: int = 7, size: int = 100_000) -> dict:
    return await service.sign(owner_id=owner, scene="chat-image", content_type="image/jpeg",
                              size_bytes=size)


# ---------------------------------------------------------------- 签发


async def test_sign_returns_single_key_put_credential_and_preregisters_row():
    service, store, _ = _service()
    signed = await _signed(service)

    assert signed["upload"]["method"] == "PUT"
    assert signed["upload"]["headers"] == {"Content-Type": "image/jpeg"}
    assert signed["upload"]["url"].startswith("memory-put://")
    # key 纪律：<env>/uploads/<owner>/<scene>/<yyyy>/<mm>/<dd>/<id>.<ext>，含 owner 分区
    key = signed["object_key"]
    env, uploads, owner_seg, scene, yyyy, mm, dd, name = key.split("/")
    assert (env, uploads, owner_seg, scene) == ("companion-qa", "uploads", "7", "chat-image")
    assert (yyyy, mm, dd) == ("2026", "11", "18") and name.endswith(".jpg")
    # upload_id 就是 key 的文件名（去扩展名），ca_upload.id 放得下
    assert signed["upload_id"] == name.removesuffix(".jpg") and len(signed["upload_id"]) == 26
    # 预登记行：size=0（未绑定），mime 以签发记录为准
    row = store.rows[signed["upload_id"]]
    assert (row.owner_id, row.size, row.mime) == (7, 0, "image/jpeg")


async def test_sign_rejects_bad_scene_type_and_size():
    service, _, _ = _service()
    with pytest.raises(DirectRejected) as exc:
        await service.sign(owner_id=7, scene="avatar", content_type="image/jpeg", size_bytes=100)
    assert exc.value.code == "SCENE_NOT_ALLOWED"
    with pytest.raises(DirectRejected) as exc:
        await service.sign(owner_id=7, scene="chat-image", content_type="image/gif", size_bytes=100)
    assert exc.value.code == "CONTENT_TYPE_NOT_ALLOWED"
    with pytest.raises(DirectRejected) as exc:
        await service.sign(owner_id=7, scene="chat-image", content_type="image/jpeg",
                           size_bytes=MAX_BYTES_CHAT_IMAGE + 1)
    assert exc.value.code == "SIZE_NOT_ALLOWED"
    with pytest.raises(DirectRejected) as exc:
        await service.sign(owner_id=7, scene="chat-image", content_type="image/jpeg", size_bytes=0)
    assert exc.value.code == "SIZE_NOT_ALLOWED"


# ---------------------------------------------------------------- 绑定


async def test_bind_happy_path_records_actual_size():
    service, store, objects = _service()
    signed = await _signed(service)
    await objects.put_via_presigned(url=signed["upload"]["url"], data=b"x" * 222_222,
                                    content_type="image/jpeg")
    await service.bind(owner_id=7, upload_id=signed["upload_id"])
    assert store.rows[signed["upload_id"]].size == 222_222


async def test_bind_foreign_upload_is_not_found():
    service, _, objects = _service()
    signed = await _signed(service, owner=7)
    await objects.put_via_presigned(url=signed["upload"]["url"], data=b"x" * 10, content_type="image/jpeg")
    with pytest.raises(DirectRejected) as exc:
        await service.bind(owner_id=8, upload_id=signed["upload_id"])
    assert exc.value.code == "KEY_NOT_FOUND"


async def test_bind_never_put_is_412():
    service, _, _ = _service()
    signed = await _signed(service)
    with pytest.raises(DirectRejected) as exc:
        await service.bind(owner_id=7, upload_id=signed["upload_id"])
    assert exc.value.code == "KEY_NOT_PUT"


async def test_bind_oversize_is_rejected():
    service, _, objects = _service()
    signed = await _signed(service, size=1000)
    await objects.put_via_presigned(url=signed["upload"]["url"],
                                    data=b"x" * (MAX_BYTES_CHAT_IMAGE + 1), content_type="image/jpeg")
    with pytest.raises(DirectRejected) as exc:
        await service.bind(owner_id=7, upload_id=signed["upload_id"])
    assert exc.value.code == "SIZE_NOT_ALLOWED"


async def test_bind_twice_is_conflict():
    service, _, objects = _service()
    signed = await _signed(service)
    await objects.put_via_presigned(url=signed["upload"]["url"], data=b"x" * 50, content_type="image/jpeg")
    await service.bind(owner_id=7, upload_id=signed["upload_id"])
    with pytest.raises(DirectRejected) as exc:
        await service.bind(owner_id=7, upload_id=signed["upload_id"])
    assert exc.value.code == "KEY_ALREADY_BOUND"


async def test_bind_after_ttl_is_expired():
    store = MemoryUploadStore()
    objects = InMemoryObjectStore()
    moments = [NOW]
    service = DirectUploadService(objects=objects, records=store, clock=lambda: moments[0],
                                  key_prefix="companion-qa")
    signed = await _signed(service)
    await objects.put_via_presigned(url=signed["upload"]["url"], data=b"x" * 50, content_type="image/jpeg")
    moments[0] = NOW + timedelta(minutes=11)
    with pytest.raises(DirectRejected) as exc:
        await service.bind(owner_id=7, upload_id=signed["upload_id"])
    assert exc.value.code == "KEY_EXPIRED"


async def test_relay_row_passes_bind_untouched():
    """中转通道（POST /v1/uploads）的行不满足直传 key 形状：bind 必须原样放行，
    否则老客户端的每一次发图都会被直传校验误伤。"""
    service, store, _ = _service()
    relay = UploadRecord(id="01" + "J" * 24, owner_id=7, object_key="companion-qa/uploads/7/01J.jpg",
                         mime="image/jpeg", size=1234, width=10, height=10, referenced=False, created_at=NOW)
    await store.create(relay)
    await service.bind(owner_id=7, upload_id=relay.id)  # 不抛
    assert store.rows[relay.id].size == 1234
