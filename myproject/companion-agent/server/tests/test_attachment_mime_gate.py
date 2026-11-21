"""回合的附件 mime 闸门（P2-13）。

``_load_images`` 过去把消息里**每个** upload_id 无条件 base64 成 data URL 塞给模型——
在只有图片的年代成立，视频附件进来就不成立了：一段 25 MiB 的 MP4 会变成几十万 token
直接把回合打死。闸门按 ca_upload 的 mime 判定：非 image/* 一律跳过并记日志，
文字与图片照常进模型，不因为一条视频让整轮失败。
"""

from __future__ import annotations

from companion.agent.brain.port import TurnInputMessage
from companion.db.port import UploadRecord
from companion.service.chat.turn_runner import TurnInput, TurnRunner


class FakeUploads:
    def __init__(self, rows: dict[str, UploadRecord], blobs: dict[str, bytes]) -> None:
        self._rows = rows
        self._blobs = blobs
        self.read_ids: list[str] = []

    async def get_owned(self, *, owner_id: int, upload_id: str):
        row = self._rows.get(upload_id)
        return row if row and row.owner_id == owner_id else None

    async def read_bytes(self, *, record: UploadRecord) -> bytes:
        self.read_ids.append(record.id)
        return self._blobs[record.id]


def _record(upload_id: str, mime: str) -> UploadRecord:
    return UploadRecord(id=upload_id, owner_id=7, object_key=f"companion-qa/uploads/7/{upload_id}",
                        mime=mime, size=100, width=0, height=0, referenced=True,
                        created_at=None)  # type: ignore[arg-type]


def _runner(uploads: FakeUploads) -> TurnRunner:
    # _load_images 不碰控制面/消息/队列，闸门测试用 None 占位即可
    return TurnRunner(control=None, messages=None, queue=None, produce=None, uploads=uploads)


def _inp() -> TurnInput:
    return TurnInput(owner_id=7, session_id=1, character_id="linche", turn_id="t1",
                     owner="test:t1", text="", message_ids=[11])


async def test_video_attachment_is_skipped_but_image_still_reaches_the_model():
    uploads = FakeUploads(
        rows={"img1": _record("img1", "image/jpeg"), "vid1": _record("vid1", "video/mp4")},
        blobs={"img1": b"jpegbytes", "vid1": b"M" * 100_000},
    )
    runner = _runner(uploads)
    inputs = [TurnInputMessage(message_id=11, text="看这个", upload_ids=("img1", "vid1"))]

    result = await runner._load_images(_inp(), inputs)

    urls = result[11]
    assert len(urls) == 1 and urls[0].startswith("data:image/jpeg;base64,")
    assert all("video" not in u for u in urls)


async def test_message_with_only_video_gets_no_image_slot():
    uploads = FakeUploads(rows={"vid1": _record("vid1", "video/mp4")}, blobs={"vid1": b"M" * 10})
    runner = _runner(uploads)
    inputs = [TurnInputMessage(message_id=11, text="视频来了", upload_ids=("vid1",))]

    result = await runner._load_images(_inp(), inputs)

    assert 11 not in result


async def test_non_mp4_non_image_kinds_are_skipped_too():
    """闸门按「是不是图片」判定，不按「是不是视频」枚举——文件消息（application/pdf）
    将来接上中转通道时不会被当成图片 base64 进去。"""
    uploads = FakeUploads(
        rows={"pdf1": _record("pdf1", "application/pdf"), "img1": _record("img1", "image/png")},
        blobs={"pdf1": b"%PDF", "img1": b"pngbytes"},
    )
    runner = _runner(uploads)
    inputs = [TurnInputMessage(message_id=11, text="合同", upload_ids=("pdf1", "img1"))]

    result = await runner._load_images(_inp(), inputs)

    assert result[11] == ("data:image/png;base64," + __import__("base64").b64encode(b"pngbytes").decode(),)
