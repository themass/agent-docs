"""``speech.begin`` 的计划：把一句话切成段、给每段估时长（§9.3 / §9.7 / §13）。

纯函数，不碰网络也不碰 TTS。调用方（回合 → TTS 的那一层）决定段怎么切；这里只负责
两件事：

1. **估时长要在 begin 时就齐全。** §9.6 的要点：`before` 类 cue 必须在它锚定的那段
   开口前到达端侧，所以 `est_ms` 不能等 TTS 实测出来再给。`est_ms` 必需，按字符数估。
2. **有界。** §13 不变量 3：每条 payload 有上限。段数超过 :data:`MAX_SEGMENTS` 时，
   尾部段合并进最后一段——段多了，端侧的累积误差也多，合并比截断安全。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from companion.agent.util.ids import new_ulid

#: §9.7：中文语速按 4.5–6 字/秒估，取中点。误差可达 ±20%，靠段起点校正收敛。
CHARS_PER_SECOND = 5.5

#: 段数上限。每段约 60 字节，24 段远低于 ``MAX_PAYLOAD_BYTES``（4096）。
MAX_SEGMENTS = 24


@dataclass(frozen=True)
class PlannedSegment:
    idx: int
    text: str
    est_ms: int

    @property
    def chars(self) -> int:
        return len(self.text)


@dataclass(frozen=True)
class SpeechPlan:
    speech_id: str
    turn_id: str
    segments: tuple[PlannedSegment, ...]
    total_est_ms: int
    voice: str | None = None

    def begin_args(self) -> dict[str, Any]:
        """``speech.begin`` 的 args（§9.3）。``dur_ms`` 此时还不知道，故不带。"""
        args: dict[str, Any] = {
            "speech_id": self.speech_id,
            "turn_id": self.turn_id,
            "segments": [
                {"idx": s.idx, "chars": s.chars, "est_ms": s.est_ms} for s in self.segments
            ],
            "total_est_ms": self.total_est_ms,
        }
        if self.voice:
            args["voice"] = self.voice
        return args


def estimate_ms(text: str) -> int:
    """按字符数估一段的时长。至少 1 ms，免得空段把时间线压成同一个点。"""
    return max(1, round(len(text) * 1000 / CHARS_PER_SECOND))


def plan_speech(
    texts: Sequence[str],
    *,
    turn_id: str,
    voice: str | None = None,
    speech_id: str | None = None,
) -> SpeechPlan | None:
    """把已经切好的段（``texts``）变成一份计划。

    空串段跳过（不占 idx）。全部为空返回 ``None``——没有可说的东西就不该发 begin。
    ``speech_id`` 缺省用 ULID（§10.3：不复用，墓碑才有意义）。
    """
    cleaned = [t for t in texts if t and t.strip()]
    if not cleaned:
        return None
    if len(cleaned) > MAX_SEGMENTS:
        head, tail = cleaned[: MAX_SEGMENTS - 1], cleaned[MAX_SEGMENTS - 1 :]
        cleaned = [*head, "".join(tail)]

    segments = tuple(
        PlannedSegment(idx=i, text=t, est_ms=estimate_ms(t)) for i, t in enumerate(cleaned)
    )
    return SpeechPlan(
        speech_id=speech_id or f"sp_{new_ulid()}",
        turn_id=turn_id,
        segments=segments,
        total_est_ms=sum(s.est_ms for s in segments),
        voice=voice,
    )


class SpeechStream:
    """边出边声明的一句话（§9.3.1 分批声明）。

    流式 LLM 出一句声明一句：第一句随 ``speech.begin`` 发，之后每句一条
    ``speech.extend``。这里只管段号与估时，不管发不发——发送由调用方按协商结果决定。

    段号从 0 连续编，只计**已声明**的段。空白句不占号；超过 :data:`MAX_SEGMENTS` 的句子
    照样会被说出来，但不再声明（§9.3.1：超出部分锚定的 cue 按 NO_ANCHOR 丢弃）。
    """

    def __init__(self, *, turn_id: str, voice: str | None = None, speech_id: str | None = None) -> None:
        self.speech_id = speech_id or f"sp_{new_ulid()}"
        self.turn_id = turn_id
        self.voice = voice
        self._segments: list[PlannedSegment] = []

    @property
    def declared(self) -> int:
        return len(self._segments)

    def push(self, text: str) -> PlannedSegment | None:
        """登记下一句。返回新段；空白或已满返回 ``None``（此句不声明）。"""
        if not text or not text.strip():
            return None
        if len(self._segments) >= MAX_SEGMENTS:
            return None
        seg = PlannedSegment(idx=len(self._segments), text=text, est_ms=estimate_ms(text))
        self._segments.append(seg)
        return seg

    def begin_plan(self, first: PlannedSegment) -> SpeechPlan:
        """第一段的 begin：只带这一段（§9.3.1：begin 带首批，至少 1 段）。"""
        return SpeechPlan(
            speech_id=self.speech_id,
            turn_id=self.turn_id,
            segments=(first,),
            total_est_ms=first.est_ms,
            voice=self.voice,
        )
