"""把每次合成的结果归档：文本和耗时写进 ``ca_voice_turn``，音频（用户同意后）传对象存储。

一个回复可能分成几次 ``tts_node`` 调用（框架遇到 ``FlushSentinel`` 会分段合成），所以同一个回合的
几段在这里按 ``turn_id`` 累积：文本拼接，音频顺序拼接，每次都把完整的 WAV 重新传到同一个键，
最终留下的是这个回合完整的一段音频。
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Any

from companion.trace.qa import VoiceTurnRecord
from companion.voice.tts_capture import TtsSegment, pcm_to_wav

log = logging.getLogger("companion.voice.archive")

# 只缓存最近几个回合的累积音频。语音房间里回合是顺序发生的，最多同时有“正在播的”和“刚被打断的”。
MAX_OPEN_TURNS = 8


class _Turn:
    __slots__ = ("texts", "pcm", "rate", "channels", "truncated", "ttfb_ms", "audio_ms", "interrupted")

    def __init__(self) -> None:
        self.texts: list[str] = []
        self.pcm = bytearray()
        self.rate = 0
        self.channels = 1
        self.truncated = False
        self.ttfb_ms: int | None = None
        self.audio_ms = 0
        self.interrupted = False


class TtsArchiver:
    def __init__(self, *, qa: Any, compliance: Any = None, objects: Any = None, key_prefix: str = "",
                 provider: str = "", voice: str = "") -> None:
        self._qa = qa
        self._compliance = compliance
        self._objects = objects
        self._prefix = key_prefix
        self._provider, self._voice = provider, voice
        self._turns: OrderedDict[str, _Turn] = OrderedDict()

    def audio_key(self, *, owner_id: int, session_id: int, turn_id: str) -> str:
        return f"{self._prefix}qa/tts/{owner_id}/{session_id}/{turn_id}.wav"

    async def __call__(self, *, turn_id: str, session_id: int, owner_id: int, role_id: str,
                       user_message_id: int | None, segment: TtsSegment) -> None:
        turn = self._turns.pop(turn_id, None) or _Turn()
        self._turns[turn_id] = turn
        while len(self._turns) > MAX_OPEN_TURNS:
            self._turns.popitem(last=False)
        self._absorb(turn, segment)

        keep = await self._compliance.qa_content_allowed(owner_id=owner_id) if self._compliance is not None else False
        key = ""
        if keep and self._objects is not None and turn.pcm and turn.rate:
            key = self.audio_key(owner_id=owner_id, session_id=session_id, turn_id=turn_id)
            try:
                await self._objects.put(key=key, data=pcm_to_wav(bytes(turn.pcm), sample_rate=turn.rate,
                                                                 channels=turn.channels), content_type="audio/wav")
            except Exception:  # noqa: BLE001 —— 上传失败：文本照样记，音频键留空，不假装有音频
                log.warning("tts audio upload failed", extra={"turn_id": turn_id})
                key = ""
        await self._qa.record_voice_turn(VoiceTurnRecord(
            turn_id=turn_id, session_id=session_id, owner_id=owner_id, role_id=role_id,
            user_message_id=user_message_id, tts_provider=self._provider, tts_voice=self._voice,
            tts_text=list(turn.texts), audio_out_key=key, tts_ttfb_ms=turn.ttfb_ms, tts_audio_ms=turn.audio_ms,
            tts_truncated=turn.truncated, interrupted=True if turn.interrupted else None), keep_content=keep)

    @staticmethod
    def _absorb(turn: _Turn, seg: TtsSegment) -> None:
        if seg.text:
            turn.texts.append(seg.text)
        if turn.ttfb_ms is None:
            turn.ttfb_ms = seg.ttfb_ms
        if not seg.completed:
            turn.interrupted = True
        turn.truncated = turn.truncated or seg.truncated
        if not seg.pcm:
            return
        if not turn.rate:
            turn.rate, turn.channels = seg.sample_rate, seg.channels
        if (seg.sample_rate, seg.channels) != (turn.rate, turn.channels):
            turn.truncated = True      # 分段格式不一致，没法拼成一个 WAV
            return
        turn.pcm += seg.pcm
        turn.audio_ms = int(len(turn.pcm) // (2 * turn.channels) * 1000 / turn.rate)
