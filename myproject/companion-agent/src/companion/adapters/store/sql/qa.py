"""模型调用与语音质检记录的存储。

两条规则贯穿这里：

1. **指标永远写，内容看同意。** token、耗时、结束原因不含用户原话；输入输出、识别文本、送去合成的文本
   只有 ``keep_content=True`` 时才写。调用方决定 keep_content（读用户的质检留存同意），本类不自己查。
2. **能被清理。** 到期删除要同时给出音频对象的键，让调用方去对象存储里一并删掉；
   按用户删除（注销）同理。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.adapters.store.sql.schema import chat_turn, llm_call, voice_turn


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class LlmCallRecord:
    turn_id: str
    session_id: int
    owner_id: int
    role_id: str = ""
    seq: int = 0
    provider: str = ""
    model: str = ""
    prompt_version: str = ""
    input_messages: list[dict[str, Any]] | None = None
    output_text: str = ""
    reasoning_text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    first_token_ms: int | None = None
    total_ms: int | None = None
    finish_reason: str = ""
    error_code: str = ""


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

    async def record_llm_calls(self, records: list[LlmCallRecord], *, keep_content: bool) -> int:
        if not records:
            return 0
        rows = [dict(
            turn_id=r.turn_id, session_id=r.session_id, owner_id=r.owner_id, role_id=r.role_id or None, seq=r.seq,
            provider=r.provider or None, model=r.model or None, prompt_version=r.prompt_version or None,
            content_kept=keep_content,
            input_messages=r.input_messages if keep_content else None,
            output_text=r.output_text if keep_content else None,
            reasoning_text=(r.reasoning_text or None) if keep_content else None,
            # 工具名永远记（不含用户原话）；参数可能带用户说的内容，没同意就去掉
            tool_calls=([{"id": c.get("id"), "name": c.get("name"),
                          **({"args": c.get("args")} if keep_content else {})} for c in r.tool_calls] or None),
            input_tokens=r.input_tokens, output_tokens=r.output_tokens, cached_tokens=r.cached_tokens,
            first_token_ms=r.first_token_ms, total_ms=r.total_ms,
            finish_reason=r.finish_reason or None, error_code=r.error_code or None, created_at=_now(),
        ) for r in records]
        async with self._engine.begin() as conn:
            await conn.execute(insert(llm_call), rows)
        return len(rows)

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
        """删除 ``cutoff`` 之前的全部记录，返回要一并从对象存储删除的音频键。"""
        async with self._engine.begin() as conn:
            keys = await self._audio_keys(conn, voice_turn.c.created_at < cutoff)
            n = (await conn.execute(delete(llm_call).where(llm_call.c.created_at < cutoff))).rowcount or 0
            n += (await conn.execute(delete(voice_turn).where(voice_turn.c.created_at < cutoff))).rowcount or 0
        return Purged(rows=n, object_keys=keys)

    async def delete_user(self, *, owner_id: int) -> Purged:
        async with self._engine.begin() as conn:
            keys = await self._audio_keys(conn, voice_turn.c.owner_id == owner_id)
            n = (await conn.execute(delete(llm_call).where(llm_call.c.owner_id == owner_id))).rowcount or 0
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
            return {"llm_call": (await conn.execute(select(func.count()).select_from(llm_call))).scalar_one(),
                    "voice_turn": (await conn.execute(select(func.count()).select_from(voice_turn))).scalar_one()}


    # ---- 回合汇总（ca_chat_turn）----
    # 一个回合一行：用的哪个模型、提示词版本、用了哪些 skill、用量合计、结束状态和起止时间。
    # 由两处写入：produce 在回合收尾时带来模型与用量（running），TurnRunner 的 after_turn 带来最终状态。
    # 两者谁先到都行，所以都是“有则更新、无则插入”。

    async def note_turn_models(self, *, turn_id: str, session_id: int, owner_id: int, role_id: str,
                               prompt_version: str, skills: tuple[str, ...], records: list[LlmCallRecord],
                               started_at: datetime) -> None:
        usage = {
            "calls": len(records),
            "input_tokens": sum(r.input_tokens or 0 for r in records),
            "output_tokens": sum(r.output_tokens or 0 for r in records),
            "cached_tokens": sum(r.cached_tokens or 0 for r in records),
            "llm_ms": sum(r.total_ms or 0 for r in records),
            "tool_calls": sum(len(r.tool_calls) for r in records),
        }
        model = next((r.model for r in reversed(records) if r.model), "")
        await self._upsert_turn(turn_id, session_id=session_id, owner_id=owner_id, role_id=role_id,
                                changes=dict(model=model or None, prompt_version=prompt_version or None,
                                             skills=list(skills), usage=usage, started_at=started_at))

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
