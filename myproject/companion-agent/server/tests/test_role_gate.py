"""两个建会话入口的角色闸门：未知 role_id 一律 400 unknown_role。

背景（线上事故）：旧客户端把占位符 __default__ 当角色 id 发给服务端，会话建成
201，之后每条消息的回合都在 RoleProfileResolver 里抛 RoleNotFound 整轮失败。
闸门必须装在建会话这一刻——文字 /v1/sessions 与语音 /v1/voice/sessions
（后者会自动创建聊天会话，坏 id 不拦就直接落库）。
"""

from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.api.http.deps import AllowAllVerifier, build_current_user
from companion.api.http.routers.chat import ChatApi, build_router as build_chat_router
from companion.api.livekit.sessions_router import build_router as build_voice_router
from companion.service.room.sessions import SessionError


class Sessions:
    def __init__(self):
        self.created = []

    async def create(self, *, owner_id, role_id, name, locale):
        self.created.append(role_id)
        return SimpleNamespace(id=len(self.created), owner_id=owner_id, role_id=role_id,
                               name=name, locale=locale, updated_at=datetime.now(UTC))


async def _known(role_id, **_kw):
    return role_id in {"linche", "u_mine"}


def _chat_client(role_check=_known):
    api = ChatApi(sessions=Sessions(), messages=None, queue=None, control=None,
                  submit=None, drain=None, role_check=role_check)
    app = FastAPI()
    app.include_router(build_chat_router(api, build_current_user(AllowAllVerifier())))
    return TestClient(app), api


def test_chat_create_session_rejects_unknown_role_and_stores_nothing():
    client, api = _chat_client()
    r = client.post("/v1/sessions", json={"role_id": "__default__"},
                    headers={"Authorization": "Bearer 1001"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "unknown_role"
    assert api.sessions.created == []


def test_chat_create_session_allows_known_role():
    client, api = _chat_client()
    r = client.post("/v1/sessions", json={"role_id": "linche"},
                    headers={"Authorization": "Bearer 1001"})
    assert r.status_code == 201
    assert api.sessions.created == ["linche"]


def test_chat_without_role_check_keeps_old_behavior():
    """离线/测试装配没挂校验器：不拦（宁缺勿错杀），行为与闸门上线前一致。"""
    client, api = _chat_client(role_check=None)
    r = client.post("/v1/sessions", json={"role_id": "__default__"},
                    headers={"Authorization": "Bearer 1001"})
    assert r.status_code == 201
    assert api.sessions.created == ["__default__"]


def _voice_client(role_check=_known, service=None):
    if service is None:
        async def create(**kw):  # 默认替身：被调到就是测试要观察的点
            raise AssertionError("service.create must not run for unknown role")
        service = SimpleNamespace(create=create)
    app = FastAPI()
    app.include_router(build_voice_router(service, build_current_user(AllowAllVerifier()),
                                          chat_sessions=None, role_check=role_check))
    return TestClient(app)


def test_voice_create_session_rejects_unknown_role_before_provisioning():
    """未知角色必须拒在任何建房/发 token/落库之前——替身一旦被调到就是失败。"""
    client = _voice_client()
    r = client.post("/v1/voice/sessions", json={"character_id": "__default__"},
                    headers={"Authorization": "Bearer 1001"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "unknown_role"


def test_voice_known_role_still_reaches_the_service():
    """闸门放行后语音链路原样走：service.create 被调到（替身抛 AssertionError）= 通过。"""
    client = _voice_client()
    try:
        client.post("/v1/voice/sessions", json={"character_id": "linche"},
                    headers={"Authorization": "Bearer 1001"})
    except AssertionError:
        return
    raise AssertionError("expected the gate to pass through to service.create")


def test_voice_non_numeric_user_id_skips_gate_instead_of_crashing():
    """owner_id 是 int：非数字 user id 不进闸门（int() 会 ValueError→500）。
    生产里这类 id 由 resolve_chat_session 按既有语义拒绝；闸门不替它做、也不放歪。"""
    seen = {"create": False, "checked": []}

    async def create(**kw):
        seen["create"] = True
        raise SessionError("reached service")  # 映射为 400 纯文本，非 unknown_role

    async def spy(role_id, owner_id):
        seen["checked"].append(owner_id)
        return True

    client = _voice_client(role_check=spy, service=SimpleNamespace(create=create))
    r = client.post("/v1/voice/sessions", json={"character_id": "linche"},
                    headers={"Authorization": "Bearer alice"})
    assert seen["checked"] == []                       # 闸门整个跳过，没有 int("alice")
    assert r.status_code == 400 and "unknown_role" not in str(r.json()["detail"])
