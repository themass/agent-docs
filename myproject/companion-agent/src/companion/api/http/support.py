"""HTTP 层共用的小工具：分页窗口与 ISO-8601 时间。

集中在一处，是因为这两件事每个路由都要用，而边界值写歪的后果不成比例：
分页上限漏了，一个 ``limit=100000`` 就能把内存后端拖垮；时区漏了，一条
提醒会静默错几个小时。复制粘贴保持一致性不可靠，所以只写一份。
"""

from __future__ import annotations

from datetime import UTC, datetime

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
# 深翻页没有产品需求，但要有个上限，否则后端实现可能被迫扫全表。
MAX_OFFSET = 1000


def clamp_window(limit: int | None, offset: int | None) -> tuple[int, int]:
    """把客户端给的窗口收进合法范围。

    越界不报错而是夹取：移动端的查询参数常来自缓存或旧版本客户端，一次
    422 会让整页打不开，而夹取的结果仍然是有用的数据。
    """
    resolved_limit = DEFAULT_LIMIT if limit is None else limit
    if resolved_limit < 1:
        resolved_limit = DEFAULT_LIMIT
    resolved_limit = min(resolved_limit, MAX_LIMIT)

    resolved_offset = 0 if offset is None else offset
    if resolved_offset < 0:
        resolved_offset = 0
    return resolved_limit, min(resolved_offset, MAX_OFFSET)


def iso_utc(value: datetime) -> str:
    """统一输出带 ``Z`` 的 UTC 时间，客户端不必猜时区。

    无时区的时间按 UTC 处理：存储层写进来的都应该带时区，这里兜底是为了
    不把 naive 时间当成本地时间换算——那会错得很难发现。
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime:
    """解析客户端时间，必须带时区。

    拒绝 naive 时间：服务端与用户可能不在同一时区，猜一个就等于制造一个
    「提醒提前/延后几小时」的 bug。
    """
    text = (value or "").strip()
    if not text:
        raise ValueError("timestamp is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid timestamp: {text}") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone, e.g. 2026-11-20T14:00:00Z")
    return parsed.astimezone(UTC)
