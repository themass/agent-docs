"""Direct-upload sign / bind / GC (ADR-011).

The whole point of this module is that the application server never touches
the bytes: sign mints a key and a presigned PUT, the browser PUTs straight to
the bucket, bind validates ownership against the issuance row and the object's
real size via one HEAD. A signed URL is a bearer secret — it is returned to the
caller and never written to logs, analytics or error detail.

Bind is the trust boundary, and it is an OWNERSHIP check, not a content check
(ADR-011 §7.1): the key must exist in the issuance table, belong to this same
actor, match the scene, still be unbound, and still be inside its TTL. Then one
HEAD answers "did it actually arrive and how big" — the two failure modes
presigned PUT cannot be prevented from having (no upload, oversize body).
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta

from agentkit.web.auth import Actor
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jc.config import settings
from jc.exceptions import (
    ConflictError,
    ForbiddenError,
    GoneError,
    NotFoundError,
    ServiceUnavailableError,
    TooManyRequestsError,
)
from jc.models.enums import MediaUploadState
from jc.models.media_upload import MediaUpload
from jc.redis_client import get_redis, redis_key
from jc.services.media_scene import MediaSceneError, extension_for, resolve_scene
from jc.storage_keys import storage_key

logger = logging.getLogger(__name__)

#: 22 chars of urlsafe base64 = 132 bits. Long enough that enumeration is not
# a strategy; short enough to keep keys readable in ops tooling.
_KEY_ID_BYTES = 16


def new_key_id() -> str:
    return secrets.token_urlsafe(_KEY_ID_BYTES).rstrip("=")


class MediaService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ----------------------------- sign -----------------------------

    async def sign(self, *, actor: Actor, scene: str, content_type: str, size_bytes: int) -> dict:
        if not settings.storage_remote_enabled:
            # Dev fallback writes local disk; there is no bucket to PUT into.
            # The frontend treats 503 as "use the multipart channel" — that
            # channel is also production's degradation path (ADR-011 §6-A).
            raise ServiceUnavailableError(
                "直传未启用，请使用普通上传。", code="direct_upload_disabled"
            )

        media_scene = resolve_scene(scene)
        content_type = content_type.strip().lower()
        if content_type not in media_scene.content_types:
            raise MediaSceneError("该场景不支持这个文件类型。", code="unsupported_content_type")
        if size_bytes > media_scene.max_bytes:
            limit_mb = media_scene.max_bytes // (1024 * 1024)
            raise MediaSceneError(
                f"文件超过 {limit_mb} MB 上限，请压缩后重试。", code="size_over_limit"
            )

        await self._check_rate_limit(actor=actor)

        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=settings.jc_media_sign_ttl_sec)
        ext = extension_for(content_type)
        key = storage_key(
            "uploads",
            actor.actor_id,
            media_scene.name,
            f"{now:%Y}",
            f"{now:%m}",
            f"{now:%d}",
            f"{new_key_id()}.{ext}",
        )

        store = self._object_store()
        # content_type is ALWAYS passed: it enters the signature, so the client
        # cannot sign once and PUT with a spoofed type. This closes most of the
        # optional-parameter hole the companion agent's version left open.
        url = store.presigned_put_url(
            key, content_type=content_type, expires_in=settings.jc_media_sign_ttl_sec
        )

        self._db.add(
            MediaUpload(
                object_key=key,
                actor_id=actor.actor_id,
                actor_kind=actor.kind,
                scene=media_scene.name,
                content_type=content_type,
                declared_size=size_bytes,
                state=MediaUploadState.ISSUED,
                expires_at=expires_at,
            )
        )
        await self._db.commit()

        return {
            "object_key": key,
            "upload": {
                "method": "PUT",
                "url": url,
                "headers": {"Content-Type": content_type},
                "expires_at": expires_at,
            },
            "limits": {"max_bytes": media_scene.max_bytes},
        }

    async def _check_rate_limit(self, *, actor: Actor) -> None:
        """Per-actor sign issuance throttle (ADR-011 §2).

        Fixed window in Redis, minute and day. A guest has no account anchor,
        so this is the only thing standing between a scripted visitor and an
        expensive flood of signed keys; a user hitting it means a bug or an
        attack, never normal use (20/min is far above any real session).
        """
        redis = get_redis()
        now = datetime.now(UTC)
        minute_key = redis_key("media:sign:minute", f"{actor.actor_id}:{now:%Y%m%d%H%M}")
        day_key = redis_key("media:sign:day", f"{actor.actor_id}:{now:%Y%m%d}")
        minute = await redis.incr(minute_key)
        if minute == 1:
            await redis.expire(minute_key, 60)
        if minute > settings.jc_media_sign_rate_limit_per_min:
            raise TooManyRequestsError("上传请求过于频繁，请稍后再试。")
        day = await redis.incr(day_key)
        if day == 1:
            await redis.expire(day_key, 90 * 60 * 60)
        if day > settings.jc_media_sign_daily_limit:
            raise TooManyRequestsError("今日上传次数已达上限，请明天再试。", code="daily_limit")

    # ----------------------------- bind -----------------------------

    async def bind(self, *, actor: Actor, object_key: str, scene: str, bound_ref: str) -> int:
        """Validate and consume one issued key; returns the actual byte count.

        Raises NotFoundError (unknown/foreign key shape), ForbiddenError (key
        exists but belongs to someone else — 403, per ADR-011 §7), GoneError
        (expired), ConflictError (already bound), MediaSceneError (HEAD shows a
        missing or oversize object). Callers run this inside their business
        transaction so a rejected bind cannot leave the business row behind.
        """
        row = await self._load_for_bind(actor=actor, object_key=object_key, scene=scene)

        store = self._object_store()
        size = await asyncio.to_thread(store.head_object_size, object_key)
        if size is None:
            raise NotFoundError("文件没有上传成功，请重试。", code="upload_not_found")
        media_scene = resolve_scene(row.scene)
        if size > media_scene.max_bytes:
            # Leave the row ISSUED: the object is garbage, GC removes it. The
            # key stays bindable in theory but nothing sane will re-PUT under
            # it — and re-PUT requires the still-valid signed URL anyway.
            limit_mb = media_scene.max_bytes // (1024 * 1024)
            raise MediaSceneError(
                f"上传的文件超过 {limit_mb} MB 上限。", code="uploaded_size_over_limit"
            )

        now = datetime.now(UTC)
        result = await self._db.execute(
            update(MediaUpload)
            .where(
                MediaUpload.object_key == object_key,
                MediaUpload.state == MediaUploadState.ISSUED,
            )
            .values(
                state=MediaUploadState.BOUND,
                actual_size=size,
                bound_ref=bound_ref,
                bound_at=now,
            )
        )
        if result.rowcount != 1:  # type: ignore[attr-defined]
            # Lost a race to a concurrent bind of the same key.
            raise ConflictError("该文件已被使用，请重新上传。", code="already_bound")
        return size

    async def _load_for_bind(self, *, actor: Actor, object_key: str, scene: str) -> MediaUpload:
        row = await self._db.get(MediaUpload, object_key)
        if row is None:
            raise NotFoundError("上传记录不存在或已过期，请重新上传。", code="upload_unknown")
        if row.actor_id != actor.actor_id:
            # 403, not 404: the caller produced a key we issued to someone else,
            # which is an attack-shaped request and worth an unambiguous signal.
            raise ForbiddenError("无权使用此上传。", code="foreign_upload")
        if row.scene != scene:
            raise ForbiddenError("该上传不属于此场景。", code="scene_mismatch")
        if row.state == MediaUploadState.BOUND:
            raise ConflictError("该文件已被使用，请重新上传。", code="already_bound")
        if row.state == MediaUploadState.EXPIRED:
            raise GoneError("上传已过期，请重新上传。", code="upload_expired")
        if datetime.now(UTC) >= row.expires_at:
            await self._expire(row.object_key)
            raise GoneError("上传已过期，请重新上传。", code="upload_expired")
        return row

    async def _expire(self, object_key: str) -> None:
        await self._db.execute(
            update(MediaUpload)
            .where(
                MediaUpload.object_key == object_key,
                MediaUpload.state == MediaUploadState.ISSUED,
            )
            .values(state=MediaUploadState.EXPIRED)
        )
        await self._db.commit()

    def _object_store(self):
        # Local import: storage_client lru_caches an ObjectStore built from
        # settings; importing it at module load would freeze test monkeypatches
        # out of the picture.
        from jc.storage_client import get_object_store

        return get_object_store()


# ------------------------------- GC -------------------------------


async def sweep_media_uploads(*, dry_run: bool = False) -> dict[str, int]:
    """One GC pass over `jc/<env>/uploads/` (ADR-011 §3).

    Two bounded scans, neither of which walks outside the uploads prefix:
    1. expired rows (ISSUED past TTL+grace, or marked EXPIRED) -> delete object,
       delete row;
    2. objects under the prefix the table never heard of (signed URL used after
       a crash between PUT and bind, leftovers of half-applied deploys) older
       than the orphan age -> delete object. Objects only, never rows: the row
       may not exist, and if it does exist we leave it alone.

    Batch limits keep a single pass cheap; there is at most one bucket list
    page and at most `batch` deletes per category.
    """
    if not settings.storage_remote_enabled:
        return {"expired": 0, "orphans": 0}
    from jc.db.session import AsyncSessionLocal
    from jc.storage_client import get_object_store

    store = get_object_store()
    now = datetime.now(UTC)
    batch = settings.jc_media_gc_batch_limit
    removed_expired = 0
    removed_orphans = 0

    # 1. Expired: give the row TTL plus a grace window so a client mid-retry is
    # never pulled out from under, then the object and the row both go.
    cutoff = (
        now
        - timedelta(seconds=settings.jc_media_sign_ttl_sec)
        - timedelta(hours=settings.jc_media_gc_expired_grace_hours)
    )
    async with AsyncSessionLocal() as db:
        stale_keys = (
            (
                await db.execute(
                    select(MediaUpload.object_key)
                    .where(
                        MediaUpload.state.in_([MediaUploadState.ISSUED, MediaUploadState.EXPIRED]),
                        MediaUpload.expires_at < cutoff,
                    )
                    .order_by(MediaUpload.expires_at)
                    .limit(batch)
                )
            )
            .scalars()
            .all()
        )
    for key in stale_keys:
        if not dry_run:
            await asyncio.to_thread(store.delete_object, key)
            async with AsyncSessionLocal() as db:
                await db.execute(
                    MediaUpload.__table__.delete().where(MediaUpload.object_key == key)
                )
                await db.commit()
        removed_expired += 1

    # 2. Orphans: list the prefix, keep entries the table does not know, delete
    # the object. Listing twice the batch lets table-known keys sit in the page
    # without starving the scan for unknown ones.
    def _list_prefix() -> list[tuple[str, object]]:
        # storage_key's discipline: the sweep can only ever see jc/<env>/uploads/.
        return store.list_object_keys(storage_key("uploads") + "/", max_keys=batch * 2)

    objects = await asyncio.to_thread(_list_prefix)
    if objects:
        orphan_age = timedelta(hours=settings.jc_media_gc_orphan_age_hours)
        stale = [
            (key, modified)
            for key, modified in objects
            if modified is not None and now - modified >= orphan_age
        ]
        if stale:
            async with AsyncSessionLocal() as db:
                known = set(
                    (
                        await db.execute(
                            select(MediaUpload.object_key).where(
                                MediaUpload.object_key.in_([key for key, _ in stale])
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
            for key, _modified in stale:
                if key in known:
                    continue
                if not dry_run:
                    await asyncio.to_thread(store.delete_object, key)
                removed_orphans += 1

    logger.info(
        "media GC expired=%s orphans=%s dry_run=%s", removed_expired, removed_orphans, dry_run
    )
    return {"expired": removed_expired, "orphans": removed_orphans}


async def run_media_gc(*, poll_seconds: float = 3600) -> None:
    """Hourly sweep alongside the other dispatchers (same loop shape as parse)."""
    while True:
        try:
            await sweep_media_uploads()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("media GC pass failed")
        await asyncio.sleep(poll_seconds)
