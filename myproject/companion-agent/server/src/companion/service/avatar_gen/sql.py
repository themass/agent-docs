"""生成账本与头像指针的 SQL 实现（端口见 port.py）。

两个 store 放一个文件：它们都只碰各自那张 ca_ 表，且都只被 avatar_gen 服务用。
时间列一律由**调用方传入**（``created_at`` / 比较用的 ``now``），不用
``server_default``——配额窗口与 TTL 判断都要跑在可注入的时钟上，测试才能钉死
「过了一天就不再算」和「到 20h 就该删」。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.db.schema import avatar_gen_attempt, user_avatar
from companion.service.avatar_gen.port import ExpiredSource


class SqlAvatarGenAttemptStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._auto_engine = None

    @property
    def _auto(self):
        """单语句读用的 autocommit 视图（异地库上省 BEGIN/ROLLBACK 两次往返，同 db/sql.py）。"""
        if self._auto_engine is None:
            self._auto_engine = self._engine.execution_options(isolation_level="AUTOCOMMIT")
        return self._auto_engine

    async def add_attempt(self, *, owner_id: int, source_upload_id: str, source_key: str,
                          style: str, created_at: datetime, expires_at: datetime) -> int:
        async with self._engine.begin() as conn:
            res = await conn.execute(insert(avatar_gen_attempt).values(
                owner_id=owner_id, source_upload_id=source_upload_id, source_key=source_key,
                style=style, created_at=created_at, expires_at=expires_at))
            # inserted_primary_key 是跨方言的（PG 走 RETURNING、MySQL/SQLite 走 lastrowid）；
            # .returning() 在 MySQL 上直接编译失败。
            return int(res.inserted_primary_key[0])

    async def count_recent(self, *, owner_id: int, since: datetime) -> int:
        async with self._auto.connect() as conn:
            res = (await conn.execute(select(avatar_gen_attempt.c.id).where(and_(
                avatar_gen_attempt.c.owner_id == owner_id,
                avatar_gen_attempt.c.created_at >= since)))).all()
        return len(res)

    async def attach_result(self, *, attempt_id: int, result_upload_id: str) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(update(avatar_gen_attempt)
                               .where(avatar_gen_attempt.c.id == attempt_id)
                               .values(result_upload_id=result_upload_id))

    async def result_owned(self, *, owner_id: int, upload_id: str) -> bool:
        async with self._auto.connect() as conn:
            row = (await conn.execute(select(avatar_gen_attempt.c.id).where(and_(
                avatar_gen_attempt.c.owner_id == owner_id,
                avatar_gen_attempt.c.result_upload_id == upload_id)).limit(1))).first()
        return row is not None

    async def due_sources(self, *, now: datetime, limit: int) -> list[ExpiredSource]:
        """到期的源图，按源去重（同一张源图跑过多次只出一条）。``expires_at`` 为空 = 已清理。"""
        cols = (avatar_gen_attempt.c.source_upload_id, avatar_gen_attempt.c.owner_id,
                avatar_gen_attempt.c.source_key)
        async with self._auto.connect() as conn:
            rows = (await conn.execute(select(*cols).where(
                avatar_gen_attempt.c.expires_at.is_not(None),
                avatar_gen_attempt.c.expires_at <= now).distinct().limit(limit))).all()
        return [ExpiredSource(upload_id=r.source_upload_id, owner_id=int(r.owner_id),
                              object_key=r.source_key) for r in rows]

    async def mark_source_purged(self, *, source_upload_id: str) -> None:
        """源图对象与 ca_upload 行已删：置空 expires_at，行留着（配额窗口与 apply 认领还要用）。"""
        async with self._engine.begin() as conn:
            await conn.execute(update(avatar_gen_attempt)
                               .where(avatar_gen_attempt.c.source_upload_id == source_upload_id)
                               .values(expires_at=None))


class SqlUserAvatarStore:
    """当前头像指针：每用户一行（主键 owner_id），换头像就是 UPDATE。"""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._auto_engine = None

    @property
    def _auto(self):
        if self._auto_engine is None:
            self._auto_engine = self._engine.execution_options(isolation_level="AUTOCOMMIT")
        return self._auto_engine

    async def get(self, *, owner_id: int) -> str | None:
        async with self._auto.connect() as conn:
            row = (await conn.execute(select(user_avatar.c.upload_id)
                                      .where(user_avatar.c.owner_id == owner_id))).first()
        return None if row is None else str(row.upload_id)

    async def set(self, *, owner_id: int, upload_id: str) -> None:
        from sqlalchemy.dialects.mysql import insert as mysql_insert
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        values = {"owner_id": owner_id, "upload_id": upload_id}
        async with self._engine.begin() as conn:
            dialect = conn.dialect.name
            if dialect == "postgresql":
                stmt = pg_insert(user_avatar).values(**values).on_conflict_do_update(
                    index_elements=[user_avatar.c.owner_id], set_={"upload_id": upload_id})
            elif dialect == "mysql":
                stmt = mysql_insert(user_avatar).values(**values).on_duplicate_key_update(
                    upload_id=upload_id)
            else:  # SQLite（测试夹具）
                from sqlalchemy.dialects.sqlite import insert as sqlite_insert

                stmt = sqlite_insert(user_avatar).values(**values).on_conflict_do_update(
                    index_elements=[user_avatar.c.owner_id], set_={"upload_id": upload_id})
            await conn.execute(stmt)

    async def delete(self, *, owner_id: int) -> None:
        """账号注销用（account/sql.py 的 _OWNED 也覆盖这张表，这里给显式入口）。"""
        async with self._engine.begin() as conn:
            await conn.execute(delete(user_avatar).where(user_avatar.c.owner_id == owner_id))
