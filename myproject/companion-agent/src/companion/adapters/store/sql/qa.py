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

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.adapters.store.sql.schema import llm_call, voice_turn


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
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    first_token_ms: int | None = None
    total_ms: int | None = None
    finish_reason: str = ""
    error_code: str = ""


@dataclass
class VoiceTurnRecord:
    turn_id: str
    session_id: int
    owner_id: int
    role_id: str = ""
    user_message_id: int | None = None
    stt_provider: str = ""
    stt_text: str = ""
    stt_confidence: float | None = None
    llm_text: str = ""
    tts_provider: str = ""
    tts_voice: str = ""
    tts_text: list[str] = field(default_factory=list)
    audio_in_key: str = ""
    audio_out_key: str = ""
    first_sentence_ms: int | None = None
    total_ms: int | None = None
    interrupted: bool = False


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
            input_tokens=r.input_tokens, output_tokens=r.output_tokens, cached_tokens=r.cached_tokens,
            first_token_ms=r.first_token_ms, total_ms=r.total_ms,
            finish_reason=r.finish_reason or None, error_code=r.error_code or None, created_at=_now(),
        ) for r in records]
        async with self._engine.begin() as conn:
            await conn.execute(insert(llm_call), rows)
        return len(rows)

    async def record_voice_turn(self, record: VoiceTurnRecord, *, keep_content: bool) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(insert(voice_turn).values(
                turn_id=record.turn_id, session_id=record.session_id, owner_id=record.owner_id,
                role_id=record.role_id or None, user_message_id=record.user_message_id, content_kept=keep_content,
                stt_provider=record.stt_provider or None,
                stt_text=record.stt_text if keep_content else None,
                stt_confidence=record.stt_confidence,
                llm_text=record.llm_text if keep_content else None,
                tts_provider=record.tts_provider or None, tts_voice=record.tts_voice or None,
                tts_text=list(record.tts_text) if keep_content else None,
                # 音频是用户的声音，同意之前一律不留
                audio_in_key=(record.audio_in_key or None) if keep_content else None,
                audio_out_key=(record.audio_out_key or None) if keep_content else None,
                first_sentence_ms=record.first_sentence_ms, total_ms=record.total_ms,
                interrupted=record.interrupted, created_at=_now()))

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
