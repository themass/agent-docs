"""Pasted-text建档: the third way into a profile.

Uploading a file and answering the interview were the only two routes, and both failed
a real case — a resume that lives in a chat message, or a user who would rather type a
paragraph than find a file. They had to save a `.txt` first.

What these tests pin down is that the new route is a *thin* one: it writes the text as
a source and lets the existing upload pipeline do everything else. The risk in a
feature like this is not that it fails, it is that it quietly becomes a second
implementation of ingest with its own parse status, its own failure copy, and its own
idea of whether the user still has to confirm. So most of the assertions here are about
what it reuses rather than what it adds.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agentkit.web.auth import UserActor

from jc.models.enums import ParseStatus
from jc.models.profile import Profile
from jc.services.profile_ingest_service import (
    _MIN_TEXT_CHARS,
    IngestValidationError,
    ProfileIngestService,
)
from jc.services.profile_service import ProfileService

RESUME_TEXT = (
    "张伟，后端工程师，8 年经验。\n"
    "2019.03-2024.08 字节跳动 推荐架构组 技术专家\n"
    "负责推荐系统召回链路重构，QPS 从 3 万提升到 12 万，P99 延迟下降 40%。\n"
    "带 6 人小组完成特征平台迁移，支撑日均 20 亿次请求。\n"
    "2016.07-2019.02 美团 基础架构 高级工程师\n"
    "自研配置中心，接入 300+ 服务。"
)


# --- the floor on what can become a profile -------------------------------------


def test_validate_text_accepts_a_real_resume() -> None:
    ProfileIngestService().validate_text(RESUME_TEXT)


def test_validate_text_rejects_empty() -> None:
    with pytest.raises(IngestValidationError) as err:
        ProfileIngestService().validate_text("   \n  ")
    assert "空" in str(err.value)


def test_validate_text_rejects_one_line() -> None:
    """A single line has nothing to extract.

    The structurer answers a near-empty prompt by producing a plausible profile, so
    refusing here is what stops a user from being handed a career they never had. The
    message therefore has to say what to write instead, not just that it is too short.
    """
    with pytest.raises(IngestValidationError) as err:
        ProfileIngestService().validate_text("我是一个后端工程师")
    message = str(err.value)
    assert "至少" in message
    assert "公司" in message


def test_validate_text_rejects_a_novel() -> None:
    with pytest.raises(IngestValidationError) as err:
        ProfileIngestService().validate_text("字" * 50_001)
    assert "万字" in str(err.value)


def test_user_facing_bounds_match_the_schema() -> None:
    """The schema and the service must not disagree about what is acceptable.

    Pydantic refuses a malformed call cheaply; the service explains why in Chinese. If
    the schema's ceiling were the lower of the two, the explanation would be
    unreachable and the user would get a generic validation error instead.
    """
    from jc.schemas.profile import ProfileTextIngestRequest
    from jc.services import profile_ingest_service as ingest

    schema_max = ProfileTextIngestRequest.model_fields["raw_text"].metadata
    ceilings = [getattr(m, "max_length", None) for m in schema_max]
    assert ingest._MAX_TEXT_CHARS in ceilings


# --- the route is thin: it hands off to the upload pipeline ----------------------


@pytest.fixture
def service() -> ProfileService:
    svc = object.__new__(ProfileService)
    svc._ingest = ProfileIngestService()
    svc._storage = SimpleNamespace(put_object=lambda *a, **k: None)
    svc._db = SimpleNamespace(commit=AsyncMock())
    return svc


@pytest.fixture
def captured(service: ProfileService, monkeypatch: pytest.MonkeyPatch) -> dict:
    profile = Profile(id="prof_1", user_id="usr_a", guest_session_id=None, version=1)
    state: dict = {"sources": [], "objects": {}}

    def put_object(key: str, body: bytes, *, content_type: str | None = None) -> str:
        state["objects"][key] = (body, content_type)
        return key

    async def add_source(source) -> None:  # noqa: ANN001
        state["sources"].append(source)

    async def get_by_id(profile_id: str, *, with_sources: bool = False):  # noqa: ANN001, ANN202
        profile.sources = state["sources"]
        return profile

    service._storage = SimpleNamespace(put_object=put_object)
    service._profiles = SimpleNamespace(add_source=add_source, get_by_id=get_by_id)
    monkeypatch.setattr(
        ProfileService,
        "_get_or_create_active_profile",
        AsyncMock(return_value=profile),
    )
    monkeypatch.setattr(
        ProfileService,
        "_to_response",
        lambda self, p: SimpleNamespace(id=p.id, sources=state["sources"], status=p.status),
    )
    state["profile"] = profile
    return state


async def test_pasted_text_becomes_a_pending_source(
    service: ProfileService, captured: dict
) -> None:
    await service.ingest_text(
        actor=UserActor(user_id="usr_a", session_id="sess_x"), raw_text=RESUME_TEXT
    )
    source = captured["sources"][0]
    # PROCESSING, not DONE: the structurer has not run yet. This is what makes the
    # existing parse-progress UI and its polling work unchanged.
    assert source.parse_status == ParseStatus.PROCESSING
    assert source.parse_phase == "queued"
    assert source.content_type == "text/plain"
    assert source.file_size == len(RESUME_TEXT.encode())


async def test_the_text_is_stored_as_an_object_not_in_the_row(
    service: ProfileService, captured: dict
) -> None:
    """Same rule as every other blob in JC: the bytes go to storage, the row gets a key."""
    await service.ingest_text(
        actor=UserActor(user_id="usr_a", session_id="sess_x"), raw_text=RESUME_TEXT
    )
    source = captured["sources"][0]
    assert source.storage_key == f"jc/dev/profiles/prof_1/source/{source.id}.txt"
    body, content_type = captured["objects"][source.storage_key]
    assert body.decode() == RESUME_TEXT
    assert content_type == "text/plain"


async def test_source_is_named_so_the_user_recognises_it(
    service: ProfileService, captured: dict
) -> None:
    await service.ingest_text(
        actor=UserActor(user_id="usr_a", session_id="sess_x"), raw_text=RESUME_TEXT
    )
    assert captured["sources"][0].file_name == "粘贴的内容.txt"


async def test_a_given_title_is_used_and_bounded(
    service: ProfileService, captured: dict
) -> None:
    await service.ingest_text(
        actor=UserActor(user_id="usr_a", session_id="sess_x"),
        raw_text=RESUME_TEXT,
        title="字" * 200,
    )
    name = captured["sources"][0].file_name
    assert name.endswith(".txt")
    assert len(name) <= 84


async def test_short_text_is_refused_before_anything_is_written(
    service: ProfileService, captured: dict
) -> None:
    with pytest.raises(IngestValidationError):
        await service.ingest_text(
            actor=UserActor(user_id="usr_a", session_id="sess_x"), raw_text="太短"
        )
    assert captured["sources"] == []
    assert captured["objects"] == {}


async def test_profile_stays_draft_so_confirmation_still_applies(
    service: ProfileService, captured: dict
) -> None:
    """Pasting is not a shortcut around review.

    The one thing this route must not do is produce a confirmed profile: the text went
    through a model, so the facts in it are the model's reading of what the user wrote
    and the user still has to agree with them.
    """
    await service.ingest_text(
        actor=UserActor(user_id="usr_a", session_id="sess_x"), raw_text=RESUME_TEXT
    )
    assert captured["profile"].status != "confirmed"


async def test_upload_blocking_call_is_off_the_event_loop(
    service: ProfileService, captured: dict
) -> None:
    import threading

    loop_thread = threading.current_thread().ident
    seen: list[int | None] = []
    original = service._storage.put_object

    def recording(key: str, body: bytes, *, content_type: str | None = None) -> str:
        seen.append(threading.current_thread().ident)
        return original(key, body, content_type=content_type)

    service._storage = SimpleNamespace(put_object=recording)
    await service.ingest_text(
        actor=UserActor(user_id="usr_a", session_id="sess_x"), raw_text=RESUME_TEXT
    )
    assert seen and all(tid != loop_thread for tid in seen)


# --- the entry point the backend route is useless without -------------------------


def test_the_paste_route_is_reachable_from_the_upload_screen() -> None:
    """A working endpoint with no entry point is a feature nobody has.

    `from-text` shipped a release before its UI, which is exactly the kind of gap that
    survives a green test suite. This asserts the uploader actually calls it, and that
    its floor matches the server's — a form that accepts 40 characters and then shows a
    rejection has just wasted the user's time.
    """
    from jc.paths import PROJECT_ROOT

    uploader = (
        PROJECT_ROOT / "frontend" / "web" / "components" / "profile" / "ProfileUploader.tsx"
    ).read_text(encoding="utf-8")
    api = (PROJECT_ROOT / "frontend" / "web" / "lib" / "api" / "profile.ts").read_text(
        encoding="utf-8"
    )

    assert "/profiles/from-text" in api, "no client function calls the paste endpoint"
    assert "ingestProfileText" in uploader, "the upload screen offers no way to paste"
    assert f"MIN_PASTE_CHARS = {_MIN_TEXT_CHARS}" in uploader, (
        "the form's floor must match the server's, or it submits text it knows will be refused"
    )


def test_building_from_nothing_offers_both_tools_separately() -> None:
    """Two genuinely different experiences must not hide behind one button.

    There was one button reading 「用对话建一份简历」 and it opened the structured question
    panel — a form. Both capabilities are real (agent interview and question plan), so
    the fix is two choices, not relabelling one.
    """
    from jc.paths import PROJECT_ROOT

    uploader = (
        PROJECT_ROOT / "frontend" / "web" / "components" / "profile" / "ProfileUploader.tsx"
    ).read_text(encoding="utf-8")

    assert "聊着写" in uploader, "no conversational route offered"
    assert "按问题填写" in uploader, "no structured route offered"
    assert '"chat"' in uploader and '"interview"' in uploader, (
        "the two routes must be distinguishable to the caller, not one flag"
    )
