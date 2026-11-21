"""用户档案的 SQL 实现。协议见 port.py，语义见 model.py。

档案行和批量游标是同一行：(owner_id, role_id) 主键，``last_message_id`` / ``pending_chars``
就是 persona_cursor 那套「攒够一批再维护」的水位。LLM 维护用乐观并发（version 条件更新）：
管理员在维护期间改过档案，这一批放弃，下一批以管理员的版本为底稿——管理员永远赢。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.db.schema import profile_doc
from companion.service.profile_doc.model import ProfileDoc


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


class SqlProfileDocStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def get(self, *, owner_id: int, role_id: str) -> ProfileDoc | None:
        async with self._engine.connect() as conn:
            r = (await conn.execute(select(profile_doc).where(
                profile_doc.c.owner_id == owner_id, profile_doc.c.role_id == role_id))).mappings().first()
        if r is None:
            return None
        return ProfileDoc(owner_id=owner_id, role_id=role_id, markdown=r["markdown"],
                          version=int(r["version"]), source=r["source"],
                          last_message_id=int(r["last_message_id"]))

    async def advance(self, *, owner_id: int, role_id: str, last_message_id: int, add_chars: int) -> int:
        """回合收尾调用：档案还不存在时先建行（markdown 空串、version 0），累计待维护字数。"""
        now = _now()
        async with self._engine.begin() as conn:
            row = (await conn.execute(
                select(profile_doc.c.pending_chars).where(
                    profile_doc.c.owner_id == owner_id, profile_doc.c.role_id == role_id)
                .with_for_update())).first()
            if row is None:
                await conn.execute(insert(profile_doc).values(
                    owner_id=owner_id, role_id=role_id, markdown="", version=0, source="",
                    last_message_id=0, pending_chars=add_chars, created_at=now, updated_at=now))
                return add_chars
            pending = row.pending_chars + add_chars
            await conn.execute(update(profile_doc).where(
                profile_doc.c.owner_id == owner_id, profile_doc.c.role_id == role_id)
                .values(pending_chars=pending, updated_at=now))
        return pending

    async def commit_llm(self, *, owner_id: int, role_id: str, markdown: str, up_to_message_id: int,
                         expected_version: int) -> bool:
        """LLM 维护的落库：乐观并发，版本对不上（期间被管理员改过）就放弃，返回 False。"""
        now = _now()
        async with self._engine.begin() as conn:
            row = (await conn.execute(select(profile_doc.c.version, profile_doc.c.last_message_id).where(
                profile_doc.c.owner_id == owner_id, profile_doc.c.role_id == role_id)
                .with_for_update())).first()
            if row is None:
                # 游标行在 advance 里建过；这里只兜底（advance 被跳过时）
                await conn.execute(insert(profile_doc).values(
                    owner_id=owner_id, role_id=role_id, markdown=markdown, version=1, source="llm",
                    last_message_id=up_to_message_id, pending_chars=0, created_at=now, updated_at=now))
                return True
            if row.version != expected_version:
                return False
            await conn.execute(update(profile_doc).where(
                and_(profile_doc.c.owner_id == owner_id, profile_doc.c.role_id == role_id,
                     profile_doc.c.version == expected_version))
                .values(markdown=markdown, version=expected_version + 1, source="llm",
                        generated_from={"up_to_message_id": up_to_message_id},
                        last_message_id=up_to_message_id, pending_chars=0, updated_at=now))
        return True

    async def save_admin(self, *, owner_id: int, role_id: str, markdown: str) -> bool:
        """管理员改写：无条件覆盖，版本号照常 +1（下一批 LLM 以它为底稿）。"""
        now = _now()
        async with self._engine.begin() as conn:
            row = (await conn.execute(select(profile_doc).where(
                profile_doc.c.owner_id == owner_id, profile_doc.c.role_id == role_id)
                .with_for_update())).first()
            if row is None:
                await conn.execute(insert(profile_doc).values(
                    owner_id=owner_id, role_id=role_id, markdown=markdown, version=1, source="admin",
                    last_message_id=0, pending_chars=0, created_at=now, updated_at=now))
                return True
            await conn.execute(update(profile_doc).where(
                profile_doc.c.owner_id == owner_id, profile_doc.c.role_id == role_id)
                .values(markdown=markdown, version=row.version + 1, source="admin",
                        pending_chars=0, updated_at=now))
        return True

    async def mark_processed(self, *, owner_id: int, role_id: str, last_message_id: int) -> None:
        """这一批看完了但没有新档案可写（模型说无变化）：只推水位，不动正文与版本。"""
        async with self._engine.begin() as conn:
            await conn.execute(update(profile_doc).where(
                profile_doc.c.owner_id == owner_id, profile_doc.c.role_id == role_id)
                .values(pending_chars=0,
                        last_message_id=func.greatest(profile_doc.c.last_message_id, last_message_id),
                        updated_at=_now()))

    async def delete_user(self, *, owner_id: int) -> int:
        async with self._engine.begin() as conn:
            res = await conn.execute(delete(profile_doc).where(profile_doc.c.owner_id == owner_id))
        return res.rowcount

