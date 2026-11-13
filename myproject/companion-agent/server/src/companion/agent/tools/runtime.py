"""工具运行时（T §2.3–2.5）：校验 → 授权 → 确认或执行 → 截断 → 审计。

模型只决定「调哪个工具、传什么业务参数」。身份、权限、白名单全部来自服务端。
这里不调用模型，也不依赖 DeerFlow：图内中间件把工具调用交给这里处理。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError

from companion.agent.util.ids import new_ulid
from companion.agent.tools.policy import Verdict, authorize, fingerprint, truncate
from companion.agent.tools.registry import ToolRegistry
from companion.agent.tools.spec import Permission, ToolContext, ToolSpec
from companion.db.port import ConfirmationRecord, ConfirmationStore
from companion.agent.tools.port import ToolCallRecord, ToolCallStore

log = logging.getLogger("companion.tools")

CONFIRM_TTL = timedelta(hours=24)
SUMMARY_MAX = 200


@dataclass(frozen=True)
class ToolTurn:
    """一个回合里工具调用的上下文，由图内中间件从 runtime.context 构造。"""

    owner_id: int
    session_id: int
    turn_id: str
    character_id: str
    locale: str
    product: str
    allowed: frozenset[str]          # 本回合白名单（T §2.3）


@dataclass(frozen=True)
class ToolOutcome:
    status: str          # executed | needs_confirmation | invalid_args | not_available | failed | timeout
    model_text: str      # 回给模型的内容（JSON 字符串）
    confirmation_id: str | None = None


class ToolRuntime:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        confirmations: ConfirmationStore,
        audit: ToolCallStore | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._registry = registry
        self._confirmations = confirmations
        self._audit = audit
        self._clock = clock

    async def invoke(self, turn: ToolTurn, name: str, raw_args: dict[str, Any]) -> ToolOutcome:
        started = time.monotonic()
        registered = self._registry.get(name)
        spec = registered.spec if registered else None
        parsed, problem = _parse(spec, raw_args)
        verdict = authorize(spec, turn.allowed, args_valid=problem is None)

        if verdict is Verdict.NOT_AVAILABLE:
            outcome = ToolOutcome("not_available", _json({"error": "tool_not_available", "tool": name}))
        elif verdict is Verdict.INVALID_ARGS:
            outcome = ToolOutcome("invalid_args", _json({"error": "invalid_args", "tool": name, "detail": problem}))
        elif verdict is Verdict.CONFIRM:
            outcome = await self._request_confirmation(turn, spec, parsed)
        else:
            outcome = await self._execute(turn, registered.handler, spec, parsed)

        await self._record(turn, spec, raw_args, outcome, started)
        return outcome

    async def run_confirmed(self, *, owner_id: int, session_id: int, turn_id: str, character_id: str,
                            locale: str, name: str, args: dict[str, Any],
                            confirmation_id: str | None = None) -> ToolOutcome:
        """确认后执行快照参数。不做授权（已由用户确认），也不调用模型（T §2.4）。"""
        registered = self._registry.get(name)
        if registered is None:
            return ToolOutcome("failed", _json({"error": "tool_not_available", "tool": name}))
        parsed, problem = _parse(registered.spec, args)
        if problem is not None:
            return ToolOutcome("failed", _json({"error": "invalid_args", "detail": problem}))
        ctx = ToolContext(owner_id=owner_id, session_id=session_id, turn_id=turn_id,
                          character_id=character_id, locale=locale, confirmation_id=confirmation_id)
        started = time.monotonic()
        outcome = await self._execute_with_ctx(ctx, registered.handler, registered.spec, parsed)
        if self._audit is not None:
            await self._audit.append(ToolCallRecord(
                turn_id=turn_id, owner_id=owner_id, tool=name, permission=Permission.CONFIRM.value,
                args_fingerprint=fingerprint(name, args), status=outcome.status,
                latency_ms=int((time.monotonic() - started) * 1000), result_chars=len(outcome.model_text)))
        return outcome

    # ---- 内部 ----

    async def _request_confirmation(self, turn: ToolTurn, spec: ToolSpec, parsed: Any) -> ToolOutcome:
        args = parsed.model_dump(mode="json")
        confirmation_id = "cfm_" + new_ulid()
        now = self._clock()
        record = ConfirmationRecord(
            id=confirmation_id, owner_id=turn.owner_id, session_id=turn.session_id, turn_id=turn.turn_id,
            tool=spec.name, args=args, args_fingerprint=fingerprint(spec.name, args),
            title=spec.confirm_title[:120], summary=_summary(spec, args), status="pending",
            expires_at=now + CONFIRM_TTL,
        )
        await self._confirmations.create(record)
        text = _json({
            "status": "needs_confirmation",
            "confirmation_id": confirmation_id,
            "instruction": "已请求用户确认。请告诉用户需要确认，不要声称已经完成。",
        })
        return ToolOutcome("needs_confirmation", text, confirmation_id)

    async def _execute(self, turn: ToolTurn, handler: Callable[..., Any], spec: ToolSpec, parsed: Any) -> ToolOutcome:
        ctx = ToolContext(owner_id=turn.owner_id, session_id=turn.session_id, turn_id=turn.turn_id,
                          character_id=turn.character_id, locale=turn.locale)
        return await self._execute_with_ctx(ctx, handler, spec, parsed)

    async def _execute_with_ctx(self, ctx: ToolContext, handler: Callable[..., Any], spec: ToolSpec,
                                parsed: Any) -> ToolOutcome:
        try:
            result = await asyncio.wait_for(handler(ctx, parsed), timeout=spec.timeout_s)
        except TimeoutError:
            return ToolOutcome("timeout", _json({"error": "timeout", "tool": spec.name}))
        except Exception:  # noqa: BLE001 — 工具内部错误不泄露细节给模型
            log.exception("tool failed", extra={"tool": spec.name, "turn_id": ctx.turn_id})
            return ToolOutcome("failed", _json({"error": "tool_failed", "tool": spec.name}))
        body = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
        body, _cut = truncate(body, spec.result_budget_chars)
        return ToolOutcome("executed", _json({"status": "ok", "tool": spec.name, "result": body}))

    async def _record(self, turn: ToolTurn, spec: ToolSpec | None, raw_args: dict[str, Any],
                      outcome: ToolOutcome, started: float) -> None:
        if self._audit is None:
            return
        await self._audit.append(ToolCallRecord(
            turn_id=turn.turn_id, owner_id=turn.owner_id, tool=spec.name if spec else "unknown",
            permission=(spec.permission.value if spec else Permission.READ.value),
            args_fingerprint=fingerprint(spec.name if spec else "unknown", raw_args),
            status=outcome.status, latency_ms=int((time.monotonic() - started) * 1000),
            result_chars=len(outcome.model_text)))


def _parse(spec: ToolSpec | None, raw_args: dict[str, Any]) -> tuple[Any, str | None]:
    if spec is None:
        return None, "unknown tool"
    try:
        return spec.params.model_validate(raw_args or {}), None
    except ValidationError as exc:
        # 只把字段名与错误类型告诉模型，不回显用户输入原文。
        return None, "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in exc.errors())


def _summary(spec: ToolSpec, args: dict[str, Any]) -> str:
    parts = [f"{k}: {v}" for k, v in args.items()]
    return truncate(f"{spec.confirm_title}（{'；'.join(parts)}）", SUMMARY_MAX)[0]


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)
