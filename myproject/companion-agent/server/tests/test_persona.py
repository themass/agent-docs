"""用户画像：合并规则、渲染、抽取解析、更新服务、接口（docs/her-research 建议 1）。

存储用进程内假实现；SQL 实现另有 test_persona_store.py（需要数据库）。
"""

import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.api.http.deps import AllowAllVerifier, build_current_user
from companion.api.http.routers.memory_v1 import build_router
from companion.app.persona.updater import PERSONA_JOB, PersonaUpdater
from companion.adapters.timeline.memory import InMemoryTimeline
from companion.domain.persona.extraction import parse_drafts, render_prompt
from companion.domain.persona.model import (
    ABORT, APPEND, DYNAMIC, STATIC, UPDATE, MergeAction, ProfileDraft, ProfileEntry, clean_draft, plan_merge,
    render_profile,
)


def entry(i=1, topic="职业", memo="做前端开发", **kw):
    base = dict(id=i, topic=topic, memo=memo, section=STATIC, is_inference=False, confidence=0.9,
                source_fact_ids=("f1",), mentioned_at=None, happened_at=None)
    base.update(kw)
    return ProfileEntry(**base)


# ---- 规则 ----

def test_sensitive_topics_and_memos_never_enter_the_profile():
    assert clean_draft(ProfileDraft("银行卡", "尾号 1234")) is None
    assert clean_draft(ProfileDraft("职业", "他的密码是 abc")) is None
    assert clean_draft(ProfileDraft("", "没有话题")) is None
    assert clean_draft(ProfileDraft("职业", "x")) is None          # 备忘太短
    assert clean_draft(ProfileDraft("职业", "做前端" * 100)).memo.__len__() <= 120


def test_merge_rules():
    assert plan_merge([], ProfileDraft("职业", "做前端开发")).kind == APPEND
    assert plan_merge([entry()], ProfileDraft("职业", "做前端开发")).kind == ABORT              # 没变
    changed = plan_merge([entry()], ProfileDraft("职业", "转做后端了"))
    assert (changed.kind, changed.replaces) == (UPDATE, 1)
    # 推断不能覆盖用户明说的事实
    guess = plan_merge([entry()], ProfileDraft("职业", "可能是设计师", is_inference=True))
    assert (guess.kind, guess.reason) == (ABORT, "inference_must_not_override_fact")
    # 用户说过「别再提」：不换个说法再生成
    assert plan_merge([entry(suppressed=True)], ProfileDraft("职业", "后端开发")).reason == "suppressed"
    # 被取代的旧条目不挡路
    assert plan_merge([entry(superseded_by=2)], ProfileDraft("职业", "后端开发")).kind == APPEND


def test_a_section_that_is_full_rejects_new_topics():
    full = [entry(i, topic=f"话题{i}") for i in range(1, 21)]
    assert plan_merge(full, ProfileDraft("新话题", "新的内容")).reason == "section_full"


def test_render_marks_guesses_and_drops_the_least_important_first():
    text = render_profile([entry(), entry(2, "性格", "比较内向", is_inference=True, confidence=0.5)], budget_chars=500)
    assert "职业：做前端开发" in text and "性格：比较内向（推测，不确定）" in text
    tight = render_profile([entry(), entry(2, "性格", "比较内向", is_inference=True, confidence=0.5),
                            entry(3, "近况", "最近在加班", section=DYNAMIC)], budget_chars=len(
        render_profile([entry()], budget_chars=500)) + 5)
    assert "做前端开发" in tight and "加班" not in tight and "内向" not in tight     # 事实最后才丢
    assert render_profile([entry()], budget_chars=0) == ""
    assert render_profile([entry(superseded_by=9), entry(2, suppressed=True)], budget_chars=500) == ""


# ---- 抽取解析 ----

def test_parse_drops_invented_fact_refs_and_caps_inference_confidence():
    raw = json.dumps({"entries": [
        {"topic": "职业", "memo": "做前端开发", "section": "static", "inference": False, "confidence": 0.9,
         "sources": ["F1", "F99"]},
        {"topic": "性格", "memo": "比较内向", "inference": True, "confidence": 0.99, "sources": []},
        {"topic": "银行卡", "memo": "尾号 1234"}]}, ensure_ascii=False)
    drafts = parse_drafts("好的：```json\n" + raw + "\n```", fact_ids={"F1": "fact-1"})
    assert [(d.topic, d.source_fact_ids, d.confidence) for d in drafts] == [
        ("职业", ("fact-1",), 0.9), ("性格", (), 0.6)]
    assert parse_drafts("不是 json", fact_ids={}) == [] and parse_drafts("", fact_ids={}) == []


def test_prompt_survives_json_braces_and_numbers_the_facts():
    p = render_prompt(existing=[entry()], fact_lines=[("F1", "在做前端")], utterances=["我最近在加班"])
    assert "F1. 在做前端" in p and "职业：做前端开发" in p and "我最近在加班" in p and "{{" not in p


# ---- 更新服务 ----

class Store:
    def __init__(self, entries=()):
        self.entries = list(entries)
        self.pending = 0
        self.cursor_id = 0
        self.applied = []

    async def list_entries(self, *, owner_id, role_id, include_history=False):
        return list(self.entries) if include_history else [e for e in self.entries if e.current]

    async def apply(self, *, owner_id, role_id, actions):
        self.applied += actions
        return len(actions)

    async def advance(self, *, owner_id, role_id, last_message_id, add_chars):
        self.pending += add_chars
        return self.pending

    async def cursor(self, *, owner_id, role_id):
        return (self.cursor_id, self.pending)

    async def reset_pending(self, *, owner_id, role_id, last_message_id):
        self.pending, self.cursor_id = 0, last_message_id


class Jobs:
    def __init__(self):
        self.items = []

    async def enqueue(self, *, kind, payload, run_after, dedupe_key=None, max_attempts=5):
        self.items.append((kind, dedupe_key))
        return True


class Memory:
    async def list_for_user(self, user_id, limit=50, offset=0):
        from types import SimpleNamespace
        return [SimpleNamespace(id="fact-1", content="在做前端开发")]


class Messages:
    def __init__(self, rows):
        self.rows = rows

    async def list_after(self, *, owner_id, session_id, after_id, limit):
        return [m for m in self.rows if m.id > after_id][:limit]


def msg(i, role="user", text="我最近在加班", kind="chat"):
    from types import SimpleNamespace
    return SimpleNamespace(id=i, role=role, content=text, kind=kind)


def llm_returning(payload):
    async def call(prompt):
        call.prompts.append(prompt)
        return json.dumps(payload, ensure_ascii=False)

    call.prompts = []
    return call


async def test_updates_are_batched_not_per_turn():
    store, jobs = Store(), Jobs()
    updater = PersonaUpdater(store=store, memory=Memory(), messages=Messages([]), llm=llm_returning({}),
                             trigger_chars=600)
    assert not await updater.note_turn(owner_id=7, role_id="linche", last_message_id=1, user_text="x" * 300,
                                       jobs=jobs, session_id=3)
    assert jobs.items == []                                    # 字数不够：只记数，不入队
    assert await updater.note_turn(owner_id=7, role_id="linche", last_message_id=2, user_text="x" * 400,
                                   jobs=jobs, session_id=3)
    assert jobs.items == [(PERSONA_JOB, f"{PERSONA_JOB}:7:linche:2")]
    assert not await updater.note_turn(owner_id=7, role_id="linche", last_message_id=3, user_text="   ",
                                       jobs=jobs, session_id=3)


async def test_run_merges_drafts_and_keeps_only_the_best_per_topic():
    store = Store()
    llm = llm_returning({"entries": [
        {"topic": "职业", "memo": "做前端开发", "confidence": 0.7, "sources": ["F1"]},
        {"topic": "职业", "memo": "在一家公司做前端", "confidence": 0.9, "sources": ["F1"]},
        {"topic": "近况", "memo": "最近在加班", "section": "dynamic", "confidence": 0.8, "sources": []}]})
    updater = PersonaUpdater(store=store, memory=Memory(), messages=Messages([msg(1), msg(2, "assistant", "辛苦了")]),
                             llm=llm)
    written = await updater.run(owner_id=7, role_id="linche", session_id=3, up_to_message_id=2)
    assert written == 2
    topics = {a.draft.topic: a.draft.memo for a in store.applied}
    assert topics == {"职业": "在一家公司做前端", "近况": "最近在加班"}      # 同话题只留置信度高的
    assert store.applied[0].draft.source_fact_ids == ("fact-1",)         # 短编号换回真实 id
    assert "辛苦了" not in llm.prompts[0]                                # 角色说的话不进提示词
    assert store.cursor_id == 2 and store.pending == 0


async def test_a_failing_model_keeps_the_cursor_for_the_retry():
    async def broken(prompt):
        raise RuntimeError("model down")

    store = Store()
    store.pending = 700
    updater = PersonaUpdater(store=store, memory=Memory(), messages=Messages([msg(1)]), llm=broken)
    with pytest.raises(RuntimeError):
        await updater.run(owner_id=7, role_id="linche", session_id=3, up_to_message_id=1)
    assert store.pending == 700 and store.cursor_id == 0


# ---- 接口 ----

class ApiStore(Store):
    def __init__(self, entries):
        super().__init__(entries)
        self.suppressed, self.deleted, self.dropped = [], [], []

    async def suppress(self, *, owner_id, entry_id):
        self.suppressed.append((owner_id, entry_id))
        return entry_id == 1

    async def delete(self, *, owner_id, entry_id):
        self.deleted.append((owner_id, entry_id))
        return entry_id == 1

    async def drop_for_facts(self, *, owner_id, fact_ids):
        self.dropped.append((owner_id, fact_ids))
        return 1


@pytest.fixture
def profile_client():
    from companion.memory.fake import InMemoryMemoryPort
    from memory_hub import AppConfig, MemoryHub

    store = ApiStore([entry(), entry(2, "性格", "比较内向", is_inference=True, confidence=0.5)])
    hub = MemoryHub.from_config([AppConfig("companion")], lambda cfg: InMemoryMemoryPort())
    app = FastAPI()
    app.include_router(build_router(memory=hub.for_app("companion"), timeline=InMemoryTimeline(),
                                    current_user=build_current_user(AllowAllVerifier()), persona=store))
    return TestClient(app), store


ME = {"Authorization": "Bearer 7"}


def test_profile_endpoints(profile_client):
    client, store = profile_client
    items = client.get("/v1/memory/profile?role_id=linche", headers=ME).json()["items"]
    assert [(i["topic"], i["is_inference"]) for i in items] == [("职业", False), ("性格", True)]
    assert client.get("/v1/memory/profile", headers=ME).json()["items"] == []     # 不带角色：不猜
    assert client.post("/v1/memory/profile/1/suppress", headers=ME).status_code == 204
    assert client.post("/v1/memory/profile/9/suppress", headers=ME).status_code == 404
    assert client.delete("/v1/memory/profile/1", headers=ME).status_code == 204
    assert store.suppressed[0] == (7, 1) and store.deleted[0] == (7, 1)


def test_deleting_or_rewriting_a_fact_removes_profile_entries_derived_from_it(profile_client):
    client, store = profile_client
    created = client.post("/v1/memory/facts?role_id=linche", json={"content": "在做前端开发"}, headers=ME).json()
    assert client.delete(f"/v1/memory/facts/{created['id']}?role_id=linche", headers=ME).status_code == 204
    assert store.dropped == [(7, [created["id"]])]
    created2 = client.post("/v1/memory/facts?role_id=linche", json={"content": "喜欢喝茶"}, headers=ME).json()
    before = len(store.dropped)
    assert client.patch(f"/v1/memory/facts/{created2['id']}?role_id=linche",
                        json={"content": "更喜欢绿茶"}, headers=ME).status_code == 200
    # 改写是「取代」，旧事实仍作为历史保留，画像的依据没丢，所以不联动删除
    assert len(store.dropped) == before
