"""从对话里抽取时间线事件。

与事实抽取分开：事件的判断标准是「这句话里有没有一个可以落到日历上的时间点」，
事实的判断标准是「这句话是不是在描述一个人」。混在一个提示词里，模型会把
「我下周三面试」既写进事实又写成事件，还会把「我讨厌面试」误记成事件。
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from datetime import datetime

from companion.service.timeline.models import EventKind, Recurrence, TimelineEvent

LLMCall = Callable[[str], Awaitable[str]]

EXTRACTION_PROMPT = """\
从下面这段对话里，找出**用户明确说出的、带时间点的事件**。

只抽取满足全部条件的：
1. 是用户自己的事，不是角色说的、不是假设的、不是过去重复发生的习惯；
2. 有一个能落到日历上的时间（日期、星期、相对时间如「下周三」「三天后」）；
3. 用户是在陈述，不是在提问或想象。

输出 JSON 数组，每项：
{"kind": "interview|birthday|exam|appointment|anniversary|trip|other",
 "title": "不超过 20 字的事件描述",
 "at": "ISO8601 时间，含时区",
 "recurrence": "none|yearly|monthly|weekly",
 "confidence": 0 到 1 之间的小数}

没有符合条件的事件就输出 []。不要解释，不要输出 JSON 以外的任何内容。

对话：
{conversation}
"""


async def extract_events(
    *,
    conversation: str,
    user_id: str,
    character_id: str,
    message_id: str,
    llm: LLMCall,
) -> list[TimelineEvent]:
    """跑一次抽取。模型输出不合法时返回空列表，不抛错。

    抽取失败不该让一个已经完成的回合变成错误——它只是少记了一条事件。
    """
    # 提示词里含 JSON 示例的大括号，不能用 str.format（会当成占位符）；只替换对话那一段。
    raw = await llm(EXTRACTION_PROMPT.replace("{conversation}", conversation))
    return parse_events(
        raw,
        user_id=user_id,
        character_id=character_id,
        message_id=message_id,
    )


def parse_events(
    raw: str,
    *,
    user_id: str,
    character_id: str,
    message_id: str,
) -> list[TimelineEvent]:
    payload = _extract_json_array(raw)
    if payload is None:
        return []

    events: list[TimelineEvent] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            continue
        at = _parse_time(item.get("at"))
        title = str(item.get("title") or "").strip()
        if at is None or not title:
            continue
        events.append(
            TimelineEvent(
                # id 由本地生成：后端不起作用，但必须稳定唯一，供后续 update/delete
                id=f"evt-{message_id}-{index}",
                user_id=user_id,
                kind=_parse_kind(item.get("kind")),
                title=title[:60],
                at=at,
                source_character_id=character_id,
                source_message_id=message_id,
                confidence=_parse_confidence(item.get("confidence")),
                recurrence=_parse_recurrence(item.get("recurrence")),
            )
        )
    return events


def _extract_json_array(raw: str) -> list | None:
    """模型常把 JSON 包在 ```json 里，或者在前后加一句话。取第一个数组即可。"""
    if not raw:
        return None
    fenced = re.search(r"```(?:json)?\s*(.+?)```", raw, re.S)
    candidate = fenced.group(1) if fenced else raw
    start, end = candidate.find("["), candidate.rfind("]")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_kind(value: object) -> EventKind:
    try:
        return EventKind(str(value))
    except ValueError:
        return EventKind.OTHER


def _parse_recurrence(value: object) -> Recurrence:
    try:
        return Recurrence(str(value))
    except ValueError:
        return Recurrence.NONE


def _parse_confidence(value: object) -> float:
    try:
        return max(0.0, min(1.0, float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        # 模型没给就给个中性值，不当作可信也不当作不可信。
        return 0.5
