"""后台任务的纯规则（O §2.1）：重试退避、死信、租约过期判断。无 I/O。"""

from __future__ import annotations

from datetime import datetime, timedelta

# 重试退避：第 1、2、3、4 次失败后分别等 1、4、16、64 分钟（O §2.1 的 1、4、16 再延伸一步）。
BACKOFF_MINUTES = (1, 4, 16, 64)
LEASE = timedelta(minutes=5)
LEASE_RENEW_EVERY_SECONDS = 60


def retry_delay(failed_attempts: int) -> timedelta:
    index = min(max(failed_attempts, 1), len(BACKOFF_MINUTES)) - 1
    return timedelta(minutes=BACKOFF_MINUTES[index])


def after_failure(attempts: int, max_attempts: int, now: datetime) -> tuple[str, datetime | None]:
    """返回 (新状态, 下次执行时间)。尝试次数用尽则 dead，不再排期。"""
    if attempts >= max_attempts:
        return "dead", None
    return "queued", now + retry_delay(attempts)


def lease_expired(lease_until: datetime | None, now: datetime) -> bool:
    return lease_until is None or lease_until <= now
