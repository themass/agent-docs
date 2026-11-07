"""主动性子系统：什么时候、以什么方式、主动找用户。

与对话路径分开，因为约束不同（频控、安静时段、退订），失败代价也不同——
对话里回错一句话是体验问题，半夜误发一条推送是信任问题。

三段职责分得很清，因为它们各自错的方式不同：

- [InitiativeScheduler]：什么时候该判断（时间对不对）；
- [InitiativePolicy]：要不要开口（分寸对不对）；
- [ChannelRouter] / [InitiativeLoop]：说出去并记账（通道与去重对不对）。
"""

from companion.proactive.delivery import (
    ChannelRouter,
    DeliveryError,
    DeliveryPort,
    DeliveryReceipt,
    InAppDelivery,
    InMemorySendLedger,
    PushDelivery,
    RecordingDelivery,
    SendRecorder,
)
from companion.proactive.loop import (
    InitiativeLoop,
    InitiativeRunResult,
    in_quiet_hours,
    occurrence_key,
)
from companion.proactive.models import (
    Channel,
    InitiativeDecision,
    InitiativePreferences,
    InitiativeState,
    SendRecord,
)
from companion.proactive.policy import InitiativePolicy
from companion.proactive.scheduler import InitiativeScheduler, SchedulerResult

__all__ = [
    "Channel",
    "ChannelRouter",
    "DeliveryError",
    "DeliveryPort",
    "DeliveryReceipt",
    "InAppDelivery",
    "InMemorySendLedger",
    "InitiativeDecision",
    "InitiativeLoop",
    "InitiativePolicy",
    "InitiativePreferences",
    "InitiativeRunResult",
    "InitiativeScheduler",
    "InitiativeState",
    "PushDelivery",
    "RecordingDelivery",
    "SchedulerResult",
    "SendRecord",
    "SendRecorder",
    "in_quiet_hours",
    "occurrence_key",
]
