"""工具定义的构造期规则、授权判定、运行时与确认闭环（T §2）。"""

import dataclasses
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from companion.app.tools.builtin import register_builtin_tools
from companion.app.tools.confirmation import ConfirmationService
from companion.app.tools.runtime import ToolRuntime, ToolTurn
from companion.domain.tools.policy import Verdict, authorize, fingerprint, truncate
from companion.domain.tools.registry import ToolRegistry
from companion.domain.tools.spec import Permission, SideEffect, ToolSpec, ToolSpecError


class P(BaseModel):
    title: str = "x"


class Leaky(BaseModel):
    user_id: str


def spec(**kw):
    base = dict(name="sample_tool", description="d", params=P, permission=Permission.READ,
                side_effect=SideEffect.NONE)
    base.update(kw)
    return ToolSpec(**base)


@pytest.mark.parametrize("kwargs", [
    dict(name="drop_it", undoable=False, permission=Permission.AUTO, side_effect=SideEffect.OWN_DATA),
    dict(name="send_mail", permission=Permission.AUTO, side_effect=SideEffect.EXTERNAL),
    dict(name="remember_x", permission=Permission.AUTO, side_effect=SideEffect.NONE),
    dict(name="read_file_now"),
    dict(name="leaky_tool", params=Leaky),
    dict(name="create_thing", permission=Permission.CONFIRM, side_effect=SideEffect.EXTERNAL, confirm_title=""),
])
def test_construction_rules_reject_violations(kwargs):
    with pytest.raises(ToolSpecError):
        spec(**kwargs)


def test_valid_confirm_tool_is_accepted():
    s = spec(name="create_reminder", permission=Permission.CONFIRM, side_effect=SideEffect.EXTERNAL,
             confirm_title="建立提醒")
    assert s.permission is Permission.CONFIRM


def test_authorization_order_whitelist_then_args_then_permission():
    s = spec(name="create_reminder", permission=Permission.CONFIRM, side_effect=SideEffect.EXTERNAL,
             confirm_title="t")
    allowed = frozenset({"create_reminder"})
    assert authorize(s, frozenset(), True) is Verdict.NOT_AVAILABLE
    assert authorize(s, allowed, False) is Verdict.INVALID_ARGS
    assert authorize(s, allowed, True) is Verdict.CONFIRM
    assert authorize(None, allowed, True) is Verdict.NOT_AVAILABLE


def test_fingerprint_is_short_and_stable_and_truncate_marks_cut():
    assert len(fingerprint("t", {"a": 1})) == 16
    assert fingerprint("t", {"a": 1, "b": 2}) == fingerprint("t", {"b": 2, "a": 1})
    assert truncate("abcdef", 3) == ("ab…", True)
    assert truncate("ab", 3) == ("ab", False)


class Confirmations:
    def __init__(self):
        self.rows = {}

    async def create(self, rec):
        self.rows[rec.id] = rec

    async def get_pending(self, *, owner_id, confirmation_id):
        r = self.rows.get(confirmation_id)
        return r if r and r.owner_id == owner_id and r.status == "pending" else None

    async def list_pending(self, *, owner_id):
        return [r for r in self.rows.values() if r.owner_id == owner_id and r.status == "pending"]

    async def _move(self, owner_id, cid, src, dst):
        r = self.rows.get(cid)
        if r and r.owner_id == owner_id and r.status == src:
            self.rows[cid] = dataclasses.replace(r, status=dst)
            return True
        return False

    async def decide(self, *, owner_id, confirmation_id, status):
        return await self._move(owner_id, confirmation_id, "pending", status)

    async def finish(self, *, owner_id, confirmation_id, status):
        return await self._move(owner_id, confirmation_id, "processing", status)

    async def expire_due(self, *, now):
        n = 0
        for cid, r in list(self.rows.items()):
            if r.status == "pending" and r.expires_at <= now:
                self.rows[cid] = dataclasses.replace(r, status="expired")
                n += 1
        return n


class Audit:
    def __init__(self):
        self.rows = []

    async def append(self, rec):
        self.rows.append(rec)


class Messages:
    def __init__(self):
        self.rows = []

    async def append(self, **kw):
        m = SimpleNamespace(id=len(self.rows) + 1, **kw)
        self.rows.append(m)
        return m


def build():
    memory = SimpleNamespace(search=AsyncMock(return_value=[SimpleNamespace(content="喜欢茶")]), add=AsyncMock())
    timeline = SimpleNamespace(add=AsyncMock(), list_for_user=AsyncMock(return_value=[]))
    reg = ToolRegistry()
    register_builtin_tools(reg, memory=memory, timeline=timeline)
    confirmations, audit, messages = Confirmations(), Audit(), Messages()
    runtime = ToolRuntime(registry=reg, confirmations=confirmations, audit=audit)
    service = ConfirmationService(store=confirmations, messages=messages, runtime=runtime)
    return SimpleNamespace(memory=memory, timeline=timeline, confirmations=confirmations, audit=audit,
                           messages=messages, runtime=runtime, service=service)


def turn(allowed, owner=7):
    return ToolTurn(owner_id=owner, session_id=1, turn_id="T1", character_id="linche", locale="zh-CN",
                    product="roleplay", allowed=frozenset(allowed))


async def test_tool_outside_whitelist_is_not_executed():
    env = build()
    outcome = await env.runtime.invoke(turn({"recall_facts"}), "remember_fact", {"content": "我喜欢喝茶"})
    assert outcome.status == "not_available"
    assert env.memory.add.await_count == 0


async def test_invalid_arguments_are_reported_without_echoing_input():
    env = build()
    outcome = await env.runtime.invoke(turn({"recall_facts"}), "recall_facts", {"query": "茶", "limit": 99})
    assert outcome.status == "invalid_args"
    assert "茶" not in outcome.model_text


async def test_identity_comes_from_context_not_arguments():
    env = build()
    outcome = await env.runtime.invoke(turn({"recall_facts"}, owner=7), "recall_facts",
                                       {"query": "茶", "user_id": "99"})
    assert outcome.status == "executed"
    # 身份来自上下文；记忆按角色隔离，所以是「用户 + 当前角色」的记忆主体，而不是参数里的 99。
    assert env.memory.search.await_args.args[0] == "7.linche"


async def test_confirmation_requires_owner_and_runs_once_and_writes_action_message():
    env = build()
    created = await env.runtime.invoke(turn({"create_reminder"}), "create_reminder",
                                       {"title": "吃药", "at": "2026-12-01T09:00:00+00:00"})
    assert created.status == "needs_confirmation"
    assert env.timeline.add.await_count == 0
    cid = created.confirmation_id

    assert await env.service.decide(owner_id=8, confirmation_id=cid, accept=True) is None
    first = await env.service.decide(owner_id=7, confirmation_id=cid, accept=True)
    assert first.status == "executed"
    assert env.timeline.add.await_count == 1
    assert env.messages.rows[-1].kind == "action"
    assert await env.service.decide(owner_id=7, confirmation_id=cid, accept=True) is None


async def test_decline_never_executes():
    env = build()
    created = await env.runtime.invoke(turn({"create_reminder"}), "create_reminder",
                                       {"title": "喝水", "at": "2026-12-02T09:00:00+00:00"})
    result = await env.service.decide(owner_id=7, confirmation_id=created.confirmation_id, accept=False)
    assert result.status == "declined"
    assert env.timeline.add.await_count == 0


async def test_expired_confirmation_is_not_executed():
    env = build()
    created = await env.runtime.invoke(turn({"create_reminder"}), "create_reminder",
                                       {"title": "喝水", "at": "2026-12-02T09:00:00+00:00"})
    later = datetime.now(UTC) + timedelta(days=2)
    env.service._clock = lambda: later
    result = await env.service.decide(owner_id=7, confirmation_id=created.confirmation_id, accept=True)
    assert result.status == "expired"
    assert env.timeline.add.await_count == 0


async def test_every_call_is_audited_with_fingerprint():
    env = build()
    await env.runtime.invoke(turn({"recall_facts"}), "recall_facts", {"query": "茶"})
    await env.runtime.invoke(turn({"recall_facts"}), "remember_fact", {"content": "我喜欢喝茶"})
    assert [(a.tool, a.status) for a in env.audit.rows] == [("recall_facts", "executed"),
                                                             ("remember_fact", "not_available")]
    assert all(len(a.args_fingerprint) == 16 for a in env.audit.rows)
