"""Durable confirm lifecycle through real HTTP/service/SQL, no Redis or model mocks."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from agentkit.web.auth import UserActor
from fastapi import FastAPI
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.api.auth_router import register_exception_handlers
from jc.authz import RunScope
from jc.db.base import Base
from jc.models.agent import AgentSession
from jc.models.agent_message import AgentMessage
from jc.models.profile import Profile
from jc.models.profile_patch_confirm import ProfilePatchConfirm
from jc.models.profile_snapshot import ProfileSnapshot
from jc.models.user import User
from jc.schemas.agent import AgentConfirmRequest
from jc.services.agent_service import AgentService
from jc.services.profile_patch_service import propose_patch


@pytest.fixture
async def env(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/confirm.sqlite")

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        db.add(User(id="usr_owner", email="owner@example.test", password_hash="test"))
        db.add(User(id="usr_other", email="other@example.test", password_hash="test"))
        await db.flush()
        db.add(
            Profile(
                id="prof_owned",
                user_id="usr_owner",
                owner_kind="user",
                payload={"contact": {"name": "原姓名"}},
                version=1,
            )
        )
        await db.flush()
        db.add(
            AgentSession(
                id="session_owned",
                user_id="usr_owner",
                profile_id="prof_owned",
                deerflow_thread_id="thread",
            )
        )
        db.add(
            AgentSession(
                id="session_other",
                user_id="usr_owner",
                profile_id="prof_owned",
                deerflow_thread_id="thread_other",
            )
        )
        await db.commit()
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/api/v1/agent/sessions/{session_id}/confirm")
    async def confirm(session_id: str, body: AgentConfirmRequest):
        async with sessions() as db:
            try:
                return await AgentService(db).confirm_patch(
                    session_id,
                    actor=UserActor(user_id="usr_owner", session_id="auth_test"),
                    body=body,
                )
            except Exception:
                await db.rollback()
                raise

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://fixture"
    ) as client:
        yield SimpleNamespace(sessions=sessions, client=client)
    await engine.dispose()


def scope(db):
    return RunScope(db=db, user_id="usr_owner", profile_id="prof_owned", session_id="session_owned")


async def propose(env, text="修改后内容"):
    # A separate session represents the MCP process; HTTP uses another session.
    async with env.sessions() as db:
        result = await propose_patch(scope(db), patch={"summary": text})
        return result["confirm_id"]


async def click(env, confirm_id, approved=True, session_id="session_owned"):
    return await env.client.post(
        f"/api/v1/agent/sessions/{session_id}/confirm",
        json={"confirm_id": confirm_id, "approved": approved},
    )






@pytest.mark.asyncio
async def test_failure_does_not_consume_command_or_partially_save(env, monkeypatch):
    cid = await propose(env)
    from jc.stores.agent_message_store import AgentMessageStore

    original = AgentMessageStore.append

    async def broken(*args, **kwargs):
        raise RuntimeError("simulate audit failure after profile UPDATE")

    monkeypatch.setattr(AgentMessageStore, "append", broken)
    with pytest.raises(RuntimeError, match="audit failure"):
        await click(env, cid)
    async with env.sessions() as db:
        assert (await db.get(Profile, "prof_owned")).version == 1
        assert (await db.get(ProfilePatchConfirm, cid)).status == "pending"
        assert not (await db.execute(select(ProfileSnapshot))).scalars().all()
    monkeypatch.setattr(AgentMessageStore, "append", original)
    assert (await click(env, cid)).json()["version"] == 2






async def old_card(env, version=1):
    async with env.sessions() as db:
        db.add(
            AgentMessage(
                id="agm_legacy",
                session_id="session_owned",
                role="assistant",
                event_type="confirm",
                payload_json=json.dumps(
                    {
                        "confirm_id": "cfm_legacy",
                        "profile_id": "prof_owned",
                        "patch": {"summary": "历史卡片修改"},
                        "preview": {"version_before": version},
                    }
                ),
            )
        )
        await db.commit()
    return "cfm_legacy"








@pytest.mark.asyncio
async def test_owner_cannot_consume_another_users_command(env):
    cid = await propose(env)
    async with env.sessions() as db:
        row = await db.get(ProfilePatchConfirm, cid)
        row.user_id = "usr_other"
        await db.commit()
    response = await click(env, cid)
    assert response.status_code == 400 and response.json()["code"] == "confirmation_not_found"

@pytest.mark.asyncio
async def test_trace_style_paths_survive_confirm_http_and_fresh_db_read(env):
    original = {
        "contact": {"name": "原姓名"},
        "experiences": [{"id": "exp_tencent", "company": "腾讯", "title": "T11", "start_date": "2020-05",
                         "highlights": ["原文一", "原文二", "保留", "原文四"]}],
        "meta": {"source_locale": "zh-CN"},
        "i18n": {"zh-CN": {"experiences": [{"id": "exp_tencent", "title": "T11",
                                            "highlights": ["过期缓存"]}]}},
    }
    async with env.sessions() as db:
        profile = await db.get(Profile, "prof_owned")
        profile.payload = original
        await db.commit()
        proposal = await propose_patch(scope(db), patch={
            "experiences[0].highlights[0]": "修改一",
            "experiences[0].highlights[1]": "修改二",
            "experiences[0].highlights[3]": "修改三",
        })
    response = await click(env, proposal["confirm_id"])
    assert response.status_code == 200, response.text
    async with env.sessions() as db:
        profile = await db.get(Profile, "prof_owned")
        assert profile.payload["experiences"][0]["highlights"] == ["修改一", "修改二", "保留", "修改三"]
        assert profile.payload["i18n"]["zh-CN"]["experiences"][0]["highlights"] == ["修改一", "修改二", "保留", "修改三"]
        assert profile.version == response.json()["version"]




