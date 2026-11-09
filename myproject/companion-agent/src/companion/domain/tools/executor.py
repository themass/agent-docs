"""动作：her 的「手」。

没有动作，她只能建议；有了动作，她能替用户做事。但能做事就必须有授权模型，
否则用户不敢用——参考 Rakazo 的做法，行动前要人工批准。

授权分三级，来自配置，**模型不能改自己的权限**。
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """动作的授权级别。

    READ  —— 只读，直接执行。
    CONFIRM —— 需要用户同意。语音模式下是一句追问，文字模式下是一条待确认消息。
    AUTO —— 自动执行，事后告知。只用于写 agent 自己的库、可撤销、无外部副作用的动作。
    """

    READ = "read"
    CONFIRM = "confirm"
    AUTO = "auto"


@dataclass(frozen=True)
class ActionSpec:
    name: str
    description: str
    parameters: dict
    permission: Permission
    idempotent: bool = True
    # 不可撤销的动作必须至少是 CONFIRM。打电话撤不回来，删数据也撤不回来。
    undoable: bool = True

    def __post_init__(self) -> None:
        if not self.undoable and self.permission == Permission.AUTO:
            raise ValueError(
                f"{self.name}: 不可撤销的动作不能是 AUTO，否则误触发无法补救"
            )


class ActionRegistry:
    """动作注册表。工具描述从这里生成给模型，执行也从这里走。"""

    def __init__(self) -> None:
        self._specs: dict[str, ActionSpec] = {}
        self._handlers: dict[str, Callable[..., Awaitable[Any]]] = {}

    def register(
        self, spec: ActionSpec, handler: Callable[..., Awaitable[Any]]
    ) -> None:
        if spec.name in self._specs:
            raise ValueError(f"duplicate action: {spec.name}")
        self._specs[spec.name] = spec
        self._handlers[spec.name] = handler

    def spec(self, name: str) -> ActionSpec | None:
        return self._specs.get(name)

    def specs(self) -> list[ActionSpec]:
        """给模型看的工具列表。权限不影响可见性——模型需要知道能做什么。"""
        return list(self._specs.values())

    def handler(self, name: str) -> Callable[..., Awaitable[Any]] | None:
        return self._handlers.get(name)

    def describe(self) -> list[dict]:
        return [
            {
                "name": s.name,
                "description": s.description,
                "parameters": s.parameters,
            }
            for s in self._specs.values()
        ]


@dataclass
class ActionRequest:
    name: str
    arguments: dict
    user_id: str
    character_id: str


@dataclass
class ActionOutcome:
    status: str          # executed | needs_confirmation | denied | failed
    result: Any = None
    reason: str = ""
    confirmation_id: str = ""


@dataclass
class ActionLog:
    """审计记录。用户能看到系统替他做了什么。"""

    id: str
    user_id: str
    character_id: str
    action: str
    args_hash: str
    status: str
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


def args_fingerprint(arguments: dict) -> str:
    """参数指纹。

    只存指纹不存原文：动作参数里可能有用户隐私（地址、人名），审计需要的是
    「同一次调用能对上」，不是「能读出参数」。
    """
    encoded = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


class ConfirmationStore(Protocol):
    async def create(self, request: ActionRequest) -> str: ...

    async def take(self, confirmation_id: str, user_id: str) -> ActionRequest | None: ...

    async def list_for(self, user_id: str) -> list[tuple[str, ActionRequest]]: ...


class InMemoryConfirmations:
    """待确认动作。进程内，重启丢失——重启后未确认的动作本就该失效。"""

    def __init__(self) -> None:
        self._items: dict[str, ActionRequest] = {}

    async def create(self, request: ActionRequest) -> str:
        cid = f"cfm-{args_fingerprint(request.arguments)}-{len(self._items)}"
        self._items[cid] = request
        return cid

    async def take(self, confirmation_id: str, user_id: str) -> ActionRequest | None:
        request = self._items.get(confirmation_id)
        if request is None or request.user_id != user_id:
            return None
        return self._items.pop(confirmation_id)

    async def list_for(self, user_id: str) -> list[tuple[str, ActionRequest]]:
        """按用户列出待确认。用户维度在这里过滤，调用方不需要记得再筛一次。"""
        return [
            (cid, request)
            for cid, request in self._items.items()
            if request.user_id == user_id
        ]


class ActionExecutor:
    """按权限执行动作，所有执行（含拒绝与待确认）都留审计。"""

    def __init__(
        self,
        *,
        registry: ActionRegistry,
        confirmations: ConfirmationStore | None = None,
        log_sink: Callable[[ActionLog], None] | None = None,
    ) -> None:
        self._registry = registry
        self._confirmations = confirmations or InMemoryConfirmations()
        self._log_sink = log_sink
        self._logs: list[ActionLog] = []

    @property
    def logs(self) -> list[ActionLog]:
        return list(self._logs)

    async def execute(self, request: ActionRequest, *, confirmed: bool = False) -> ActionOutcome:
        spec = self._registry.spec(request.name)
        if spec is None:
            return self._finish(request, ActionOutcome("denied", reason="unknown_action"))

        if spec.permission == Permission.CONFIRM and not confirmed:
            cid = await self._confirmations.create(request)
            return self._finish(
                request,
                ActionOutcome("needs_confirmation", confirmation_id=cid),
            )

        handler = self._registry.handler(request.name)
        if handler is None:
            return self._finish(request, ActionOutcome("denied", reason="no_handler"))

        try:
            # 身份由服务端注入、覆盖模型给的任何 user_id：模型不能选择替谁做事。
            kwargs = {**request.arguments, "user_id": request.user_id}
            result = await handler(**kwargs)
        except Exception as exc:  # noqa: BLE001 —— 动作失败本身是正常结果
            logger.warning("action failed: %s: %s", request.name, exc)
            return self._finish(request, ActionOutcome("failed", reason=str(exc)))

        return self._finish(request, ActionOutcome("executed", result=result))

    async def confirm(self, confirmation_id: str, user_id: str) -> ActionOutcome:
        request = await self._confirmations.take(confirmation_id, user_id)
        if request is None:
            # 已失效、越权、或 id 不对——三种都按同样的方式拒绝，不泄露哪一种。
            return ActionOutcome("denied", reason="confirmation_invalid")
        return await self.execute(request, confirmed=True)

    async def discard(self, confirmation_id: str, user_id: str) -> bool:
        """用户拒绝。消费掉这条确认并留审计；不存在或不是他的返回 False。"""
        request = await self._confirmations.take(confirmation_id, user_id)
        if request is None:
            return False
        self._finish(request, ActionOutcome("declined"))
        return True

    async def pending(self, user_id: str) -> list[dict]:
        """待确认列表。只给出能渲染确认卡片的字段，原始参数是用户自己的，可以给。"""
        items = await self._confirmations.list_for(user_id)
        result = []
        for cid, request in items:
            spec = self._registry.spec(request.name)
            result.append(
                {
                    "confirmation_id": cid,
                    "user_id": request.user_id,
                    "character_id": request.character_id,
                    "action": request.name,
                    "description": spec.description if spec else "",
                    "arguments": dict(request.arguments),
                }
            )
        return result

    def _finish(self, request: ActionRequest, outcome: ActionOutcome) -> ActionOutcome:
        entry = ActionLog(
            id=f"log-{len(self._logs)}",
            user_id=request.user_id,
            character_id=request.character_id,
            action=request.name,
            args_hash=args_fingerprint(request.arguments),
            status=outcome.status,
        )
        self._logs.append(entry)
        if self._log_sink is not None:
            try:
                self._log_sink(entry)
            except Exception as exc:  # noqa: BLE001
                logger.debug("action log sink failed: %s", exc)
        return outcome
