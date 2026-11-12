"""TTS 准确性：把合成出的音频送回识别，和当初送进 TTS 的文本比，算字错率（CER）。

怎么读这个数：它测的是“合成 → 识别”一个来回的失真，**不是**纯粹的 TTS 错误率。
- 识别器自己会错，也会靠上下文把念错的字猜对（多音字最典型），所以 CER 偏低不等于 TTS 没问题；
- 数字、日期、英文缩写的读法不唯一（“2026” 读作“二零二六”还是“两千零二十六”），识别结果与原文的写法对不上，
  会被算成错误。所以适合比较**同一套数据下不同音色/供应商的相对好坏**，和盯着数值有没有突然变差，
  不适合当绝对指标，更不能用来证明“念得完全正确”。
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

_KEEP = re.compile(r"[^\w]", re.UNICODE)
_MAX_LEN = 2000         # 编辑距离是 O(n*m)，一条回复远到不了；设上限防止异常数据拖慢整批


def normalize(text: str) -> str:
    """统一写法后只保留字母数字汉字：全半角、大小写、标点、空白、emoji 都不该算成念错。"""
    return _KEEP.sub("", unicodedata.normalize("NFKC", text).lower()).replace("_", "")


def edit_distance(a: str, b: str) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


@dataclass(frozen=True)
class Cer:
    reference: str
    hypothesis: str
    edits: int
    length: int          # 参考文本归一化后的字数

    @property
    def rate(self) -> float:
        return self.edits / self.length if self.length else (0.0 if not self.hypothesis else 1.0)


def cer(reference: str, hypothesis: str) -> Cer:
    ref, hyp = normalize(reference)[:_MAX_LEN], normalize(hypothesis)[:_MAX_LEN]
    return Cer(reference=ref, hypothesis=hyp, edits=edit_distance(ref, hyp), length=len(ref))


@dataclass(frozen=True)
class TurnCheck:
    turn_id: str
    sent: str                    # 当初送进 TTS 的文本
    heard: str                   # 音频回灌识别得到的文本
    cer: float
    interrupted: bool


@dataclass(frozen=True)
class Summary:
    count: int
    mean_cer: float
    p90_cer: float
    worst: tuple[TurnCheck, ...]


def summarize(checks: Sequence[TurnCheck], *, worst_n: int = 5) -> Summary:
    if not checks:
        return Summary(0, 0.0, 0.0, ())
    rates = sorted(c.cer for c in checks)
    p90 = rates[min(len(rates) - 1, int(len(rates) * 0.9))]
    worst = tuple(sorted(checks, key=lambda c: c.cer, reverse=True)[:worst_n])
    return Summary(len(checks), sum(rates) / len(rates), p90, worst)


Fetch = Callable[[str], Awaitable[bytes]]
Transcribe = Callable[[bytes], Awaitable[str]]


async def check_rows(rows: Sequence[dict], *, fetch: Fetch, transcribe: Transcribe) -> list[TurnCheck]:
    """逐行检查。被打断的回合音频只到打断那一刻，文本却是整句，比对会虚高，所以单独标出而不混进去算。
    某一行取音频或识别失败就跳过这一行，不让一条坏数据废掉整批。"""
    out: list[TurnCheck] = []
    for row in rows:
        key, texts = row.get("audio_out_key"), row.get("tts_text")
        if not key or not texts:
            continue
        try:
            heard = await transcribe(await fetch(key))
        except Exception:  # noqa: BLE001
            continue
        sent = "".join(texts)
        out.append(TurnCheck(turn_id=row["turn_id"], sent=sent, heard=heard, cer=cer(sent, heard).rate,
                             interrupted=bool(row.get("interrupted"))))
    return out
