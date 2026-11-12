"""清空历史与消息附件。

两条都是主对话切到 agent 前必须补齐的能力：不补，切过去用户就丢功能。
"""

import os

import pytest

URL = (os.environ.get("COMPANION_TEST_DATABASE_URL") or os.environ.get("COMPANION_TEST_MYSQL_URL", ""))
pytestmark = pytest.mark.skipif(not URL, reason="COMPANION_TEST_DATABASE_URL not set")


def _client():
    import time

    from fastapi.testclient import TestClient

    from companion.adapters.brain.fake import FakeBrain
    from companion.adapters.memory.fake import InMemoryMemoryPort
    from companion.bootstrap.app import create_app
    from companion.bootstrap.container import create_container
    from companion.bootstrap.platform import build_platform
    from companion.config import Settings

    container = create_container()
    settings = Settings(companion_mysql_url=URL, companion_redis_url=os.environ.get("COMPANION_TEST_REDIS_URL", ""))
    platform = build_platform(settings, brain=FakeBrain(["好"]), prompts=container.prompts,
                              memory_port=InMemoryMemoryPort())
    app = create_app(livekit_url="", run_initiative=False, platform=platform)
    # 每次用新的用户 id：全量跑时不能被上一次运行或别的用例的历史干扰
    user = str(int(time.time() * 1000) % 10**12)
    return TestClient(app), {"Authorization": f"Bearer {user}"}


def test_clearing_history_empties_only_that_session():
    client, h = _client()
    with client as c:
        keep = c.post("/api/agent/v1/sessions", json={"role_id": "linche", "name": "保留"}, headers=h).json()["id"]
        clear = c.post("/api/agent/v1/sessions", json={"role_id": "linche", "name": "清空"}, headers=h).json()["id"]
        for sid in (keep, clear):
            c.post(f"/api/agent/v1/sessions/{sid}/messages", json={"text": "你好"}, headers=h)

        assert c.delete(f"/api/agent/v1/sessions/{clear}/messages", headers=h).status_code == 204

        assert c.get(f"/api/agent/v1/sessions/{clear}/messages", headers=h).json()["items"] == []
        kept = c.get(f"/api/agent/v1/sessions/{keep}/messages", headers=h).json()["items"]
        assert [m["content"] for m in kept if m["role"] == "user"] == ["你好"], "别的会话不能被牵连"


def test_clearing_another_users_history_is_a_404():
    client, h = _client()
    with client as c:
        sid = c.post("/api/agent/v1/sessions", json={"role_id": "linche", "name": "别人的"}, headers=h).json()["id"]
    other, h2 = _client()
    with other as c:
        assert c.delete(f"/api/agent/v1/sessions/{sid}/messages", headers=h2).status_code == 404


def test_attachment_only_message_is_accepted_and_kept_on_the_message():
    client, h = _client()
    with client as c:
        sid = c.post("/api/agent/v1/sessions", json={"role_id": "linche", "name": "发图"}, headers=h).json()["id"]
        r = c.post(f"/api/agent/v1/sessions/{sid}/messages",
                   json={"text": "", "attachments": [{"upload_id": "u-1", "kind": "image", "name": "a.jpg"}]},
                   headers=h)
        assert r.status_code == 202, r.text
        items = c.get(f"/api/agent/v1/sessions/{sid}/messages", headers=h).json()["items"]
        mine = [m for m in items if m["role"] == "user"]
        assert len(mine) == 1
        # 附件挂在消息上，刷新历史后还在
        assert mine[0].get("attachments", [])[0]["upload_id"] == "u-1"
