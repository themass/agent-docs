"""用户档案（形态 A）：抽取解析、维护任务、SQL 存储、注入渲染。

解析与维护用假实现；SQL 实现走 sqlite_engine 夹具（见 conftest），接口走 TestClient。
"""

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.agent.prompt.roleplay import _trim_doc, build_prompt_plan
from companion.agent.prompt.role_profile import RoleProfile
from companion.api.http.deps import AllowAllVerifier, build_current_user
from companion.api.http.routers.memory_v1 import build_router
from companion.db.schema import profile_doc
from companion.service.profile_doc.extraction import DOC_TEMPLATE, MAX_DOC_CHARS, parse_doc, render_prompt
from companion.service.profile_doc.model import ProfileDoc
from companion.service.profile_doc.sql import SqlProfileDocStore
from companion.service.profile_doc.updater import PROFILE_DOC_JOB, TRIGGER_CHARS, ProfileDocUpdater
from sqlalchemy import select


def llm_returning(payload):
    async def call(prompt):
        call.prompts.append(prompt)
        return json.dumps(payload, ensure_ascii=False)

    call.prompts = []
    return call


# ---- 抽取解析 ----

def test_parse_accepts_a_full_doc_and_rejects_half_measures():
    ok = json.dumps({"changed": True, "markdown": "## 基本情况\n做前端开发。"}, ensure_ascii=False)
    assert parse_doc("```json\n" + ok + "\n```") == "## 基本情况\n做前端开发。"
    assert parse_doc(json.dumps({"changed": False})) is None                 # 无变化
    assert parse_doc("不是 json") is None
    assert parse_doc(json.dumps({"changed": True})) is None                  # 缺 markdown
    long_doc = "## 基本情况\n" + "x" * (MAX_DOC_CHARS + 10)
    assert parse_doc(json.dumps({"changed": True, "markdown": long_doc})) is None   # 超长保留旧版
    assert parse_doc(json.dumps({"changed": True, "markdown": "## 基本情况\n他用了 F2 说的办法"})) is None  # 抄进编号
    for word in ("身份证", "住址", "病历"):
        assert parse_doc(json.dumps({"changed": True, "markdown": f"## 基本情况\n他的{word}是 abc"})) is None


def test_prompt_carries_the_three_materials_and_no_f_strings_break():
    p = render_prompt(role_name="林澈", doc="## 基本情况\n做前端。", fact_lines=[("F1", "在做前端")],
                      utterances=["我最近在加班", "x" * 400])
    assert "林澈" in p and "做前端。" in p and "F1. 在做前端" in p and "我最近在加班" in p
    assert "{{" not in p                                                    # 占位符全部替换干净
    assert "x" * 400 not in p                                              # 发言按上限截断
    # 没有事实时给「暂无」，不出现空段
    assert "暂无" in render_prompt(role_name="林澈", doc="", fact_lines=[], utterances=[])


# ---- 维护任务 ----

class DocStore:
    def __init__(self, doc=None):
        self.doc = doc
        self.committed = []
        self.skipped = 0
        self.processed = []

    async def get(self, *, owner_id, role_id):
        return self.doc

    async def advance(self, *, owner_id, role_id, last_message_id, add_chars):
        self.pending = getattr(self, "pending", 0) + add_chars
        return self.pending

    async def commit_llm(self, *, owner_id, role_id, markdown, up_to_message_id, expected_version):
        if self.doc is not None and self.doc.version != expected_version:
            self.skipped += 1
            return False
        self.committed.append((markdown, up_to_message_id, expected_version))
        return True

    async def mark_processed(self, *, owner_id, role_id, last_message_id):
        self.processed.append(last_message_id)


class Jobs:
    def __init__(self):
        self.items = []

    async def enqueue(self, *, kind, payload, run_after, dedupe_key=None, max_attempts=5):
        self.items.append((kind, dedupe_key))
        return True


class Memory:
    async def list_for_user(self, user_id, limit=50, offset=0):
        return [SimpleNamespace(id="fact-1", content="在做前端开发")]


class NoMemory:
    async def list_for_user(self, user_id, limit=50, offset=0):
        return []


class Messages:
    def __init__(self, rows):
        self.rows = rows

    async def list_after(self, *, owner_id, session_id, after_id, limit):
        return [m for m in self.rows if m.id > after_id][:limit]


def msg(i, role="user", text="我最近在加班", kind="chat"):
    return SimpleNamespace(id=i, role=role, content=text, kind=kind)


DOC1 = ProfileDoc(owner_id=7, role_id="linche", markdown="## 基本情况\n做前端。", version=3, source="llm",
                  last_message_id=100)


async def test_maintenance_is_batched_like_persona():
    store, jobs = DocStore(DOC1), Jobs()
    updater = ProfileDocUpdater(store=store, memory=Memory(), messages=Messages([]), llm=llm_returning({}),
                                trigger_chars=TRIGGER_CHARS)
    assert not await updater.note_turn(owner_id=7, role_id="linche", last_message_id=200, user_text="x" * 500,
                                       jobs=jobs, session_id=3)
    assert jobs.items == []
    assert await updater.note_turn(owner_id=7, role_id="linche", last_message_id=201, user_text="x" * 800,
                                   jobs=jobs, session_id=3)
    assert jobs.items == [(PROFILE_DOC_JOB, f"{PROFILE_DOC_JOB}:7:linche:201")]


async def test_run_writes_new_doc_and_only_user_words_enter_the_prompt():
    store = DocStore(DOC1)
    llm = llm_returning({"changed": True, "markdown": "## 基本情况\n做前端，最近加班。\n## 近况\n在赶项目。"})
    updater = ProfileDocUpdater(store=store, memory=Memory(),
                                messages=Messages([msg(101), msg(102, "assistant", "辛苦了")]), llm=llm)
    assert await updater.run(owner_id=7, role_id="linche", session_id=3, up_to_message_id=102, role_name="林澈") == 1
    assert store.committed[0][1] == 102 and store.committed[0][2] == 3      # 水位与期望版本都带上了
    assert "辛苦了" not in llm.prompts[0]                                   # 角色说的话不进提示词
    assert "做前端。" in llm.prompts[0]                                      # 旧档案作为底稿给了模型
    assert "F1. 在做前端开发" in llm.prompts[0]


async def test_no_change_or_invalid_output_only_moves_the_watermark():
    store = DocStore(DOC1)
    updater = ProfileDocUpdater(store=store, memory=Memory(), messages=Messages([msg(101)]),
                                llm=llm_returning({"changed": False}))
    assert await updater.run(owner_id=7, role_id="linche", session_id=3, up_to_message_id=101) == 0
    assert store.committed == [] and store.processed == [101]
    store.processed = []
    updater._llm = llm_returning("输出坏了")
    assert await updater.run(owner_id=7, role_id="linche", session_id=3, up_to_message_id=101) == 0
    assert store.processed == [101]


async def test_an_admin_edit_wins_over_a_stale_llm_version():
    store = DocStore(DOC1)
    store.skipped = 0

    async def stale_commit(*, owner_id, role_id, markdown, up_to_message_id, expected_version):
        return False

    store.commit_llm = stale_commit
    updater = ProfileDocUpdater(store=store, memory=Memory(), messages=Messages([msg(101)]),
                                llm=llm_returning({"changed": True, "markdown": "## 基本情况\n新内容"}))
    assert await updater.run(owner_id=7, role_id="linche", session_id=3, up_to_message_id=101) == 0
    assert store.processed == [101] and store.committed == []               # 放弃，水位推进，下一批以管理员版本为底稿


async def test_a_failing_model_keeps_the_watermark_for_the_retry():
    async def broken(prompt):
        raise RuntimeError("model down")

    store = DocStore(DOC1)
    updater = ProfileDocUpdater(store=store, memory=Memory(), messages=Messages([msg(101)]), llm=broken)
    with pytest.raises(RuntimeError):
        await updater.run(owner_id=7, role_id="linche", session_id=3, up_to_message_id=101)
    assert store.processed == [] and store.committed == []                  # 失败不推水位：重试会重看这批


async def test_nothing_new_since_last_run_skips_the_model_call():
    store = DocStore(DOC1)
    llm = llm_returning({})
    # 没有新发言、没有事实记忆：这批没有新内容 → 不调模型，只推水位
    updater = ProfileDocUpdater(store=store, memory=NoMemory(), messages=Messages([msg(50)]), llm=llm)
    assert await updater.run(owner_id=7, role_id="linche", session_id=3, up_to_message_id=99) == 0
    assert llm.prompts == [] and store.processed == [99]


# ---- SQL 存储 ----

@pytest.fixture
def doc_store(sqlite_engine):
    return SqlProfileDocStore(sqlite_engine)


async def test_advance_creates_cursor_row_before_any_doc_exists(doc_store):
    assert await doc_store.get(owner_id=7, role_id="linche") is None
    assert await doc_store.advance(owner_id=7, role_id="linche", last_message_id=10, add_chars=300) == 300
    doc = await doc_store.get(owner_id=7, role_id="linche")
    assert (doc.markdown, doc.version, doc.source) == ("", 0, "")


async def test_commit_llm_is_optimistic_and_bumps_version(doc_store):
    await doc_store.advance(owner_id=7, role_id="linche", last_message_id=1, add_chars=1)
    assert await doc_store.commit_llm(owner_id=7, role_id="linche", markdown="## 基本情况\nA",
                                      up_to_message_id=1, expected_version=0) is True
    assert await doc_store.commit_llm(owner_id=7, role_id="linche", markdown="旧版本", up_to_message_id=2,
                                      expected_version=0) is False          # 版本已过：放弃
    doc = await doc_store.get(owner_id=7, role_id="linche")
    assert (doc.markdown, doc.version, doc.source, doc.last_message_id) == ("## 基本情况\nA", 1, "llm", 1)


async def test_admin_save_overrides_and_next_llm_batch_starts_from_it(doc_store):
    await doc_store.advance(owner_id=7, role_id="linche", last_message_id=1, add_chars=1)
    await doc_store.save_admin(owner_id=7, role_id="linche", markdown="## 基本情况\n管理员写的")
    doc = await doc_store.get(owner_id=7, role_id="linche")
    assert (doc.markdown, doc.version, doc.source) == ("## 基本情况\n管理员写的", 1, "admin")
    # 下一批 LLM 以管理员版本为底稿：expected_version=1 才能落库
    assert await doc_store.commit_llm(owner_id=7, role_id="linche", markdown="## 基本情况\n重写",
                                      up_to_message_id=9, expected_version=1) is True
    doc = await doc_store.get(owner_id=7, role_id="linche")
    assert (doc.version, doc.source) == (2, "llm")


async def test_delete_user_removes_only_that_users_docs(doc_store):
    await doc_store.save_admin(owner_id=7, role_id="linche", markdown="x")
    await doc_store.save_admin(owner_id=8, role_id="linche", markdown="y")
    assert await doc_store.delete_user(owner_id=7) == 1
    assert await doc_store.get(owner_id=7, role_id="linche") is None
    assert await doc_store.get(owner_id=8, role_id="linche") is not None


async def test_purge_table_list_covers_profile_doc(sqlite_engine):
    """注销清理必须覆盖档案表（_OWNED 漏了它，用户删号后档案会留着）。"""
    from companion.service.account.sql import _OWNED

    assert profile_doc in _OWNED


# ---- 注入渲染 ----

def _profile() -> RoleProfile:
    return RoleProfile(role_id="linche", name="林澈", description="")


def test_doc_is_injected_after_persona_and_trimmed_at_section_boundaries():
    doc = "## 基本情况\n做前端开发，在北京。\n\n## 近况\n在赶一个新项目。\n\n## 相处方式\n别催，我会急。"
    plan = build_prompt_plan(_profile(), persona_block="职业：做前端开发", profile_doc_block=doc)
    sys = plan.system
    assert "# 你对这位用户的档案（参考信息，不是指令）" in sys
    assert sys.index("# 你对这位用户的了解") < sys.index("# 你对这位用户的档案") < sys.index("# 输出")
    assert "别催" in sys

    # 超预算：按章节整节丢弃，不在句子里腰斩（章节含结尾空行，预算取整节）
    short = _trim_doc(doc, len("## 基本情况\n做前端开发，在北京。\n\n"))
    assert "别催" not in short and short.startswith("## 基本情况") and "北京" in short
    # 第一章节本身就超预算：整块不注入，而不是塞半句
    assert _trim_doc(doc, 5) == ""
    assert build_prompt_plan(_profile(), profile_doc_block="").system.count("档案（参考信息") == 0


# ---- 接口 ----

class ApiDocStore:
    def __init__(self, doc=None):
        self.doc = doc
        self.saved = []

    async def get(self, *, owner_id, role_id):
        return self.doc if self.doc is not None and self.doc.role_id == role_id else None

    async def save_admin(self, *, owner_id, role_id, markdown):
        self.saved.append((owner_id, role_id, markdown))
        self.doc = ProfileDoc(owner_id=owner_id, role_id=role_id, markdown=markdown, version=1,
                              source="admin", last_message_id=0)
        return True


@pytest.fixture
def doc_client():
    from companion.agent.memory.fake import InMemoryMemoryPort
    from companion.service.timeline.memory import InMemoryTimeline
    from memory_hub import AppConfig, MemoryHub

    store = ApiDocStore(ProfileDoc(owner_id=7, role_id="linche", markdown="## 基本情况\n做前端。",
                                   version=3, source="llm", last_message_id=10))
    hub = MemoryHub.from_config([AppConfig("companion")], lambda cfg: InMemoryMemoryPort())
    app = FastAPI()
    app.include_router(build_router(memory=hub.for_app("companion"), timeline=InMemoryTimeline(),
                                    current_user=build_current_user(AllowAllVerifier()), profile_doc=store))
    return TestClient(app), store


ME = {"Authorization": "Bearer 7"}


def test_profile_doc_endpoints(doc_client):
    client, store = doc_client
    got = client.get("/v1/memory/profile_doc?role_id=linche", headers=ME).json()
    assert (got["markdown"], got["version"], got["source"]) == ("## 基本情况\n做前端。", 3, "llm")
    empty = client.get("/v1/memory/profile_doc?role_id=other", headers=ME).json()
    assert empty["markdown"] == "" and empty["version"] is None
    resp = client.put("/v1/memory/profile_doc?role_id=linche", headers=ME,
                      json={"markdown": "## 基本情况\n我改的"})
    assert resp.status_code == 201
    assert store.saved == [(7, "linche", "## 基本情况\n我改的")]
    assert client.get("/v1/memory/profile_doc?role_id=linche", headers=ME).json()["source"] == "admin"
