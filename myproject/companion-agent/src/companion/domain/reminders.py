"""定时提醒的领域规则（纯函数）。

时间由模型给出带时区的绝对时间（它先用 get_current_time 拿到现在，再把「明天下午 3 点」换算成绝对时间）；
这里只校验与换算，不做自然语言解析。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MIN_LEAD = timedelta(minutes=1)
MAX_HORIZON = timedelta(days=366)
MAX_CONTENT_CHARS = 200
RETRY_DELAY = timedelta(minutes=2)
MAX_ATTEMPTS = 3


class ReminderInvalid(ValueError):
    pass


@dataclass(frozen=True)
class DueTime:
    utc: datetime       # 无时区信息的 UTC，直接入库
    timezone: str       # 用户时区（展示用）


def normalize_due(at: datetime, *, timezone: str | None, now: datetime) -> DueTime:
    """``at`` 必须带时区；``now`` 为带时区的当前时间。"""
    if at.tzinfo is None:
        raise ReminderInvalid("time must include a timezone offset")
    tz_name = timezone or "UTC"
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ReminderInvalid(f"unknown timezone: {tz_name}") from exc
    due = at.astimezone(UTC)
    current = now.astimezone(UTC)
    if due < current + MIN_LEAD:
        raise ReminderInvalid("time must be at least one minute in the future")
    if due > current + MAX_HORIZON:
        raise ReminderInvalid("time must be within one year")
    return DueTime(utc=due.replace(tzinfo=None), timezone=tz_name)


def normalize_content(text: str) -> str:
    content = " ".join(text.split())
    if not content:
        raise ReminderInvalid("content is empty")
    if len(content) > MAX_CONTENT_CHARS:
        raise ReminderInvalid(f"content longer than {MAX_CONTENT_CHARS} characters")
    return content


def local_time_text(due_utc: datetime, timezone: str) -> str:
    local = due_utc.replace(tzinfo=UTC).astimezone(ZoneInfo(timezone))
    return local.strftime("%Y-%m-%d %H:%M")


def proactive_instruction(*, content: str, due_utc: datetime, timezone: str) -> str:
    """到点后发起主动回合时交给模型的输入。它不是用户说的话，消息以 kind=proactive 保存。"""
    return (
        "【系统提醒，不是用户说的话】"
        f"现在是 {local_time_text(due_utc, timezone)}（{timezone}）。"
        f"用户之前请你在这个时间提醒：{content}。"
        "请以你的角色身份主动联系用户，自然地提起这件事；不要提到「系统提醒」这几个字。"
    )
