"""``speech.seg`` 的段号与估时（§9.3 / §9.7 / §13）。

纯函数，不碰网络也不碰 TTS。流式 LLM 出一句，就给这一句分配一个段号、估一个时长，
然后交给发送口（:mod:`companion.api.livekit.speech_publisher`）按协商结果发出去。

两件事：

1. **估时长要在该句开口前就齐全。** §9.6：段首前导的 cue 必须先于该段音频到达端侧，
   所以 ``est_ms`` 不能等 TTS 实测出来再给。按字符数估。
2. **有界。** §13 不变量 3：段数到达 :data:`MAX_SEGMENTS` 之后，剩下的句子照常朗读，
   但不再声明段（锚在它们上的 cue 由端侧按 NO_ANCHOR 丢弃并计数）。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from companion.agent.util.ids import new_ulid

#: §9.7：中文语速按 4.5–6 字/秒估，取中点。误差可达 ±20%，段起点精度有上界（见 §9.7）。
CHARS_PER_SECOND = 5.5

#: 段数上限。每条 ``speech.seg`` 远小于 200 字节，24 段不会碰到 ``MAX_PAYLOAD_BYTES``。
MAX_SEGMENTS = 24


@dataclass(frozen=True)
class PlannedSegment:
    idx: int
    text: str
    est_ms: int
    #: 可选实测 / 校正时长（§18 #2）。声明时通常不设；有值才上线，不升版。
    dur_ms: int | None = None
    #: 所属回合（契约 v2 §2.3）。有值才上线 ``speech.seg``，老端忽略未知键。
    #: 前缀计算也要用它把打断对回正在生成的回合。
    turn_id: str = ""

    @property
    def chars(self) -> int:
        return len(self.text)

    def seg_args(self, speech_id: str) -> dict[str, Any]:
        """``speech.seg`` 的 args（§9.3 / 契约 v2 §2.3）。

        ``dur_ms`` / ``turn_id`` 有值才带，老端忽略未知键。
        """
        args: dict[str, Any] = {
            "speech_id": speech_id,
            "idx": self.idx,
            "chars": self.chars,
            "est_ms": self.est_ms,
        }
        if self.dur_ms is not None:
            args["dur_ms"] = self.dur_ms
        if self.turn_id:
            args["turn_id"] = self.turn_id
        return args


def estimate_ms(text: str) -> int:
    """按字符数估一段的时长。至少 1 ms，免得空段把时间线压成同一个点。"""
    return max(1, round(len(text) * 1000 / CHARS_PER_SECOND))


def spoken_prefix(segments: Sequence[PlannedSegment], played_ms: int) -> tuple[str, int]:
    """「已经说出口的前缀」（契约 v2 §2.2）：完整播完的段 + 正在段的按字符比例部分。

    输入是端侧上报的 ``played_ms``（真实播放时钟）与我们自己声明的段序列
    （:class:`PlannedSegment` 的 ``est_ms`` 只有 ±20% 精度）。所以前缀是估计值——
    但它是「她说到哪儿」目前最好的口径：服务端没有播放时钟，端侧的数字是唯一
    真数据。返回 ``(前缀文本, 前缀字符数)``。
    """
    if played_ms <= 0 or not segments:
        return "", 0
    parts: list[str] = []
    elapsed = 0
    for seg in segments:
        end = elapsed + max(1, seg.est_ms)
        if played_ms >= end:
            parts.append(seg.text)
            elapsed = end
            continue
        if played_ms > elapsed:
            fraction = (played_ms - elapsed) / max(1, seg.est_ms)
            take = min(seg.chars, round(seg.chars * fraction))
            parts.append(seg.text[:take])
        break
    prefix = "".join(parts)
    return prefix, len(prefix)


class SpeechStream:
    """一轮回复的段号分配器。一句 :meth:`push` 一次，返回的段立即交给发送口。

    段号从 0 连续编，只计**已声明**的段。空白句不占号；超过 :data:`MAX_SEGMENTS` 的句子
    照样会被说出来，但 :meth:`push` 返回 ``None``，不再声明。
    """

    def __init__(self, *, turn_id: str, speech_id: str | None = None) -> None:
        self.speech_id = speech_id or f"sp_{new_ulid()}"
        self.turn_id = turn_id
        self._declared = 0

    @property
    def declared(self) -> int:
        return self._declared

    def push(self, text: str) -> PlannedSegment | None:
        """登记下一句。返回新段；空白或已满返回 ``None``（此句不声明）。"""
        if not text or not text.strip():
            return None
        if self._declared >= MAX_SEGMENTS:
            return None
        seg = PlannedSegment(idx=self._declared, text=text, est_ms=estimate_ms(text),
                             turn_id=self.turn_id)
        self._declared += 1
        return seg
