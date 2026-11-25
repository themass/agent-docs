"""生成与应用的编排：归属、配额、TTL 账本、provider 调用、换头像。

错误语义与端侧 ``AvatarGenRemote.mapStatus`` 一一对齐（这是契约的一部分，改之前先看那边）：

.. code-block:: text

    HTTP 401 / 403          → 端侧 NOT_LOGGED_IN    （由 current_user 依赖产生，这里不管）
    HTTP 413 / 415 / 422    → 端侧 BAD_IMAGE        （源图不存在 / 不是本人的 / style 非法）
    HTTP 429                → 端侧 QUOTA            （每日生成配额用尽）
    HTTP 502                → 端侧 SERVICE_UNAVAILABLE（provider 出图失败）

**为什么源图不即时删除**：端侧的重试语义（AvatarFlow「从生成续跑」）要求
``source_upload_id`` 在失败后仍然可用；删早了用户只能重新选图。隐私口径因此是一条
TTL：**源图在服务端存活不超过 24h**（端侧生成页的隐私说明就是这句话），到点由
``sweep`` 连对象带 ca_upload 行一起删。默认 TTL 取 20h：sweep 每 5 分钟一轮，
最坏情况仍在 24h 以内——承诺写的是 24h，配置就不许把它推到 24h 整。

配额按**尝试**计数（含 provider 失败的尝试），否则连续失败可以无限重试打穿配额。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from companion.service.avatar_gen.port import (
    ALLOWED_STYLES,
    AnimeStyleProvider,
    AvatarGenError,
    ExpiredSource,
)

log = logging.getLogger("companion.avatar_gen")

#: 每日生成配额默认值（保守）。可配置：COMPANION_AVATAR_GEN_DAILY_QUOTA。
DEFAULT_DAILY_QUOTA = 10
#: 源图存活上限。**隐私红线：不得超过 24h**（端侧文案同句）。
MAX_SOURCE_TTL = timedelta(hours=24)
#: 默认取 20h，给 sweep 的轮询间隔留余量（见模块 docstring）。
DEFAULT_SOURCE_TTL = timedelta(hours=20)
#: 后台 sweep 的轮询间隔（bootstrap/app.py 的 lifespan 里用）。
SWEEP_POLL_SEC = 300.0


def utc_now() -> datetime:
    """naive UTC：与 ca_* 表 UTCDateTime 的读写口径一致（jobs/worker.utc_now 同款）。"""
    return datetime.now(UTC).replace(tzinfo=None)


class AvatarGenService:
    """一次请求内完成（MVP 同步语义）。

    依赖全是端口：``uploads`` 是既有 ``UploadService``（源图与生成图走同一条 uploads
    存储，**不新造存储路径**）；``attempts`` 是生成账本（配额 + 源图 TTL）；
    ``avatars`` 是「当前头像」指针（服务端是真相）。
    """

    def __init__(self, *, uploads: Any, attempts: Any, avatars: Any,
                 provider: AnimeStyleProvider, daily_quota: int = DEFAULT_DAILY_QUOTA,
                 source_ttl: timedelta = DEFAULT_SOURCE_TTL,
                 clock: Callable[[], datetime] = utc_now) -> None:
        self._uploads = uploads
        self._attempts = attempts
        self._avatars = avatars
        self._provider = provider
        self._quota = max(0, int(daily_quota))
        self._ttl = min(source_ttl, MAX_SOURCE_TTL)
        self._clock = clock

    # ------------------------------------------------------------- generate

    async def generate(self, *, owner_id: int, source_upload_id: str, style: str) -> dict[str, Any]:
        """校验 → 记一次尝试（配额 + 账本）→ 读源图 → provider → 结果入 uploads。

        尝试先记账再生成：provider 失败也要占配额，只有「进不了生成」的请求
        （style 非法 / 源图不可用）不落行、不占配额。
        """
        if style not in ALLOWED_STYLES:
            # 未知 style 与坏图同类（BAD_IMAGE）：端侧不必区分，也不给探测留差异信号。
            raise AvatarGenError("style_not_allowed", status=422)

        # 不存在、不是本人的、或不是图片：同一句话（防枚举），端侧统一 BAD_IMAGE。
        source = await self._uploads.get_owned(owner_id=owner_id, upload_id=source_upload_id)
        if source is None:
            raise AvatarGenError("source_not_found", status=422)

        now = self._clock()
        if await self._attempts.count_recent(owner_id=owner_id, since=now - timedelta(hours=24)) >= self._quota:
            raise AvatarGenError("quota_exceeded", status=429)

        data = await self._uploads.read_bytes(record=source)
        attempt_id = await self._attempts.add_attempt(owner_id=owner_id, source_upload_id=source.id,
                                                      source_key=source.object_key, style=style,
                                                      created_at=now, expires_at=now + self._ttl)
        try:
            result = await self._provider.generate(image=data, style=style)
        except Exception as exc:  # noqa: BLE001 —— provider 原始错误绝不进响应（decode 纪律）
            log.warning("avatar provider failed", extra={"owner_id": owner_id, "error": repr(exc)[:300]})
            raise AvatarGenError("provider_failed", status=502) from exc

        # 结果走同一条 uploads 管线（normalize + 私有桶 + ca_upload 行）：
        # 预览因此复用 GET /v1/uploads/{id}，不需要新的读图路径。
        record = await self._uploads.accept(owner_id=owner_id, data=result)
        await self._attempts.attach_result(attempt_id=attempt_id, result_upload_id=record.id)
        return {"avatar_upload_id": record.id, "style": style, "provider": self._provider.name}

    # ---------------------------------------------------------------- apply

    async def apply(self, *, owner_id: int, avatar_upload_id: str) -> dict[str, Any]:
        """把生成结果设为当前头像（服务端真相）。

        只接受**生成账本里的结果**：拿源图直接当头像，会让 TTL sweep 把用户刚设的
        头像删掉（sweep 按账本清源图）。所以不在账本里就是 BAD_IMAGE。
        """
        record = await self._uploads.get_owned(owner_id=owner_id, upload_id=avatar_upload_id)
        if record is None or not await self._attempts.result_owned(owner_id=owner_id, upload_id=avatar_upload_id):
            raise AvatarGenError("avatar_not_generated", status=422)

        previous = await self._avatars.get(owner_id=owner_id)
        await self._avatars.set(owner_id=owner_id, upload_id=record.id)

        # 「生成图直到用户再次更换前保留」：换掉的那张当场删（对象 + 行）。
        # 先换指针再删旧对象：中途失败时用户看到旧头像还在，而不是头像空了。
        if previous is not None and previous != record.id:
            await self._delete_upload(owner_id=owner_id, upload_id=previous)
        return {"ok": True}

    # ------------------------------------------------------------- sweep

    async def sweep(self, *, limit: int = 200) -> dict[str, int]:
        """删除存活超过 TTL 的源图（对象 + ca_upload 行）。可手动调用，测试直接调它。

        删完把账本行标成「源图已清理」（``expires_at`` 置空）而不是删行：行还要留着
        做两件事——配额窗口按 created_at 计数，apply 靠它认「这是我生成的结果」。
        因此用户隔几天再 apply 昨天的结果不会被误判成 BAD_IMAGE。
        """
        now = self._clock()
        due: list[ExpiredSource] = await self._attempts.due_sources(now=now, limit=limit)
        removed = 0
        for row in due:
            if await self._delete_upload(owner_id=row.owner_id, upload_id=row.upload_id, key=row.object_key):
                removed += 1
        return {"expired_sources": removed}

    async def _delete_upload(self, *, owner_id: int, upload_id: str, key: str | None = None) -> bool:
        """删一个 uploads 对象与其行；连带把该源的账本标成已清理。

        顺序是**先删对象再删行**：对象删失败时行还在，下一轮 sweep 重试；行先删了就
        会在私有桶里留下没人认领的对象——隐私口径下最不该出现的状态。
        """
        if key is None:
            record = await self._uploads.get_owned(owner_id=owner_id, upload_id=upload_id)
            if record is None:
                await self._attempts.mark_source_purged(source_upload_id=upload_id)
                return False
            key = record.object_key
        try:
            await self._uploads.delete_object(key=key)
        except Exception:  # noqa: BLE001 —— 单个对象删失败不让整轮 sweep 退出，行留着下轮重试
            log.warning("avatar source object delete failed", extra={"owner_id": owner_id})
            return False
        await self._uploads.delete_record(owner_id=owner_id, upload_id=upload_id)
        await self._attempts.mark_source_purged(source_upload_id=upload_id)
        return True
