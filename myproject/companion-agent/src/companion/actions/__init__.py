"""动作层：her 的「手」，带授权分级与审计。"""

from companion.actions.core import register_core_actions
from companion.actions.executor import (
    ActionExecutor,
    ActionLog,
    ActionOutcome,
    ActionRegistry,
    ActionRequest,
    ActionSpec,
    InMemoryConfirmations,
    Permission,
    args_fingerprint,
)

__all__ = [
    "ActionExecutor",
    "ActionLog",
    "ActionOutcome",
    "ActionRegistry",
    "ActionRequest",
    "ActionSpec",
    "InMemoryConfirmations",
    "Permission",
    "args_fingerprint",
    "register_core_actions",
]
