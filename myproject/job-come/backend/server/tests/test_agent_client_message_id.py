"""R2 G1/G2 — `client_message_id` is stored, echoed, and idempotent.

Cursor R2 (2026-11-18) measured both failures on production and local:

* G1: the field was accepted on the request but `GET .../messages` never
  returned it — the optimistic UI could not merge its own bubble back after a
  reload, and nothing on the server could answer "which row is this?".
* G2: two sends with the same id wrote two user rows, both 200 ("静默双写").

The semantics the tests below pin are not the test plan's suggestion verbatim
— the plan allowed "return existing OR 409", and the codebase already had a
written contract that rules the plain version out: TECH-API documents that a
repeated id re-runs the model, 因为第一次可能没跑完. So the shape is::

    no row, no race            -> write one row, run the turn
    row, no committed answer   -> REUSE the row, re-run the turn  (retry button)
    row, committed answer      -> 409 duplicate_message           (pure replay)
    race past the lookup       -> loser gets IntegrityError -> 409
    id absent                  -> no dedup at all (same words, new id = new message)

Every pass above is tested next to its reject side, and the partial unique
index is tested where it lives — at the store, against the real constraint —
because a service-level check is exactly what the race defeats.
"""

from __future__ import annotations

import base64

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.agent.roles import default_role
from jc.db.base import Base
from jc.exceptions import ConflictError
from jc.models.agent import AgentSession
from jc.models.agent_trace import AgentTrace
from jc.models.user import User
from jc.schemas.agent import AgentAttachment
from jc.services import agent_attachment_service, agent_service
from jc.stores.agent_trace_store import AgentTraceStore

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(PNG).decode()


class FakeStore:
    """Object storage with a switchable failure, so both PUT outcomes are covered."""

    def __init__(self) -> None:
        self.puts: list[dict] = []
        self.bodies: dict[str, bytes] = {}
        self.fail_puts = False

    def put_object(self, key, body, *, content_type=None):
        if self.fail_puts:
            raise OSError("bucket down")
        self.puts.append({"key": key, "size": len(body), "content_type": content_type})
        self.bodies[key] = body
        return key

    def get_object_bytes(self, key):
        return self.bodies[key]

    def presigned_get_url(self, key, *, expires_in=900):
        return f"https://bucket.test/{key}?get=fake"


class ScriptedClient:
    """A DeerFlow stream that says exactly what a test needs it to say."""

    def __init__(self, events=(), *, raise_after: int | None = None) -> None:
        self.events = list(events)
        self.raise_after = raise_after

    async def stream_message(self, thread_id, message, metadata=None):
        for index, ev in enumerate(self.events):
            if self.raise_after is not None and index >= self.raise_after:
                raise RuntimeError("worker died")
            yield ev


def _ok_stream():
    return [
        {"type": "system_prompt_rendered", "content": "sys"},
        {"type": "token", "content": "在的"},
        {"type": "done"},
    ]


@pytest.fixture
async def env(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/cmid.sqlite")

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="test"))
        await db.flush()
        db.add(
            AgentSession(
                id="as1",
                user_id="u1",
                profile_id=None,
                role_id=default_role().id,
                deerflow_thread_id="thr_as1",
                trace_id="tr_as1",
            )
        )
        await db.commit()

    store = FakeStore()
    monkeypatch.setattr(agent_attachment_service, "get_storage_backend", lambda: store)
    monkeypatch.setattr(
        agent_attachment_service,
        "download_url_for_key",
        lambda key: f"https://bucket.test/{key}?get=fake",
    )
    yield sessions, store
    await engine.dispose()


ACTOR = UserActor(user_id="u1", session_id="s")


def _png_attachment() -> AgentAttachment:
    return AgentAttachment(
        kind="image", name="photo.png", mime_type="image/png", data_url=PNG_DATA_URL
    )


async def _rows(maker) -> list[AgentTrace]:
    async with maker() as db:
        return list(
            (
                await db.execute(
                    select(AgentTrace).where(AgentTrace.session_id == "as1").order_by(
                        AgentTrace.seq
                    )
                )
            ).scalars()
        )


async def _user_rows(maker) -> list[AgentTrace]:
    return [r for r in await _rows(maker) if r.event_type == "user_message"]


async def _send(
    maker,
    monkeypatch,
    *,
    client_message_id=None,
    content="你好",
    attachment=None,
    events=None,
    raise_after=None,
    client=None,
):
    """Run one whole turn to exhaustion, swallowing the scripted failure."""
    monkeypatch.setattr(
        agent_service,
        "get_deerflow_client",
        lambda db=None: client
        or ScriptedClient(events if events is not None else _ok_stream(), raise_after=raise_after),
    )
    async with maker() as db:
        stream = agent_service.AgentService(db).stream_message(
            "as1",
            actor=ACTOR,
            content=content,
            attachments=[attachment] if attachment else None,
            client_message_id=client_message_id,
        )
        async for _ in stream:
            pass


# -- G1: the stored id comes back on history ---------------------------------


@pytest.mark.asyncio
async def test_history_echoes_the_id_and_stays_null_without_one(env, monkeypatch):
    """G1, both sides in one look: an id sent comes back; a send without an id
    fabricates none on the way back — and assistant rows never carry one."""
    maker, _ = env
    await _send(maker, monkeypatch, content="记住这条", client_message_id="cm_alpha")
    await _send(maker, monkeypatch, content="没带 id")
    async with maker() as db:
        listed = await agent_service.AgentService(db).list_messages("as1", actor=ACTOR)
    by_content = {m.content: m for m in listed.messages if m.role == "user"}
    assert by_content["记住这条"].client_message_id == "cm_alpha"
    assert by_content["没带 id"].client_message_id is None
    # The id identifies the USER's message; assistant rows never carry one.
    assistants = [m for m in listed.messages if m.role == "assistant"]
    assert assistants and all(m.client_message_id is None for m in assistants)


# -- G2: idempotency on (session_id, client_message_id) -----------------------


@pytest.mark.asyncio
async def test_resend_after_a_completed_turn_is_refused_not_double_written(
    env, monkeypatch
):
    """The completed replay: 409, and still exactly one user row."""
    maker, _ = env
    await _send(maker, monkeypatch, content="同一句", client_message_id="cm_beta")
    with pytest.raises(ConflictError) as exc:
        await _send(maker, monkeypatch, content="同一句", client_message_id="cm_beta")
    assert exc.value.code == "duplicate_message"
    rows = await _user_rows(maker)
    assert len(rows) == 1, [r.id for r in rows]


@pytest.mark.asyncio
async def test_resend_of_a_half_dead_turn_reuses_the_row_and_reruns(env, monkeypatch):
    """The retry button, pinned as a contract (TECH-API: 模型仍会再跑一轮).

    The first attempt died before any answer was committed — that is not a
    completed turn, and refusing it with 409 would strand the user with a
    bubble that can never answer. The row is REUSED (same id, so the UI bubble
    stays glued to it) and the turn runs again on the second attempt.
    """
    maker, _ = env
    await _send(
        maker,
        monkeypatch,
        content="卡住了",
        client_message_id="cm_gamma",
        events=[{"type": "system_prompt_rendered", "content": "sys"}],
        raise_after=1,  # dies mid-stream: token never arrives, nothing commits
    )
    (first,) = await _user_rows(maker)
    assert not any(r.event_type == "assistant_message" for r in await _rows(maker))

    await _send(maker, monkeypatch, content="卡住了", client_message_id="cm_gamma")

    rows = await _user_rows(maker)
    assert len(rows) == 1, [r.id for r in rows]
    assert rows[0].id == first.id  # reused, not re-created
    assert any(r.event_type == "assistant_message" for r in await _rows(maker))


@pytest.mark.asyncio
async def test_a_different_id_is_a_different_message(env, monkeypatch):
    """REJECT side: idempotency is per-id, never per-text. Two ids, two rows."""
    maker, _ = env
    await _send(maker, monkeypatch, content="同一句", client_message_id="cm_one")
    await _send(maker, monkeypatch, content="同一句", client_message_id="cm_two")
    assert len(await _user_rows(maker)) == 2


@pytest.mark.asyncio
async def test_no_id_never_dedups(env, monkeypatch):
    """REJECT side of the whole feature: sends without an id are never merged.
    Doubles as the partial-index test: both rows commit under the real index,
    proving its WHERE clause lets NULL-id rows coexist."""
    maker, _ = env
    await _send(maker, monkeypatch, content="连发两次")
    await _send(maker, monkeypatch, content="连发两次")
    assert len(await _user_rows(maker)) == 2


@pytest.mark.asyncio
async def test_the_race_loser_is_refused_by_the_index(env, monkeypatch):
    """The interleaving no service check can see: two attempts pass the lookup.

    Simulated by hiding the existing row from the lookup for the second
    attempt. The partial unique index is what turns the race into one row and
    one 409 — if this test ever shows two rows, the index (not the check) is
    what broke.
    """
    maker, _ = env
    await _send(maker, monkeypatch, content="并发重发", client_message_id="cm_race")
    real_find = AgentTraceStore.find_user_message

    async def blind_find(self, session_id, client_message_id):
        return None  # the other attempt "won" first, this one sees nothing

    monkeypatch.setattr(AgentTraceStore, "find_user_message", blind_find)
    with pytest.raises(ConflictError) as exc:
        await _send(maker, monkeypatch, content="并发重发", client_message_id="cm_race")
    assert exc.value.code == "duplicate_message"
    monkeypatch.setattr(AgentTraceStore, "find_user_message", real_find)
    assert len(await _user_rows(maker)) == 1


# -- the reuse path keeps the archive honest ----------------------------------


@pytest.mark.asyncio
async def test_reuse_does_not_reupload_a_settled_attachment(env, monkeypatch):
    """Half-dead photo turn: the bytes landed, the answer never did.

    The retry must NOT mint a second key for the same bytes — that would
    double-store the photo and orphan the first object under a prefix the GC
    cannot enumerate (B-1 §2.2). The settled row is kept as-is.

    "Half dead" is scripted as a stream that dies after the upload settled:
    `assistant_message` is committed only with the turn's end, so the ledger
    has the user row and no answer — the retry button's exact state.
    """
    maker, store = env
    await _send(
        maker,
        monkeypatch,
        content="看图",
        client_message_id="cm_pic",
        attachment=_png_attachment(),
        events=[{"type": "system_prompt_rendered", "content": "sys"}],
        raise_after=1,
    )
    (first,) = await _user_rows(maker)
    first_key = first.payload["attachments"][0]["storage_key"]
    assert first_key and len(store.puts) == 1

    await _send(
        maker, monkeypatch, content="看图", client_message_id="cm_pic", attachment=_png_attachment()
    )
    (only,) = await _user_rows(maker)
    assert only.id == first.id
    assert only.payload["attachments"][0]["storage_key"] == first_key
    # Still ONE object in the bucket for this message.
    assert len(store.puts) == 1


@pytest.mark.asyncio
async def test_reuse_repairs_an_unsettled_attachment(env, monkeypatch):
    """REJECT side of the branch above: first upload FAILED, so the retry's
    bytes must go up under a fresh plan and settle the row."""
    maker, store = env
    store.fail_puts = True
    await _send(
        maker,
        monkeypatch,
        content="看图",
        client_message_id="cm_bad",
        attachment=_png_attachment(),
        events=[{"type": "system_prompt_rendered", "content": "sys"}],
        raise_after=1,
    )
    (first,) = await _user_rows(maker)
    (row,) = first.payload["attachments"]
    assert row["storage_error"] is True

    store.fail_puts = False
    await _send(
        maker, monkeypatch, content="看图", client_message_id="cm_bad", attachment=_png_attachment()
    )
    (only,) = await _user_rows(maker)
    assert only.id == first.id
    (row,) = only.payload["attachments"]
    assert "storage_error" not in row and "storage_pending" not in row
    assert row["storage_key"] and store.bodies[row["storage_key"]] == PNG
