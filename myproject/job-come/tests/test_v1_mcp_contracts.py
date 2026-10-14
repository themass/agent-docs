"""V1 business contracts, using real SQLAlchemy persistence without remote resources."""
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jobcome.db.base import Base
from jobcome.models import *  # noqa: F403
from jobcome.models.profile import Profile
from jobcome.models.user import User
from jobcome.mcp.context import McpRunContext
from jobcome.mcp import handlers
from jobcome.mcp.question_upsert import question_upsert
from jobcome.schemas.job import FitScoreResponse


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
        await db.commit()
        yield McpRunContext(db=db, user_id='usr_owner', profile_id='prof_owned',
                            session_id='session_owned')
    await engine.dispose()


@pytest.mark.asyncio
async def test_fit_returns_result_for_raw_jd(ctx, monkeypatch):
    async def score(self, **kwargs):
        return FitScoreResponse(job_id=None, score=80, recommendation='go', gaps=[], blockers=[])
    monkeypatch.setattr(handlers.FitScoreService, 'score', score)
    async def parse(self, **kwargs):
        return handlers.JdParserService._heuristic_parse(kwargs['raw_text'])
    monkeypatch.setattr(handlers.JdParserService, 'parse', parse)
    result = await handlers.fit_score(ctx, raw_jd='产品经理，用户研究和需求分析')
    assert result['score'] == 80


@pytest.mark.asyncio
async def test_mcp_cannot_read_guest_or_other_profile(ctx):
    with pytest.raises(PermissionError):
        await handlers.profile_get(ctx, 'prof_guest')
    ctx.user_id = None
    with pytest.raises(PermissionError):
        await handlers.profile_get(ctx)


@pytest.mark.asyncio
async def test_patch_preview_does_not_mutate_original(ctx, monkeypatch):
    async def pending(**kwargs):
        return SimpleNamespace(confirm_id='confirm_test', preview=kwargs['preview'])
    monkeypatch.setattr(handlers, 'create_pending', pending)
    result = await handlers.profile_patch(ctx, {'contact': {'name': '建议名字'}})
    assert result['status'] == 'pending_confirm'
    row = await handlers.ProfileStore(ctx.db).get_by_id(ctx.profile_id)
    assert row.payload['contact']['name'] == '测试用户'
    assert row.version == 1


@pytest.mark.asyncio
async def test_question_and_attempt_best_never_regresses(ctx):
    question = await question_upsert(ctx, stem='如何制定产品优先级？', question_type='case')
    first = await handlers.answer_save_attempt(ctx, question_id=question['id'],
             user_answer='基于用户价值和成本排序', coach_feedback={'score': 9})
    await handlers.answer_save_attempt(ctx, question_id=question['id'],
             user_answer='凭直觉排序', coach_feedback={'score': 8})
    row = await handlers.InterviewStore(ctx.db).get_question(question['id'])
    assert row.best_attempt_id == first['attempt_id']
    assert row.attempt_count == 2


@pytest.mark.asyncio
async def test_wrong_mock_relation_rejected_without_write(ctx):
    with pytest.raises(PermissionError):
        await question_upsert(ctx, stem='不应保存', mock_session_id='mock_other')
    assert await handlers.InterviewStore(ctx.db).count_questions(ctx.profile_id) == 0


@pytest.mark.asyncio
async def test_stdio_tools_match_registry():
    from jobcome.mcp.server import mcp
    from jobcome.mcp.registry import OPENAI_TOOLS
    actual = {tool.name for tool in await mcp.list_tools()}
    expected = {tool['function']['name'] for tool in OPENAI_TOOLS}
    assert actual == expected


@pytest.mark.asyncio
async def test_direct_apply_requires_confirmation(ctx):
    with pytest.raises(PermissionError):
        await handlers.profile_patch(ctx, {'summary': '修改'}, apply=True)


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['identity', 'stale', 'malformed'])
async def test_invalid_confirmation_is_not_consumed(ctx, monkeypatch, failure):
    pending = SimpleNamespace(user_id=ctx.user_id, session_id=ctx.session_id,
                              profile_id=ctx.profile_id, patch={'summary': '更新'},
                              preview={'version_before': 1})
    if failure == 'identity':
        pending.user_id = 'usr_other'
    elif failure == 'stale':
        pending.preview['version_before'] = 0
    else:
        pending.patch = {'contact': 'invalid'}
    consumed = []
    async def get(_):
        return pending
    async def pop(_):
        consumed.append(True)
        return pending
    monkeypatch.setattr(handlers, 'get_pending', get)
    monkeypatch.setattr(handlers, 'pop_pending', pop)
    with pytest.raises((PermissionError, ValueError)):
        await handlers.profile_patch(ctx, {}, confirm_id='confirm')
    assert not consumed


@pytest.mark.asyncio
async def test_confirmation_applies_once(ctx, monkeypatch):
    pending = SimpleNamespace(user_id=ctx.user_id, session_id=ctx.session_id,
                              profile_id=ctx.profile_id, patch={'summary': '已确认事实'},
                              preview={'version_before': 1})
    rows = {'confirm': pending}
    async def get(key):
        return rows.get(key)
    async def pop(key):
        return rows.pop(key, None)
    monkeypatch.setattr(handlers, 'get_pending', get)
    monkeypatch.setattr(handlers, 'pop_pending', pop)
    result = await handlers.profile_patch(ctx, {}, confirm_id='confirm')
    assert result['version'] == 2
    assert result['payload']['summary'] == '已确认事实'
    with pytest.raises(ValueError):
        await handlers.profile_patch(ctx, {}, confirm_id='confirm')


@pytest.mark.asyncio
async def test_mock_and_real_archive_closed_loop(ctx):
    from datetime import date
    from agentkit.web.auth import UserActor
    from jobcome.exceptions import ConflictError
    from jobcome.schemas.coach import MockSessionCreateRequest, InterviewSaveRequest
    from jobcome.services.interview_service import InterviewService
    service = InterviewService(ctx.db)
    actor = UserActor(user_id=ctx.user_id, session_id='login')
    with pytest.raises(ConflictError):
        await service.create_mock_session(actor=actor, body=MockSessionCreateRequest(profile_id=ctx.profile_id))
    session = await service.create_mock_session(actor=actor, body=MockSessionCreateRequest(profile_id=ctx.profile_id, mode='warmup'))
    question = await question_upsert(ctx, stem='如何判断运营活动的成功？', mock_session_id=session.id)
    await service.complete_mock_session(session.id, actor=actor)
    again = await service.complete_mock_session(session.id, actor=actor)
    assert again.status == 'completed'
    with pytest.raises(ConflictError):
        await question_upsert(ctx, stem='已结束不应再写入', mock_session_id=session.id)
    real = await question_upsert(ctx, stem='如何搭建财务分析体系？', source='real')
    record = await service.save_interview(ctx.profile_id, actor=actor, body=InterviewSaveRequest(
        company='互联网公司', role_title='财务分析', interview_date=date(2026, 10, 12), question_ids=[real['id']]))
    history = await service.list_interviews(ctx.profile_id, actor=actor)
    assert [r.id for r in history.interviews] == [record.id]
    assert question['id'] != real['id']
