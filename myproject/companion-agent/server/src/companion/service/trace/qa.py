"""模型调用与语音质检记录的存储。

两条规则贯穿这里：

1. **指标永远写，内容看同意。** token、耗时、结束原因不含用户原话；输入输出、识别文本、送去合成的文本
   只有 ``keep_content=True`` 时才写。调用方决定 keep_content（读用户的质检留存同意），本类不自己查。
2. **能被清理。** 到期删除要同时给出音频对象的键，让调用方去对象存储里一并删掉；
   按用户删除（注销）同理。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.db.schema import chat_turn, text_blob, turn_trace, voice_turn
from companion.agent.brain.trace_model import LlmCall, build_trace, read_trace, referenced_hashes, usage_of


def _now() -> datetime:
    return datetime.now(UTC)


# 一次 INSERT 最多带多少个文本块。Postgres 单条语句最多 65535 个参数，每块 4 个，留足余量。
BLOB_BATCH = 500


@dataclass
class VoiceTurnRecord:
    """语音回合记录。字段为 None 表示“这一方没给”：识别那一方和 TTS 那一方各写各的，按 turn_id 合并，
    谁先到都行；没给的字段不会覆盖对方已经写下的值。"""

    turn_id: str
    session_id: int
    owner_id: int
    role_id: str = ""
    user_message_id: int | None = None
    stt_provider: str | None = None
    stt_text: str | None = None
    stt_confidence: float | None = None
    tts_provider: str | None = None
    tts_voice: str | None = None
    tts_text: list[str] | None = None
    audio_in_key: str | None = None
    audio_out_key: str | None = None
    first_sentence_ms: int | None = None
    tts_ttfb_ms: int | None = None
    tts_audio_ms: int | None = None
    tts_truncated: bool | None = None
    total_ms: int | None = None
    interrupted: bool | None = None


# 含用户原话或用户声音的字段：没有同意就不写
_VOICE_CONTENT = ("stt_text", "tts_text", "audio_in_key", "audio_out_key")


@dataclass(frozen=True)
class Purged:
    rows: int
    object_keys: tuple[str, ...]


class SqlQaStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    # ---- 回合追踪 ----

    async def record_trace(self, *, turn_id: str, session_id: int, owner_id: int, role_id: str,
                           calls: list[LlmCall], keep_content: bool) -> list[dict[str, Any]]:
        """写入一个回合的追踪，返回合并后的全部步骤（供调用方算用量）。

        回合被合并重跑时同一个 ``turn_id`` 会来第二次：不覆盖，把新的步骤接在后面并记下第几次尝试。
        """
        if not calls:
            return []
        now = _now()
        async with self._engine.begin() as conn:
            row = (await conn.execute(select(turn_trace.c.steps, turn_trace.c.attempts, turn_trace.c.content_kept)
                                      .where(turn_trace.c.turn_id == turn_id))).first()
            attempt = row.attempts if row else 0
            steps, blobs = build_trace(calls, keep_content=keep_content, attempt=attempt)
            if blobs:
                await self._touch_blobs(conn, owner_id, blobs, now)
            if row is None:
                try:
                    async with conn.begin_nested():
                        await conn.execute(insert(turn_trace).values(
                            turn_id=turn_id, session_id=session_id, owner_id=owner_id, role_id=role_id or None,
                            content_kept=keep_content, steps=steps, attempts=1, created_at=now))
                    return steps
                except IntegrityError:
                    # 另一个写入方刚好先插入了：当作第二次尝试合并
                    row = (await conn.execute(select(turn_trace.c.steps, turn_trace.c.attempts, turn_trace.c.content_kept)
                                              .where(turn_trace.c.turn_id == turn_id))).first()
                    attempt = row.attempts
                    steps, blobs = build_trace(calls, keep_content=keep_content, attempt=attempt)
                    if blobs:
                        await self._touch_blobs(conn, owner_id, blobs, now)
            merged = list(row.steps or []) + steps
            # 任何一次尝试带了正文，这一行就算带正文（读取时据此知道里面有没有内容）
            await conn.execute(update(turn_trace).where(turn_trace.c.turn_id == turn_id).values(
                steps=merged, attempts=row.attempts + 1, content_kept=bool(row.content_kept) or bool(keep_content)))
            return merged

    async def _touch_blobs(self, conn: Any, owner_id: int, blobs: dict[str, str], now: datetime) -> None:
        """新块插入，已有的块刷新 last_seen_at。刷新是必须的：清理按它判断，不刷新的话
        一段长期稳定的角色卡会因为“第一次存的时间太久”而被清掉，而仍在被新追踪引用。"""
        items = list(blobs.items())
        for i in range(0, len(items), BLOB_BATCH):
            batch = items[i:i + BLOB_BATCH]
            rows = [dict(owner_id=owner_id, hash=h, body=body, last_seen_at=now) for h, body in batch]
            await conn.execute(_upsert_blobs(conn, rows))

    async def read_trace(self, *, turn_id: str, owner_id: int | None = None) -> dict[str, Any] | None:
        """还原一个回合：每次模型调用实际看到的输入、输出、思考、工具请求和指标。"""
        where = [turn_trace.c.turn_id == turn_id]
        if owner_id is not None:
            where.append(turn_trace.c.owner_id == owner_id)
        async with self._engine.connect() as conn:
            row = (await conn.execute(select(turn_trace).where(*where))).mappings().first()
            if row is None:
                return None
            steps = list(row["steps"] or [])
            hashes = referenced_hashes(steps)
            blobs: dict[str, str] = {}
            if hashes:
                got = (await conn.execute(select(text_blob.c.hash, text_blob.c.body).where(
                    text_blob.c.owner_id == row["owner_id"], text_blob.c.hash.in_(list(hashes))))).all()
                blobs = {h: body for h, body in got}
        return {"turn_id": turn_id, "session_id": row["session_id"], "owner_id": row["owner_id"],
                "role_id": row["role_id"], "content_kept": row["content_kept"], "attempts": row["attempts"],
                "created_at": row["created_at"], "usage": usage_of(steps), "steps": read_trace(steps, blobs)}

    async def record_voice_turn(self, record: VoiceTurnRecord, *, keep_content: bool) -> None:
        """写入或合并一个语音回合。内容字段只在 ``keep_content`` 时写；音频是用户相关的声音，同意之前一律不留。"""
        values: dict[str, Any] = {}
        for name in ("user_message_id", "stt_provider", "stt_text", "stt_confidence", "tts_provider", "tts_voice",
                     "tts_text", "audio_in_key", "audio_out_key", "first_sentence_ms", "tts_ttfb_ms", "tts_audio_ms",
                     "tts_truncated", "total_ms", "interrupted"):
            value = getattr(record, name)
            if value is None or value == "" or (name in _VOICE_CONTENT and not keep_content):
                continue
            values[name] = list(value) if isinstance(value, list) else value
        values["content_kept"] = keep_content
        if record.role_id:
            values["role_id"] = record.role_id
        async with self._engine.begin() as conn:
            done = (await conn.execute(update(voice_turn).where(voice_turn.c.turn_id == record.turn_id)
                                       .values(**values))).rowcount
        if done:
            return
        try:
            async with self._engine.begin() as conn:
                await conn.execute(insert(voice_turn).values(
                    turn_id=record.turn_id, session_id=record.session_id, owner_id=record.owner_id,
                    created_at=_now(), **values))
        except IntegrityError:
            # 另一方刚好先插入了（turn_id 唯一）：改为合并更新
            async with self._engine.begin() as conn:
                await conn.execute(update(voice_turn).where(voice_turn.c.turn_id == record.turn_id).values(**values))

    async def purge_before(self, *, cutoff: datetime) -> Purged:
        """删除 ``cutoff`` 之前的全部记录，返回要一并从对象存储删除的音频键。

        文本块按 last_seen_at 清：每次引用都会刷新它，所以只要还有未到期的追踪在引用，块就不会被清掉。
        追踪行和块刷新用的是同一个事务里的同一个时刻，不会出现“追踪留着、块先到期”的间隙。
        """
        async with self._engine.begin() as conn:
            keys = await self._audio_keys(conn, voice_turn.c.created_at < cutoff)
            n = (await conn.execute(delete(turn_trace).where(turn_trace.c.created_at < cutoff))).rowcount or 0
            n += (await conn.execute(delete(text_blob).where(text_blob.c.last_seen_at < cutoff))).rowcount or 0
            n += (await conn.execute(delete(voice_turn).where(voice_turn.c.created_at < cutoff))).rowcount or 0
        return Purged(rows=n, object_keys=keys)

    async def delete_user(self, *, owner_id: int) -> Purged:
        async with self._engine.begin() as conn:
            keys = await self._audio_keys(conn, voice_turn.c.owner_id == owner_id)
            n = (await conn.execute(delete(turn_trace).where(turn_trace.c.owner_id == owner_id))).rowcount or 0
            n += (await conn.execute(delete(text_blob).where(text_blob.c.owner_id == owner_id))).rowcount or 0
            n += (await conn.execute(delete(voice_turn).where(voice_turn.c.owner_id == owner_id))).rowcount or 0
        return Purged(rows=n, object_keys=keys)

    async def audio_keys_for_user(self, *, owner_id: int) -> tuple[str, ...]:
        async with self._engine.connect() as conn:
            return await self._audio_keys(conn, voice_turn.c.owner_id == owner_id)

    async def _audio_keys(self, conn: Any, where: Any) -> tuple[str, ...]:
        rows = (await conn.execute(select(voice_turn.c.audio_in_key, voice_turn.c.audio_out_key).where(where))).all()
        return tuple(sorted({k for pair in rows for k in pair if k}))

    async def count(self) -> dict[str, int]:
        async with self._engine.connect() as conn:
            return {"turn_trace": (await conn.execute(select(func.count()).select_from(turn_trace))).scalar_one(),
                    "text_blob": (await conn.execute(select(func.count()).select_from(text_blob))).scalar_one(),
                    "voice_turn": (await conn.execute(select(func.count()).select_from(voice_turn))).scalar_one()}


    # ---- 回合汇总（ca_chat_turn）----
    # 一个回合一行：用的哪个模型、提示词版本、用了哪些 skill、用量合计、结束状态和起止时间。
    # 由两处写入：produce 在回合收尾时带来模型与用量（running），TurnRunner 的 after_turn 带来最终状态。
    # 两者谁先到都行，所以都是“有则更新、无则插入”。

    async def note_turn_models(self, *, turn_id: str, session_id: int, owner_id: int, role_id: str,
                               prompt_version: str, skills: tuple[str, ...], steps: list[dict[str, Any]],
                               started_at: datetime) -> None:
        """回合汇总里的模型、用量。``steps`` 是 ``record_trace`` 返回的合并后全部步骤，
        所以回合被重跑过时用量是各次尝试的总和，而不是只有最后一次。"""
        model = next((x["m"] for x in reversed(steps) if x.get("m")), "")
        await self._upsert_turn(turn_id, session_id=session_id, owner_id=owner_id, role_id=role_id,
                                changes=dict(model=model or None, prompt_version=prompt_version or None,
                                             skills=list(skills), usage=usage_of(steps), started_at=started_at))

    async def finish_turn(self, *, turn_id: str, session_id: int, owner_id: int, role_id: str, state: str,
                          error_code: str = "") -> None:
        await self._upsert_turn(turn_id, session_id=session_id, owner_id=owner_id, role_id=role_id,
                                changes=dict(state=state, error_code=error_code or None, finished_at=_now()))

    async def _upsert_turn(self, turn_id: str, *, session_id: int, owner_id: int, role_id: str,
                           changes: dict[str, Any]) -> None:
        async with self._engine.begin() as conn:
            done = (await conn.execute(update(chat_turn).where(chat_turn.c.id == turn_id).values(**changes))).rowcount
        if done:
            return
        try:
            async with self._engine.begin() as conn:
                await conn.execute(insert(chat_turn).values(
                    id=turn_id, session_id=session_id, owner_id=owner_id, role_id=role_id or None,
                    **{"state": "running", **changes}))
        except IntegrityError:
            # 另一个写入方刚好先插入了：改为更新
            async with self._engine.begin() as conn:
                await conn.execute(update(chat_turn).where(chat_turn.c.id == turn_id).values(**changes))


def _upsert_blobs(conn: Any, rows: list[dict[str, Any]]):
    """“有则只刷新 last_seen_at，无则插入”。三种方言的写法不同；body 不更新（哈希相同则内容相同）。"""
    name = conn.dialect.name
    if name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert

        stmt = dialect_insert(text_blob).values(rows)
        return stmt.on_conflict_do_update(index_elements=["owner_id", "hash"],
                                          set_={"last_seen_at": stmt.excluded.last_seen_at})
    if name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert

        stmt = dialect_insert(text_blob).values(rows)
        return stmt.on_conflict_do_update(index_elements=["owner_id", "hash"],
                                          set_={"last_seen_at": stmt.excluded.last_seen_at})
    from sqlalchemy.dialects.mysql import insert as dialect_insert

    stmt = dialect_insert(text_blob).values(rows)
    return stmt.on_duplicate_key_update(last_seen_at=stmt.inserted.last_seen_at)
