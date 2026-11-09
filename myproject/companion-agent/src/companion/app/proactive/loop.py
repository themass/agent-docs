"""主动性循环：一轮扫描 = 判断 → 开口 → 投递。

调度器只产出触发，投递层只管发一条；把两者接起来的那一段必须在同一个地方，
因为「发不发」这件事有三个互不相干的前提（策略同意、没发过、此刻不是半夜），
分散在三个调用点里就一定会漏掉一个。

一轮的顺序是固定的：

    scan(now) → 逐个触发：去重 → 安静时段 → 频控复检 → 回合 → 投递 → 记账

每一步的失败处理写在各处，但共同的原则只有一条：**宁可少发一条，不可多发一条**。
所以三类失败都是「记日志、放弃这一次」——回合失败不发半句，投递失败不补发，
去重命中不重发。

``run_once`` 不用定时器：一个扫描周期是一个纯函数式的调用，测试注入 ``now`` 就能
覆盖跨午夜、频控、重复扫描，而不必让测试等五分钟。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from typing import Any

from companion.app.chat.conversation import ConversationService, TurnContext
from companion.app.proactive.router import ChannelRouter
from companion.ports.delivery import DeliveryError, DeliveryReceipt
from companion.domain.proactive.models import Channel, InitiativePreferences, InitiativeState
from companion.app.proactive.scheduler import InitiativeScheduler
from companion.domain.text.events import strip_emotion_tags
from companion.domain.turn.trigger import Trigger

logger = logging.getLogger(__name__)

# 去重记录保留多久。它只需要覆盖「同一次发生不会被下一轮再扫到」的时间跨度——
# 扫描窗口是分钟级，留一天已经很宽裕。定长了只会白占内存。
_SEEN_TTL = timedelta(days=1)


def in_quiet_hours(now: time, preferences: InitiativePreferences) -> bool:
    """安静时段判定。

    策略里有一份同样的逻辑，这里是刻意的第二道：投递是不可撤销的，而策略的调用
    参数来自调度器的装配——装配错了，策略会「正确地」同意在半夜发。所以投递前
    必须自己再看一次时间，不能只信上游的决定。
    """
    start, end = preferences.quiet_start, preferences.quiet_end
    if start <= end:
        return start <= now < end
    return now >= start or now < end


def occurrence_key(trigger: Trigger, now: datetime) -> tuple[str, str, str]:
    """一次「发生」的身份：(user_id, event_id, occurrence)。

    用发生时间而不是扫描时间做 occurrence：同一件事在窗口内被扫到多次，身份不变；
    下一年的同一个生日是新的发生，身份不同。没有事件 id 的触发（问候这类）退化为
    「用户 + 来源 + 日期」，即一天最多一次。
    """
    event_id = str(trigger.payload.get("event_id") or trigger.origin or trigger.kind.value)
    occurrence = str(
        trigger.payload.get("occurrence")
        or trigger.payload.get("at")
        or now.date().isoformat()
    )
    return (trigger.user_id, event_id, occurrence)


@dataclass
class InitiativeRunResult:
    """一轮扫描的结果。三个列表都是给人看与给测试断言的，不参与后续判断。"""

    delivered: list[DeliveryReceipt] = field(default_factory=list)
    # (来源, 原因)：为什么没发。原因字符串要与策略的 reason 对得上，便于排障。
    skipped: list[tuple[str, str]] = field(default_factory=list)
    # (来源, 原因)：本该发但没发成。这些不会在下一轮自动重试。
    failed: list[tuple[str, str]] = field(default_factory=list)


class InitiativeLoop:
    """扫描、开口、投递。

    ``preferences_loader`` 与 ``state_loader`` 必须传与调度器同一份实现：
    前者用于投递侧的安静时段复检，后者用于投递后复检频控——否则一轮里五件事同时
    到期会五条一起发出去，策略的日上限只在下一轮才生效。
    """

    def __init__(
        self,
        *,
        scheduler: InitiativeScheduler,
        conversation: ConversationService,
        router: ChannelRouter,
        preferences_loader: Callable[[str], Awaitable[InitiativePreferences]] | None = None,
        state_loader: Callable[[str], Awaitable[InitiativeState]] | None = None,
        seen_ttl: timedelta = _SEEN_TTL,
    ) -> None:
        self._scheduler = scheduler
        self._conversation = conversation
        self._router = router
        self._preferences_loader = preferences_loader or _default_preferences
        self._state_loader = state_loader or _default_state
        self._seen_ttl = seen_ttl
        self._seen: dict[tuple[str, str, str], datetime] = {}

    async def run_once(self, now: datetime | None = None) -> InitiativeRunResult:
        current = now or datetime.now(UTC)
        result = InitiativeRunResult()
        self._prune(current)

        scan = await self._scheduler.scan(now=current)
        result.skipped.extend((user_id, reason) for user_id, reason in scan.skipped)

        for trigger in scan.triggers:
            await self._handle(trigger, current, result)
        return result

    async def _handle(
        self, trigger: Trigger, now: datetime, result: InitiativeRunResult
    ) -> None:
        key = occurrence_key(trigger, now)
        if key in self._seen:
            # 同一件事已经处理过。处理 ≠ 成功：回合失败或投递失败也算处理过，
            # 因为重试的收益远小于「用户收到一串重复消息」的代价。
            result.skipped.append((trigger.origin, "duplicate"))
            return

        preferences = await self._preferences_loader(trigger.user_id)

        if in_quiet_hours(now.time(), preferences):
            # 不去重地跳过：安静时段结束时这次发生可能仍在窗口内，那时该发。
            result.skipped.append((trigger.origin, "quiet_hours"))
            return

        if preferences.paused_until is not None and now < preferences.paused_until:
            result.skipped.append((trigger.origin, "paused"))
            return

        cap_reason = await self._cap_reason(trigger.user_id, preferences, now)
        if cap_reason is not None:
            result.skipped.append((trigger.origin, cap_reason))
            return

        # 先占位再动手：没有占位的话，一个必然失败的回合会每五分钟重跑一次，
        # 既烧 token 又可能在某次「恰好成功」时补发一条过期提醒。
        self._seen[key] = now

        text = await self._speak(trigger, result)
        if text is None:
            return

        channel = _channel_of(trigger)
        line = f"proactive send: user={trigger.user_id} origin={trigger.origin}"
        try:
            receipt = await self._router.send(
                user_id=trigger.user_id,
                character_id=trigger.character_id,
                text=text,
                channel=channel,
                trigger=trigger.origin,
                at=now,
                meta={
                    "origin": trigger.origin,
                    "trigger": trigger.kind.value,
                    "reason": trigger.payload.get("reason", ""),
                    "event_id": trigger.payload.get("event_id", ""),
                },
            )
        except Exception as exc:  # noqa: BLE001 —— 任何投递失败都只此一次
            # 不重试：补发的消息比漏发的更烦人（设计文档第 10 节）。
            logger.warning("%s delivery failed on %s: %s", line, channel.value, exc)
            result.failed.append((trigger.origin, f"delivery:{type(exc).__name__}"))
            return

        logger.info("%s delivered as %s id=%s", line, receipt.channel.value, receipt.id)
        result.delivered.append(receipt)

    async def _speak(self, trigger: Trigger, result: InitiativeRunResult) -> str | None:
        """跑主动回合，拿到一句可以直接发出去的话。失败返回 None。"""
        ctx = TurnContext.from_trigger(trigger)
        try:
            turn = await self._conversation.start_turn(ctx)
            chunks = [chunk async for chunk in turn.chunks]
        except Exception as exc:  # noqa: BLE001 —— 回合失败不是投递的是非题
            logger.warning("proactive turn failed for %s: %s", trigger.origin, exc)
            result.failed.append((trigger.origin, f"turn:{type(exc).__name__}"))
            return None

        if turn.denied_reason:
            # 安全拒绝：没有内容可发，也不该换一条路径绕过它。
            logger.info("proactive turn denied (%s) for %s", turn.denied_reason, trigger.origin)
            result.skipped.append((trigger.origin, f"denied:{turn.denied_reason}"))
            return None

        clean, _emotions = strip_emotion_tags("".join(chunks))
        text = clean.strip()
        if not text:
            # 空回合（模型没开口、或只吐了标签）不发空消息。
            logger.info("proactive turn produced no text for %s", trigger.origin)
            result.skipped.append((trigger.origin, "empty_turn"))
            return None
        return text

    async def _cap_reason(
        self, user_id: str, preferences: InitiativePreferences, now: datetime
    ) -> str | None:
        """投递前复检频控。检查的是**上一次投递之后**的状态，不是扫描开始时的快照。"""
        state = await self._state_loader(user_id)
        if state.count_within(now=now, days=1) >= preferences.max_per_day:
            return "daily_cap"
        if state.count_within(now=now, days=7) >= preferences.max_per_week:
            return "weekly_cap"
        return None

    def _prune(self, now: datetime) -> None:
        cutoff = now - self._seen_ttl
        for key in [k for k, at in self._seen.items() if at < cutoff]:
            del self._seen[key]


def _channel_of(trigger: Trigger) -> Channel:
    raw = str(trigger.payload.get("channel", Channel.IN_APP.value))
    try:
        return Channel(raw)
    except ValueError:
        # 通道名认不出时退回应用内：它不会在半夜响铃。
        logger.warning("unknown channel %r on %s, using in_app", raw, trigger.origin)
        return Channel.IN_APP


async def _default_preferences(user_id: str) -> InitiativePreferences:
    return InitiativePreferences()


async def _default_state(user_id: str) -> InitiativeState:
    return InitiativeState()


__all__ = ["InitiativeLoop", "InitiativeRunResult", "in_quiet_hours", "occurrence_key"]
