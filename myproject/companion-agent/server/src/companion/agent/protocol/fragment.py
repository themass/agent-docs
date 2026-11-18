"""双路径摄入：结构化 say+cues 片段，或情绪标签回落（v1 §7.1 / P3）。

结构化路径优先：整句（或一行）能解成 ``{"say", "cues"?}`` 就走它；
否则剥 ``[joy]`` / ``（开心）`` 标签，映射成同一份 :class:`CueIntent`。

**不硬切**：解不出结构化对象时，原文仍可作为朗读文本（标签剥掉）。
非法 cue 单独丢掉，say 保留——修一个动作不该重播整句（v1 §7.2）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from companion.agent.protocol.cue_intent import CueIntent, normalize_kind, phase_of_anchor
from companion.agent.text.events import strip_emotion_tags

#: 只认「整段看起来像 JSON 对象」的输入，避免把正文里偶然出现的 ``{`` 当片段。
_OBJECT_SHAPE = re.compile(r"^\s*\{.*\}\s*$", re.DOTALL)


@dataclass(frozen=True)
class Fragment:
    """一句可朗读文本 + 待编译意图。``source`` 供计数：structured / tag。"""

    say: str
    intents: tuple[CueIntent, ...] = ()
    source: str = "tag"  # "structured" | "tag"
    dropped_cues: int = 0


def try_parse_fragment(text: str) -> Fragment | None:
    """尝试把 ``text`` 解成结构化片段。失败返回 None（调用方走标签回落）。

    接受的最小形状：顶层是 object，且含字符串 ``say``（可空）。
    ``cues`` 缺省 / 非 list → 空列表；单条 cue 缺 name / 未知 kind → 丢那一条。
    """
    if not text or not _OBJECT_SHAPE.match(text):
        return None
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or "say" not in data:
        return None
    say = data.get("say")
    if say is None:
        say = ""
    if not isinstance(say, str):
        return None

    intents: list[CueIntent] = []
    dropped = 0
    raw_cues = data.get("cues", [])
    if raw_cues is None:
        raw_cues = []
    if not isinstance(raw_cues, list):
        # cues 形状坏了：整段仍可当结构化（say 合法），但 cues 全丢。
        return Fragment(say=say, intents=(), source="structured", dropped_cues=1)

    for item in raw_cues:
        intent = _cue_from_item(item)
        if intent is None:
            dropped += 1
            continue
        intents.append(intent)
    return Fragment(say=say, intents=tuple(intents), source="structured", dropped_cues=dropped)


def from_tags(text: str) -> Fragment:
    """标签回落：剥情绪标记 → ``CueIntent(kind=emotion, phase=start)``。"""
    clean, emotions = strip_emotion_tags(text)
    intents = tuple(
        CueIntent(kind="emotion", name=name, phase="start") for name in emotions
    )
    return Fragment(say=clean, intents=intents, source="tag")


def ingest(text: str) -> Fragment:
    """双路径入口：结构化优先，否则标签。"""
    frag = try_parse_fragment(text)
    return frag if frag is not None else from_tags(text)


def _cue_from_item(item: Any) -> CueIntent | None:
    if not isinstance(item, dict):
        return None
    kind = normalize_kind(item.get("kind"))
    name = item.get("name")
    if kind is None or not isinstance(name, str) or not name.strip():
        return None
    params = item.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return None
    # 只保留有限标量，拒绝嵌套对象 / URL 类字段（v1 §7.2）。
    clean_params: dict[str, Any] = {}
    for key, value in params.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, bool) or value is None:
            clean_params[key] = value
        elif isinstance(value, (int, float)) and value == value and abs(value) != float("inf"):
            clean_params[key] = value
        elif isinstance(value, str) and len(value) <= 64:
            clean_params[key] = value
    phase = phase_of_anchor(item.get("anchor"))
    return CueIntent(kind=kind, name=name.strip(), params=clean_params, phase=phase)
