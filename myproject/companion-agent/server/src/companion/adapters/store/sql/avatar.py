"""形象发布元数据的 SQL 实现。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.adapters.store.sql.schema import avatar_release
from companion.ports.avatar import ONLINE, AvatarRelease


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def _release(r) -> AvatarRelease:
    return AvatarRelease(id=r["id"], avatar_key=r["avatar_key"], version=r["version"], name=r["name"],
                         role_id=r["role_id"] or "", status=r["status"], manifest=dict(r["manifest"] or {}),
                         object_key=r["object_key"], size_bytes=r["size_bytes"], sha256=r["sha256"],
                         min_app_version=r["min_app_version"], published_at=r["published_at"],
                         created_at=r["created_at"])


class SqlAvatarReleaseStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def create(self, *, avatar_key: str, name: str, role_id: str, manifest: dict[str, Any],
                     object_key_for: Any, size_bytes: int, sha256: str, min_app_version: int) -> AvatarRelease:
        now = _now()
        for _ in range(3):   # 并发上传同一个 avatar_key 时版本号会撞唯一约束，重取再试
            async with self._engine.connect() as conn:
                top = (await conn.execute(select(func.max(avatar_release.c.version))
                                          .where(avatar_release.c.avatar_key == avatar_key))).scalar() or 0
            version = top + 1
            try:
                async with self._engine.begin() as conn:
                    res = await conn.execute(insert(avatar_release).values(
                        avatar_key=avatar_key, version=version, name=name, role_id=role_id, status="draft",
                        manifest=manifest, object_key=object_key_for(version), size_bytes=size_bytes,
                        sha256=sha256, min_app_version=min_app_version, created_at=now, updated_at=now))
                    new_id = res.inserted_primary_key[0]
            except IntegrityError:
                continue
            created = await self.get(release_id=new_id)
            assert created is not None
            return created
        raise RuntimeError("could not allocate an avatar version")

    async def get(self, *, release_id: int) -> AvatarRelease | None:
        async with self._engine.connect() as conn:
            row = (await conn.execute(select(avatar_release).where(avatar_release.c.id == release_id))
                   ).mappings().first()
        return _release(row) if row else None

    async def list_all(self, *, avatar_key: str | None = None, limit: int = 100) -> list[AvatarRelease]:
        query = select(avatar_release)
        if avatar_key:
            query = query.where(avatar_release.c.avatar_key == avatar_key)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query.order_by(avatar_release.c.avatar_key, avatar_release.c.version.desc())
                                       .limit(max(1, min(limit, 500))))).mappings().all()
        return [_release(r) for r in rows]

    async def set_status(self, *, release_id: int, from_statuses: tuple[str, ...], to_status: str) -> bool:
        now = _now()
        values: dict[str, Any] = {"status": to_status, "updated_at": now}
        if to_status == ONLINE:
            values["published_at"] = now
        async with self._engine.begin() as conn:
            res = await conn.execute(update(avatar_release).where(and_(
                avatar_release.c.id == release_id, avatar_release.c.status.in_(from_statuses))).values(**values))
        return res.rowcount == 1

    async def list_online(self, *, role_id: str) -> list[AvatarRelease]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(avatar_release).where(and_(
                avatar_release.c.status == ONLINE,
                or_(avatar_release.c.role_id == role_id, avatar_release.c.role_id == "")))
                .order_by(avatar_release.c.avatar_key, avatar_release.c.version.desc()))).mappings().all()
        return [_release(r) for r in rows]
