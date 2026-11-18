"""B-1: a user's message must survive the worker dying mid-turn.

Production 2026-11-18: a message that included a photo vanished from history when
the worker running it was killed (likely OOM), and the photo object stayed in the
bucket forever as an orphan the GC cannot even enumerate.

Two things were wrong, and both are pinned here from both sides:

* the `user_message` row was held in memory until the model stream produced
  `system_prompt_rendered` — i.e. across attachment uploads, a vision call and
  graph construction, all slow. The row is now written and committed first, with
  `system_prompt` inserted LATER at an explicit `seq=0`.
* attachments were uploaded before their row existed, so a crash in between left
  an object nobody references. The row (with its deterministic key) now goes
  first and the upload step clears `storage_pending` afterwards.

A process death cannot be staged inside pytest, so the equivalent is a
deterministic failure raised at the same point plus a FRESH service/session
reading history back — which is exactly what the user's browser does next.
"""

from __future__ import annotations

import base64

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.agent.roles import default_role
from jc.db.base import Base
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
        if self.raise_after is not None and self.raise_after >= len(self.events):
            raise RuntimeError("worker died")


@pytest.fixture
async def env(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/b1.sqlite")

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="test"))
        db.add(User(id="u2", email="u2@example.test", password_hash="test"))
        await db.flush()
        for sid, uid in (("as1", "u1"), ("as2", "u2")):
            db.add(
                AgentSession(
                    id=sid,
                    user_id=uid,
                    profile_id=None,  # no profile keeps the turn provider a no-op
                    role_id=default_role().id,
                    deerflow_thread_id=f"thr_{sid}",
                    trace_id=f"tr_{sid}",
                )
            )
        await db.commit()

    store = FakeStore()
    monkeypatch.setattr(agent_attachment_service, "get_storage_backend", lambda: store)
    # `download_url_for_key` lives in `storage_client`; pin it so a test never
    # depends on which storage settings the machine happens to have.
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


async def _rows(maker, session_id="as1") -> list[AgentTrace]:
    async with maker() as db:
        return list(
            (
                await db.execute(
                    select(AgentTrace)
                    .where(AgentTrace.session_id == session_id)
                    .order_by(AgentTrace.seq)
                )
            ).scalars()
        )


async def _run(
    maker, *, events, attachment=None, monkeypatch, raise_after=None, content="看图", client=None
):
    monkeypatch.setattr(
        agent_service,
        "get_deerflow_client",
        lambda db=None: client or ScriptedClient(events, raise_after=raise_after),
    )
    async with maker() as db:
        stream = agent_service.AgentService(db).stream_message(
            "as1",
            actor=ACTOR,
            content=content,
            attachments=[attachment] if attachment else None,
        )
        async for _ in stream:
            pass


# --- row 1: the message exists even if the turn dies early ----------------


@pytest.mark.asyncio
async def test_user_message_is_durable_before_the_expensive_half(env, monkeypatch):
    """PASS: a normal turn stores system(0) < user(1) < assistant."""
    maker, _ = env
    await _run(
        maker,
        events=[
            {"type": "system_prompt_rendered", "content": "sys"},
            {"type": "token", "content": "在的"},
            {"type": "done"},
        ],
        monkeypatch=monkeypatch,
    )
    rows = await _rows(maker)
    assert [(r.seq, r.event_type) for r in rows][:2] == [
        (0, "system_prompt"),
        (1, "user_message"),
    ]
    assert rows[1].content == "看图"


@pytest.mark.asyncio
async def test_the_message_survives_a_death_in_the_vision_phase(env, monkeypatch):
    """REJECT side of row 1: the failure that actually lost the message.

    The photo turn used to sit in `flatten` (a vision call) with nothing written
    yet. Now the row is already committed, so a fresh service — the browser
    reloading history — still finds the message and its attachment key.
    """

    async def boom(*_args, **_kwargs):
        raise RuntimeError("worker died in vision")

    monkeypatch.setattr(agent_service, "flatten_message_for_text_agent", boom)
    maker, store = env
    with pytest.raises(RuntimeError, match="vision"):
        await _run(maker, events=[], attachment=_png_attachment(), monkeypatch=monkeypatch)

    rows = await _rows(maker)
    assert [r.event_type for r in rows] == ["user_message"], [r.event_type for r in rows]
    assert rows[0].content.strip() == "看图"
    (stored,) = rows[0].payload["attachments"]
    assert stored["storage_key"] and store.bodies[stored["storage_key"]] == PNG
    assert "storage_pending" not in stored

    # And a fresh reader (a new session, as the browser uses) sees it as history.
    async with maker() as db:
        listed = await agent_service.AgentService(db).list_messages("as1", actor=ACTOR)
    assert [m.event_type for m in listed.messages] == ["message"]


# --- row 2: prompt still lands at seq 0, exactly once --------------------


@pytest.mark.asyncio
async def test_a_turn_that_died_before_the_prompt_still_replays_in_order(env, monkeypatch):
    """REJECT side of row 2: first turn dies pre-prompt; the second one repairs ordering."""
    maker, _ = env
    # Turn 1: the client dies before emitting `system_prompt_rendered`.
    with pytest.raises(RuntimeError, match="worker died"):
        await _run(maker, events=[], attachment=None, monkeypatch=monkeypatch, raise_after=0)

    after_first = await _rows(maker)
    assert [r.event_type for r in after_first] == ["user_message"]
    assert all(r.event_type != "system_prompt" for r in after_first)

    # Turn 2: a healthy turn inserts the prompt at 0 — in front of BOTH user rows.
    await _run(
        maker,
        events=[
            {"type": "system_prompt_rendered", "content": "sys"},
            {"type": "token", "content": "好"},
            {"type": "done"},
        ],
        monkeypatch=monkeypatch,
        content="第二轮",
    )
    rows = await _rows(maker)
    assert [r.seq for r in rows] == list(range(len(rows))), [(r.seq, r.event_type) for r in rows]
    assert rows[0].event_type == "system_prompt"
    assert [r.event_type for r in rows].count("system_prompt") == 1
    assert [r.content for r in rows if r.event_type == "user_message"] == ["看图", "第二轮"]

    async with maker() as db:
        assert await AgentTraceStore(db).has_system_prompt("as1") is True


# --- row 3: key first, object second ------------------------------------


@pytest.mark.asyncio
async def test_a_failed_upload_leaves_a_row_that_says_so(env, monkeypatch):
    """REJECT side of row 3: bucket down → the message survives, marked as unsaved."""
    maker, store = env
    store.fail_puts = True
    await _run(
        maker,
        events=[
            {"type": "system_prompt_rendered", "content": "sys"},
            {"type": "token", "content": "收到"},
            {"type": "done"},
        ],
        attachment=_png_attachment(),
        monkeypatch=monkeypatch,
    )
    rows = await _rows(maker)
    (user_row,) = [r for r in rows if r.event_type == "user_message"]
    (stored,) = user_row.payload["attachments"]
    assert stored["storage_error"] is True
    assert stored["storage_key"] is None
    assert stored["download_url"] is None
    assert "storage_pending" not in stored
    assert store.puts == []  # nothing was written under any key

    async with maker() as db:
        listed = await agent_service.AgentService(db).list_messages("as1", actor=ACTOR)
    # History is the whole transcript, assistant rows included — the photo lives
    # on the user row.
    (message,) = [m for m in listed.messages if m.role == "user"]
    assert message.payload["attachments"][0]["storage_error"] is True


@pytest.mark.asyncio
async def test_a_death_between_row_and_put_reads_as_unsaved_not_dead_media(env, monkeypatch):
    """REJECT side of row 3, the B-1 case itself: no upload step ran at all.

    Simulated by exploding the upload step (what a SIGKILL does, except the
    exception is observable). The committed row still says `storage_pending`, and
    the wire projection must turn that into the existing "not saved" rendering
    rather than signing a URL to an object that was never written.
    """

    async def killed(*_args, **_kwargs):
        raise RuntimeError("worker died before the PUT")

    monkeypatch.setattr(agent_service, "upload_pending_attachments", killed)
    maker, store = env
    with pytest.raises(RuntimeError, match="before the PUT"):
        await _run(maker, events=[], attachment=_png_attachment(), monkeypatch=monkeypatch)

    rows = await _rows(maker)
    (user_row,) = rows
    (stored,) = user_row.payload["attachments"]
    assert stored["storage_pending"] is True
    assert store.bodies == {}

    async with maker() as db:
        listed = await agent_service.AgentService(db).list_messages("as1", actor=ACTOR)
    (message,) = [m for m in listed.messages if m.role == "user"]
    wire = message.payload["attachments"][0]
    # The raw marker does not leak to the client; what it MEANS does.
    assert "storage_pending" not in wire
    assert wire["storage_error"] is True
    assert wire["download_url"] is None


@pytest.mark.asyncio
async def test_the_key_is_minted_from_the_message_id_before_any_upload(env):
    """Unit-level counterpart: planning is pure, and the key is deterministic."""
    maker, store = env
    att = _png_attachment()
    rows = agent_attachment_service.plan_attachment_rows(
        [att], session_id="agsn_x", message_id="agm_y"
    )
    (row,) = rows
    assert row["storage_key"].endswith("/agsn_x/attachments/agm_y-0.png")
    assert row["storage_pending"] is True
    assert row["size_bytes"] == len(PNG)
    assert store.puts == []  # planning never touches the network

    # Same inputs, same key — that is what lets a retry overwrite rather than
    # accumulate orphans.
    again = agent_attachment_service.plan_attachment_rows(
        [att], session_id="agsn_x", message_id="agm_y"
    )
    assert again[0]["storage_key"] == row["storage_key"]


# --- row 4: payload.text is backfilled; interview turns keep today's shape --


@pytest.mark.asyncio
async def test_payload_text_is_backfilled_from_the_wrapped_message(env, monkeypatch):
    maker, _ = env
    await _run(
        maker,
        events=[
            {"type": "system_prompt_rendered", "content": "sys"},
            {"type": "token", "content": "好"},
            {"type": "done"},
        ],
        monkeypatch=monkeypatch,
        content="原始输入",
    )
    rows = await _rows(maker)
    (user_row,) = [r for r in rows if r.event_type == "user_message"]
    assert user_row.content == "原始输入"
    assert user_row.payload["text"], user_row.payload


@pytest.mark.asyncio
async def test_a_turn_with_no_prompt_event_still_keeps_its_text(env, monkeypatch):
    """REJECT side of row 4: the prompt never arrives (errored run) — text is not lost."""
    maker, _ = env
    client = ScriptedClient([{"type": "token", "content": "partial"}, {"type": "done"}])
    await _run(maker, events=[], attachment=None, monkeypatch=monkeypatch, client=client)

    rows = await _rows(maker)
    assert all(r.event_type != "system_prompt" for r in rows)
    (user_row,) = [r for r in rows if r.event_type == "user_message"]
    assert user_row.payload["text"]


# --- row 5: isolation did not regress -----------------------------------


@pytest.mark.asyncio
async def test_another_account_cannot_read_the_message_or_its_photo(env, monkeypatch):
    maker, _ = env
    await _run(
        maker,
        events=[
            {"type": "system_prompt_rendered", "content": "sys"},
            {"type": "token", "content": "好"},
            {"type": "done"},
        ],
        attachment=_png_attachment(),
        monkeypatch=monkeypatch,
    )
    from jc.exceptions import NotFoundError

    async with maker() as db:
        other = agent_service.AgentService(db)
        with pytest.raises(NotFoundError):
            await other.list_messages("as1", actor=UserActor(user_id="u2", session_id="s2"))
        with pytest.raises(NotFoundError):
            async for _ in other.stream_message(
                "as1", actor=UserActor(user_id="u2", session_id="s2"), content="越权"
            ):
                pass
