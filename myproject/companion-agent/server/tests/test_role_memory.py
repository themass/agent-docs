"""记忆按角色隔离：召回、写入、工具、记忆接口都只碰当前角色的记忆空间。"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.memory.fake import InMemoryMemoryPort
from companion.memory.recallers import MemoryPortRecaller, TimelineRecaller
from companion.timeline.memory import InMemoryTimeline
from companion.api.http.deps import AllowAllVerifier, build_current_user
from companion.api.http.routers.memory_v1 import build_router
from companion.memory.recorder import ExtractionRecorder
from companion.memory.hooks import RecallQuery, TurnRecord
from companion.memory.subject import role_subject
from companion.timeline.models import EventKind, TimelineEvent
from companion.memory.port import MemoryItem
from memory_hub import AppConfig, MemoryHub


def _scoped():
    port = InMemoryMemoryPort()
    return MemoryHub.from_config([AppConfig("companion")], lambda cfg: port).for_app("companion")


def test_role_subject_is_stable_and_colon_free():
    assert role_subject(7, "linche") == "7.linche"
    assert role_subject("7", None) == "7"
    odd = role_subject(7, "角色:一")
    assert ":" not in odd and odd.startswith("7.h") and odd == role_subject(7, "角色:一")
    assert role_subject(7, "a") != role_subject(7, "b")


async def test_recall_only_sees_current_role():
    memory = _scoped()
    await memory.add(role_subject(7, "linche"), [MemoryItem(id="a", content="喜欢喝茶")])
    await memory.add(role_subject(7, "sudai"), [MemoryItem(id="b", content="喜欢喝咖啡")])
    recaller = MemoryPortRecaller(memory)
    got = await recaller.recall(RecallQuery(user_id="7", scope="companion", text="喜欢喝", role_id="linche"))
    assert [i.text for i in got.items] == ["喜欢喝茶"]
    other = await recaller.recall(RecallQuery(user_id="8", scope="companion", text="喜欢喝", role_id="linche"))
    assert other.items == ()


async def test_timeline_recall_is_filtered_by_role():
    timeline = InMemoryTimeline()
    at = datetime.now(UTC) + timedelta(days=1)
    for eid, role in (("e1", "linche"), ("e2", "sudai")):
        await timeline.add(TimelineEvent(id=eid, user_id="7", kind=EventKind.OTHER, title=eid, at=at,
                                         source_character_id=role))
    got = await TimelineRecaller(timeline).recall(
        RecallQuery(user_id="7", scope="companion", text="", role_id="sudai"))
    assert [i.ref for i in got.items] == ["e2"]


async def test_recorder_writes_into_role_space():
    seen = {}

    class Extractor:
        async def extract(self, **kw):
            seen.update(kw)
            return []

    await ExtractionRecorder(Extractor()).record(TurnRecord(
        scope="companion", user_id="7", turn_id="t1", user_text="我养了一只猫", assistant_text="",
        occurred_at=datetime.now(UTC), role_id="linche"))
    assert seen["user_id"] == "7.linche"


async def test_tools_use_role_space():
    from companion.tools.builtin import register_builtin_tools
    from companion.tools.registry import ToolRegistry

    memory = _scoped()
    registry = ToolRegistry()
    register_builtin_tools(registry, memory=memory, timeline=InMemoryTimeline())
    ctx = lambda role: SimpleNamespace(owner_id=7, character_id=role, session_id=1, confirmation_id=None)  # noqa: E731
    remember = registry.get("remember_fact").handler
    recall = registry.get("recall_facts").handler
    from companion.tools.builtin import RecallFactsParams, RememberFactParams

    await remember(ctx("linche"), RememberFactParams(content="下周去杭州"))
    assert [i["content"] for i in await recall(ctx("linche"), RecallFactsParams(query="杭州"))] == ["下周去杭州"]
    assert await recall(ctx("sudai"), RecallFactsParams(query="杭州")) == []


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(build_router(memory=_scoped(), timeline=InMemoryTimeline(),
                                    current_user=build_current_user(AllowAllVerifier())))
    return TestClient(app)


ME = {"Authorization": "Bearer 7"}


def test_memory_api_scopes_facts_by_role(client):
    url = "/v1/memory/facts"
    fid = client.post(f"{url}?role_id=linche", json={"content": "喜欢喝茶"}, headers=ME).json()["id"]
    assert [i["content"] for i in client.get(f"{url}?role_id=linche", headers=ME).json()["items"]] == ["喜欢喝茶"]
    assert client.get(f"{url}?role_id=sudai", headers=ME).json()["items"] == []
    assert client.get(url, headers=ME).json()["items"] == []
    assert client.delete(f"{url}/{fid}?role_id=sudai", headers=ME).status_code == 404
    assert client.delete(f"{url}/{fid}?role_id=linche", headers=ME).status_code == 204
