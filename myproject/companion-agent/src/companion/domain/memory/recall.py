"""不依赖向量的记忆召回（词法排序）。纯逻辑，无 I/O。

- 中文（及其他无空格的字符）：同时保留单字与相邻两字，如「喜欢喝茶」→ 喜、欢、喝、茶、喜欢、欢喝、喝茶，
  使单字查询（「茶」）也能命中；
- 英文、阿拉伯文等有空格的文字：按词切分，去掉标点，统一小写；
- 分数 = 查询特征在记忆中出现的比例；相同分数按时间倒序（更近的优先）。

这是字面匹配，不是语义匹配：「咖啡」找不到「喜欢喝茶」。语义召回需要嵌入模型，本项目暂不使用。
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

T = TypeVar("T")

_PUNCT = re.compile(r"[\s\W_]+", re.UNICODE)


@dataclass(frozen=True)
class Scored(Generic[T]):
    item: T
    score: float


def _is_cjk_like(ch: str) -> bool:
    """无空格分词的文字：中日韩统一表意文字、假名、韩文音节、泰文等。"""
    if ch.isspace():
        return False
    name = unicodedata.name(ch, "")
    return name.startswith(("CJK", "HIRAGANA", "KATAKANA", "HANGUL", "THAI"))


def features(text: str) -> set[str]:
    """把一段文字切成特征集合：CJK 字符保留单字与相邻双字；其他文字按词。"""
    out: set[str] = set()
    for word in _PUNCT.split(text.casefold()):
        if not word:
            continue
        run: list[str] = []
        other: list[str] = []
        for ch in word:
            if _is_cjk_like(ch):
                if other:
                    out.add("".join(other))
                    other = []
                run.append(ch)
            else:
                if run:
                    out.update(_cjk_features(run))
                    run = []
                other.append(ch)
        if run:
            out.update(_cjk_features(run))
        if other:
            out.add("".join(other))
    out.discard("")
    return out


def _cjk_features(run: list[str]) -> set[str]:
    grams = {run[i] + run[i + 1] for i in range(len(run) - 1)}
    return grams | set(run)


def rank_scored(query: str, items: Iterable[tuple[T, str, datetime]], limit: int) -> list[Scored[T]]:
    """items 为 (记录, 内容, 创建时间)。返回带分数的前 limit 条（分数 > 0），排序见模块说明。"""
    q = features(query)
    if not q:
        return []
    scored: list[tuple[float, datetime, T]] = []
    for record, content, created_at in items:
        hit = q & features(content)
        if not hit:
            continue
        scored.append((len(hit) / len(q), created_at, record))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [Scored(record, score) for score, _at, record in scored[:limit]]


def rank(query: str, items: Iterable[tuple[T, str, datetime]], limit: int) -> list[T]:
    """同 rank_scored，只返回记录本身。"""
    return [row.item for row in rank_scored(query, items, limit)]
