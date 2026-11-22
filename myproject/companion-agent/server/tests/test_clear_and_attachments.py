"""清空历史与消息附件。

两条都是主对话切到 agent 前必须补齐的能力：不补，切过去用户就丢功能。
"""

import os

import pytest

from companion.service.uploads.policy import MAX_MESSAGE_ATTACHMENTS

URL = (os.environ.get("COMPANION_TEST_DATABASE_URL") or os.environ.get("COMPANION_TEST_MYSQL_URL", ""))
pytestmark = pytest.mark.skipif(not URL, reason="COMPANION_TEST_DATABASE_URL not set")


def _client():
    import time

    from fastapi.testclient import TestClient

    from companion.agent.brain.fake import FakeBrain
    from companion.agent.memory.fake import InMemoryMemoryPort
    from companion.bootstrap.app import create_app
    from companion.bootstrap.platform import default_prompts
    from companion.bootstrap.platform import build_platform
    from companion.config import Settings

    # tos_endpoint="" 显式关掉对象存储，让这份夹具对开发机的 .env 免疫（hermetic）：
    # 仓库里的 .env 带着真 TOS_* 凭据时，build_platform 会挂上 api.direct，于是
    # send_message 对每个 upload_id 跑一次真实 bind —— 这些用例喂的是编造的 id
    # （u-1），归属查不到就 DirectRejected("KEY_NOT_FOUND") → 404，把「数量上限」这条
    # 契约钉成了「本机有没有 TOS 凭据」。顺带也省掉启动时那次真网络自检。
    # 附件数量上限（422）发生在 bind 之前的 pydantic 校验里，关掉直传不影响它被钉住。
    settings = Settings(companion_mysql_url=URL, companion_redis_url=os.environ.get("COMPANION_TEST_REDIS_URL", ""),
                        tos_endpoint="")
    platform = build_platform(settings, brain=FakeBrain(["好"]), prompts=default_prompts(),
                              memory_port=InMemoryMemoryPort())
    app = create_app(livekit_url="", platform=platform)
    # 每次用新的用户 id：全量跑时不能被上一次运行或别的用例的历史干扰
    user = str(int(time.time() * 1000) % 10**12)
    return TestClient(app), {"Authorization": f"Bearer {user}"}


def test_clearing_history_empties_only_that_session():
    client, h = _client()
    with client as c:
        keep = c.post("/v1/sessions", json={"role_id": "linche", "name": "保留"}, headers=h).json()["id"]
        clear = c.post("/v1/sessions", json={"role_id": "linche", "name": "清空"}, headers=h).json()["id"]
        for sid in (keep, clear):
            c.post(f"/v1/sessions/{sid}/messages", json={"text": "你好"}, headers=h)

        assert c.delete(f"/v1/sessions/{clear}/messages", headers=h).status_code == 204

        assert c.get(f"/v1/sessions/{clear}/messages", headers=h).json()["items"] == []
        kept = c.get(f"/v1/sessions/{keep}/messages", headers=h).json()["items"]
        assert [m["content"] for m in kept if m["role"] == "user"] == ["你好"], "别的会话不能被牵连"


def test_clearing_another_users_history_is_a_404():
    client, h = _client()
    with client as c:
        sid = c.post("/v1/sessions", json={"role_id": "linche", "name": "别人的"}, headers=h).json()["id"]
    other, h2 = _client()
    with other as c:
        assert c.delete(f"/v1/sessions/{sid}/messages", headers=h2).status_code == 404


def test_attachment_only_message_is_accepted_and_kept_on_the_message():
    client, h = _client()
    with client as c:
        sid = c.post("/v1/sessions", json={"role_id": "linche", "name": "发图"}, headers=h).json()["id"]
        r = c.post(f"/v1/sessions/{sid}/messages",
                   json={"text": "", "attachments": [{"upload_id": "u-1", "kind": "image", "name": "a.jpg"}]},
                   headers=h)
        assert r.status_code == 202, r.text
        items = c.get(f"/v1/sessions/{sid}/messages", headers=h).json()["items"]
        mine = [m for m in items if m["role"] == "user"]
        assert len(mine) == 1
        # 附件挂在消息上，刷新历史后还在
        assert mine[0].get("attachments", [])[0]["upload_id"] == "u-1"


def _att(i: int) -> dict:
    return {"upload_id": f"u-{i}", "kind": "image", "name": f"{i}.jpg"}


def test_send_rejects_more_than_the_attachment_cap():
    """超上限必须在进业务前被拒（422），否则客户端挑选上限和服务端校验就会各裁各的。"""
    client, h = _client()
    with client as c:
        sid = c.post("/v1/sessions", json={"role_id": "linche", "name": "超上限"}, headers=h).json()["id"]
        too_many = [_att(i) for i in range(MAX_MESSAGE_ATTACHMENTS + 1)]
        r = c.post(f"/v1/sessions/{sid}/messages", json={"text": "", "attachments": too_many}, headers=h)
        assert r.status_code == 422, r.text
        # 422 时一条都不能落库：校验发生在写库之前
        assert c.get(f"/v1/sessions/{sid}/messages", headers=h).json()["items"] == []
        # 错误体要带得出具体的数字：Android 端已经把 422 翻成人话给用户看（选超了要能说
        # 「最多 9 张」），而它在客户端读的是 too_long 这条上的 max_length/actual_length。
        # 只钉住 422 这个状态码的话，服务端把校验改成「按别的数字裁」或换成不带 ctx 的
        # 自定义 detail，客户端就会静默掉回一句没信息的兜底话。
        detail = r.json()["detail"]
        too_long = [d for d in detail if d["type"] == "too_long" and d["loc"][-1] == "attachments"]
        assert len(too_long) == 1, r.text
        assert too_long[0]["ctx"]["max_length"] == MAX_MESSAGE_ATTACHMENTS, r.text
        assert too_long[0]["ctx"]["actual_length"] == MAX_MESSAGE_ATTACHMENTS + 1, r.text


def test_send_accepts_exactly_the_attachment_cap():
    client, h = _client()
    with client as c:
        sid = c.post("/v1/sessions", json={"role_id": "linche", "name": "刚好上限"}, headers=h).json()["id"]
        exact = [_att(i) for i in range(MAX_MESSAGE_ATTACHMENTS)]
        r = c.post(f"/v1/sessions/{sid}/messages", json={"text": "", "attachments": exact}, headers=h)
        assert r.status_code == 202, r.text
        items = c.get(f"/v1/sessions/{sid}/messages", headers=h).json()["items"]
        mine = [m for m in items if m["role"] == "user"]
        assert len(mine) == 1
        assert len(mine[0].get("attachments", [])) == MAX_MESSAGE_ATTACHMENTS
