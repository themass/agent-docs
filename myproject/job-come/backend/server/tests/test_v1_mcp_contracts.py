"""V1 business contracts, using real SQLAlchemy persistence without remote resources."""
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.authz import RunScope
from jc.db.base import Base
from jc.mcp import handlers
from jc.models import *  # noqa: F403
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.profile_patch_service import apply_confirmed_patch


@pytest.fixture
async def ctx():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        db.add(User(id='usr_owner', email='owner@example.test', password_hash='test'))
        db.add(Profile(id='prof_owned', user_id='usr_owner', owner_kind='user',
                       payload={'contact': {'name': '测试用户'}}, version=1))
        db.add(Profile(id='prof_guest', owner_kind='guest', payload={}, version=1))
        db.add(AgentSession(id='session_owned', user_id='usr_owner', profile_id='prof_owned', deerflow_thread_id='thread_test'))
        await db.commit()
        yield RunScope(db=db, user_id='usr_owner', profile_id='prof_owned',
                      session_id='session_owned')
    await engine.dispose()




@pytest.mark.asyncio
async def test_mcp_cannot_read_guest_or_other_profile(ctx):
    with pytest.raises(PermissionError):
        await handlers.profile_get(ctx, 'prof_guest')
    ctx.user_id = None
    with pytest.raises(PermissionError):
        await handlers.profile_get(ctx)










def test_tool_surface_cannot_express_apply():
    """ADR-003 is enforced by the signature, not by filtering arguments.

    The old handler took `apply: bool` and the dispatcher remembered to pop it off
    the model's arguments. One forgotten `pop` was a confirmation bypass. Applying
    now lives in a different function that the tool layer does not import, so there
    is no argument a model could send that writes.
    """
    import inspect

    params = inspect.signature(handlers.profile_patch).parameters
    assert 'apply' not in params
    assert 'confirm_id' not in params




@pytest.mark.asyncio
async def test_confirmation_applies_once(ctx, monkeypatch):
    from jc.models.profile_patch_confirm import ProfilePatchConfirm
    ctx.db.add(ProfilePatchConfirm(id='confirm', user_id=ctx.user_id, session_id=ctx.session_id,
        profile_id=ctx.profile_id, patch={'summary': '已确认事实'}, preview={'version_before': 1}, status='pending'))
    await ctx.db.commit()
    result = await apply_confirmed_patch(ctx, confirm_id='confirm')
    assert result['version'] == 2
    assert result['payload']['summary'] == '已确认事实'
    await ctx.db.commit()
    retry = await apply_confirmed_patch(ctx, confirm_id='confirm')
    assert retry['version'] == 2 and retry['already_applied']

    # The CAS write bypasses `before_flush` (bare UPDATE, never an ORM
    # attribute assignment), so `apply_confirmed_patch` must snapshot
    # explicitly via `build_snapshot` — confirmed here end to end through
    # the real confirm flow, not just the isolated hook unit test.
    from sqlalchemy import select

    from jc.models.profile_snapshot import ProfileSnapshot

    snap = (
        await ctx.db.execute(
            select(ProfileSnapshot).where(ProfileSnapshot.profile_id == 'prof_owned')
        )
    ).scalar_one()
    assert snap.version_after == 2
    assert snap.source == 'agent_patch'
    assert snap.actor_user_id == 'usr_owner'
    assert '已确认事实' not in str(snap.payload)  # holds the PRE-write payload










@pytest.mark.asyncio
async def test_patch_tool_result_becomes_confirm_then_persists_version(ctx, monkeypatch):
    """Connect proposal -> harness confirm event -> approved write -> fresh DB read.

    Validation, durable commands, mapping, SQL CAS, snapshots and commit/readback
    are production code. This does not exercise a real LLM or Redis.
    """
    import json

    from sqlalchemy import select

    from jc.adapters.deerflow_harness_client import _map_raw_event
    result = await handlers.profile_patch(ctx, {'summary': '牵头订单服务改造，明确交付范围。'})
    assert result['status'] == 'pending_confirm'
    raw = SimpleNamespace(type='messages-tuple', data={
        'type': 'tool', 'name': 'jc_profile_patch',
        'content': json.dumps(result, ensure_ascii=False),
    })
    events = _map_raw_event(raw)
    confirm = next(e for e in events if e['type'] == 'confirm')
    assert confirm['confirm_id'].startswith('cfm_')
    assert 'merged' not in confirm['preview']
    before = await ctx.db.get(Profile, ctx.profile_id)
    assert before.version == 1
    assert before.payload.get('summary') != result['patch']['summary']
    applied = await apply_confirmed_patch(ctx, confirm_id=confirm['confirm_id'])
    await ctx.db.commit()
    ctx.db.expire_all()
    saved = (await ctx.db.execute(select(Profile).where(Profile.id == ctx.profile_id))).scalar_one()
    assert saved.version == applied['version'] == 2
    assert saved.payload['summary'] == '牵头订单服务改造，明确交付范围。'
    assert saved.payload['contact']['name'] == '测试用户'
    from jc.models.profile_patch_confirm import ProfilePatchConfirm
    assert (await ctx.db.get(ProfilePatchConfirm, confirm["confirm_id"])).status == "applied"








