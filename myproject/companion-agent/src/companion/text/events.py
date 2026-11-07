"""头像事件协议。

模型会在回复里夹带情绪标记（``[joy]``、``（开心）``），TTS 不该读出它们，前端
却要靠它们驱动表情。这里把标记从文本里剥掉，翻译成一串带版本号的事件。纯字符串
处理，不依赖任何框架，方便在 LiveKit 的 data channel 之前先单测。
"""

from __future__ import annotations

import re
from collections.abc import Iterable

AVATAR_PROTOCOL_VERSION = 1

# 标签 -> 规范情绪名。模型写中文还是英文都能认，前端只认规范名。
_EMOTIONS: dict[str, str] = {
    "joy": "joy",
    "happy": "joy",
    "smile": "joy",
    "开心": "joy",
    "高兴": "joy",
    "笑": "joy",
    "sad": "sad",
    "难过": "sad",
    "伤心": "sad",
    "angry": "angry",
    "生气": "angry",
    "愤怒": "angry",
    "surprised": "surprised",
    "surprise": "surprised",
    "惊讶": "surprised",
    "shy": "shy",
    "害羞": "shy",
    "tender": "tender",
    "温柔": "tender",
    "excited": "excited",
    "兴奋": "excited",
    "afraid": "afraid",
    "害怕": "afraid",
    "thinking": "thinking",
    "思考": "thinking",
    "neutral": "neutral",
    "平静": "neutral",
    "calm": "neutral",
}

# 方括号标签可以出现在句中。否定断言排除 markdown 链接 [text](url) 与 [ref][id]。
_BRACKET_TAG = re.compile(r"\[([A-Za-z一-鿿][A-Za-z0-9_\-一-鿿]{0,15})\](?![(\[])")
# 圆括号标签任意位置都认，但只认括号里是情绪词的——"（旁白）" 这类叙述留着
_PAREN_TAG = re.compile(r"[（(]\s*([^（）()\n]{1,12}?)\s*[）)]")
_SPACE_RUN = re.compile(r"[ \t]{2,}")


def _strip_tags(text: str, pattern: re.Pattern[str]) -> tuple[str, list[str]]:
    """按正则找标签，认识的剥掉并记下情绪，不认识的连原文保留。"""
    parts: list[str] = []
    emotions: list[str] = []
    pos = 0
    for m in pattern.finditer(text):
        emotion = _EMOTIONS.get(m.group(1).lower())
        if emotion is None:
            continue
        parts.append(text[pos : m.start()])
        emotions.append(emotion)
        pos = m.end()
    if not emotions:
        return text, []
    parts.append(text[pos:])
    return "".join(parts), emotions


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def strip_emotion_tags(text: str) -> tuple[str, list[str]]:
    """剥掉情绪标签，返回 (干净文本, 规范情绪名列表)。

    没有任何标签时原样返回，不碰空白——调用方可能依赖原始排版。
    """
    if not text:
        return text, []
    clean, paren = _strip_tags(text, _PAREN_TAG)
    clean, bracket = _strip_tags(clean, _BRACKET_TAG)
    emotions = _dedupe(paren + bracket)
    if not emotions:
        return text, []
    return _SPACE_RUN.sub(" ", clean).strip(), emotions


def to_avatar_events(
    emotions: Iterable[str] | None,
    state: str | None = None,
) -> list[dict[str, object]]:
    """情绪先发、状态后发，前端按顺序播。"""
    events: list[dict[str, object]] = [
        {"v": AVATAR_PROTOCOL_VERSION, "type": "emotion", "emotion": emotion}
        for emotion in _dedupe(emotions or ())
    ]
    if state:
        events.append({"v": AVATAR_PROTOCOL_VERSION, "type": "state", "state": state})
    return events
