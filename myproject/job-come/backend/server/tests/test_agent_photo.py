"""MCP photo requests use stored chat references, never model-supplied URLs/bytes."""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.authz import RunScope
from jc.db.base import Base
from jc.exceptions import NotFoundError
from jc.models.agent import AgentSession
from jc.models.agent_message import AgentMessage
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.agent_photo_service import read_photo_source, request_photo_crop
from jc.storage_keys import storage_key


@pytest.fixture
async def scope():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        db.add(User(id="user_a", email="a@fixture.test", password_hash="test"))
        db.add(User(id="user_b", email="b@fixture.test", password_hash="test"))
        db.add(
            Profile(
                id="profile_a",
                user_id="user_a",
                owner_kind="user",
                payload={"contact": {"name": "A"}},
                version=1,
            )
        )
        db.add(
            AgentSession(
                id="session_a",
                user_id="user_a",
                profile_id="profile_a",
                deerflow_thread_id="thread_a",
            )
        )
        db.add(AgentSession(id="session_b", user_id="user_b", deerflow_thread_id="thread_b"))
        await db.commit()
        yield RunScope(db=db, user_id="user_a", profile_id="profile_a", session_id="session_a")
    await engine.dispose()


def image(mid="message_a", index=0, **extra):
    return {
        "kind": "image",
        "name": "photo.jpg",
        "mime_type": "image/jpeg",
        "storage_key": storage_key("agent", "session_a", "attachments", f"{mid}-{index}.jpg"),
        **extra,
    }


async def message(scope, attachments, mid="message_a", session="session_a"):
    scope.db.add(
        AgentMessage(
            id=mid,
            session_id=session,
            role="user",
            event_type="message",
            payload_json=json.dumps({"attachments": attachments}),
        )
    )
    await scope.db.commit()


@pytest.mark.asyncio
async def test_tool_prepares_crop_not_a_silent_write(scope):
    from jc.mcp.handlers import profile_photo_set

    await message(scope, [image()])
    result = await profile_photo_set(scope)
    assert result["status"] == "photo_crop_required"
    assert result["message_id"] == "message_a" and result["attachment_index"] == 0
    assert result["profile_id"] == "profile_a" and result["session_id"] == "session_a"
    assert "storage_key" not in result and "data_url" not in result and "download_url" not in result
    profile = await scope.db.get(Profile, "profile_a")
    assert profile.version == 1 and "photo" not in profile.payload["contact"]


@pytest.mark.asyncio
async def test_multiple_images_require_selection(scope):
    await message(scope, [image(), image(index=1)])
    result = await request_photo_crop(scope)
    assert result["status"] == "photo_selection_required" and len(result["images"]) == 2
    assert all("storage_key" not in value for value in result["images"])
    selected = await request_photo_crop(scope, message_id="message_a", attachment_index=1)
    assert selected["status"] == "photo_crop_required" and selected["attachment_index"] == 1
    with pytest.raises(NotFoundError):
        await request_photo_crop(scope, message_id="message_a", attachment_index=9)


@pytest.mark.asyncio
async def test_other_session_message_and_user_cannot_be_used(scope):
    await message(scope, [image()], session="session_b")
    with pytest.raises(NotFoundError):
        await request_photo_crop(scope, message_id="message_a")
    scope.session_id = "session_b"
    with pytest.raises(NotFoundError):
        await request_photo_crop(scope)


@pytest.mark.asyncio
async def test_foreign_storage_key_and_arbitrary_url_are_rejected(scope):
    await message(scope, [image(storage_key="https://attacker.invalid/a.jpg")])
    with pytest.raises(NotFoundError):
        await request_photo_crop(scope)


@pytest.mark.asyncio
async def test_missing_archive_does_not_silently_choose_an_older_picture(scope):
    await message(scope, [image()])
    await message(scope, [image(mid="new_message", storage_key=None)], mid="new_message")
    with pytest.raises(NotFoundError):
        await request_photo_crop(scope)


@pytest.mark.asyncio
async def test_authenticated_reader_uses_server_owned_key(scope, monkeypatch):
    await message(scope, [image()])
    reads = []

    def read(key):
        reads.append(key)
        return b"fixture-jpeg"

    monkeypatch.setattr(
        "jc.services.agent_photo_service.get_storage_backend",
        lambda: SimpleNamespace(get_object_bytes=read),
    )
    raw, mime = await read_photo_source(scope, message_id="message_a", attachment_index=0)
    assert raw == b"fixture-jpeg" and mime == "image/jpeg"
    assert reads == [image()["storage_key"]]
    with pytest.raises(NotFoundError):
        await read_photo_source(scope, message_id="unknown", attachment_index=0)
    assert len(reads) == 1


def test_photo_tool_is_registered_and_available_to_resume_coach():
    import inspect

    from jc.agent.tool_catalog import tools_for_skill
    from jc.mcp.server import jc_profile_photo_set

    assert "jc_profile_photo_set" in {
        x["function"]["name"] for x in tools_for_skill("resume-coach")
    }
    params = inspect.signature(jc_profile_photo_set).parameters
    assert "jc_user_id" in params and "jc_session_id" in params
    assert not {"url", "storage_key", "data_url", "apply"} & params.keys()


@pytest.mark.asyncio
async def test_dispatch_uses_same_photo_contract_and_bounds_result(scope):
    from jc.mcp.handlers import dispatch_tool

    await message(scope, [image(name="照" * 5000 + ".jpg")])
    result = await dispatch_tool(scope, "jc_profile_photo_set", {})
    assert result["status"] == "photo_crop_required"
    assert len(json.dumps(result, ensure_ascii=False)) < 2000


@pytest.mark.asyncio
async def test_binary_endpoint_authz_headers_and_invalid_index(scope, monkeypatch):
    import httpx
    from agentkit.web.auth import UserActor
    from fastapi import FastAPI

    from jc.api.agent_router import router
    from jc.api.auth_router import register_exception_handlers
    from jc.api.deps import get_agent_service, require_user
    from jc.api.profile_router import register_profile_exception_handlers
    from jc.services.agent_service import AgentService

    await message(scope, [image()])
    monkeypatch.setattr(
        "jc.services.agent_photo_service.get_storage_backend",
        lambda: SimpleNamespace(get_object_bytes=lambda key: b"fixture-jpeg"),
    )
    app = FastAPI()
    register_exception_handlers(app)
    register_profile_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_agent_service] = lambda: AgentService(scope.db)
    app.dependency_overrides[require_user] = lambda: UserActor(
        user_id="user_a", session_id="auth_test"
    )
    path = "/api/v1/agent/sessions/session_a/messages/message_a/images/"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://fixture"
    ) as client:
        response = await client.get(path + "0")
        assert response.status_code == 200 and response.content == b"fixture-jpeg"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-type"] == "image/jpeg"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert (await client.get(path + "-1")).status_code == 422
        assert (await client.get(path + "99")).status_code == 404
        app.dependency_overrides[require_user] = lambda: UserActor(
            user_id="user_b", session_id="foreign_auth"
        )
        assert (await client.get(path + "0")).status_code == 404


def test_product_rules_do_not_deny_the_photo_tool():
    from pathlib import Path

    rules = (Path(__file__).resolve().parents[2] / "agent/deerflow/product_rules.md").read_text()
    assert "jc_profile_photo_set" in rules
    assert "没有设置照片的工具" not in rules
