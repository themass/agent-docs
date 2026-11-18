"""ADR-011 direct upload: sign / bind / GC, real SQL, faked Redis + bucket.

Two-sided on purpose: every rejection path (foreign key, expired, double bind,
missing object, oversize, rate limit, wrong scene) is asserted next to the
well-formed path, because the bind checks are the entire trust boundary — a
test that only proves the happy path proves the boundary can be crossed.

The bucket is a FakeObjectStore: these tests validate OUR decisions (issuance
record, ownership, sizes, lifecycle), not boto3's signature correctness. The
Redis throttle is a counter fake for the same reason.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from agentkit.web.auth import GuestActor, UserActor
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.api.auth_router import register_exception_handlers
from jc.api.deps import get_actor, get_db
from jc.api.media_router import register_media_exception_handlers
from jc.api.media_router import router as media_router
from jc.api.profile_router import register_profile_exception_handlers
from jc.config import settings
from jc.db.base import Base
from jc.exceptions import (
    ConflictError,
    ForbiddenError,
    GoneError,
    NotFoundError,
)
from jc.models.enums import MediaUploadState
from jc.models.media_upload import MediaUpload
from jc.schemas.agent import AgentAttachment
from jc.services import agent_attachment_service, media_service
from jc.services.agent_attachment_service import (
    AttachmentRejectedError,
    AttachmentTooLargeError,
    offload_for_persistence,
    prepare_direct_attachments,
)
from jc.services.media_scene import MediaSceneError
from jc.services.media_service import MediaService, new_key_id, sweep_media_uploads

OWNER = UserActor(user_id="usr_owner", session_id="s")
OTHER = UserActor(user_id="usr_other", session_id="s")


class FakeObjectStore:
    def __init__(self) -> None:
        self.sizes: dict[str, int] = {}
        self.deleted: list[str] = []
        self.signed: list[dict] = []
        self.objects: list[tuple[str, object]] = []
        self.bodies: dict[str, bytes] = {}
        self.puts: list[dict] = []

    def get_object_bytes(self, key):
        return self.bodies[key]

    def put_object(self, key, body, *, content_type=None):
        self.puts.append({"key": key, "size": len(body), "content_type": content_type})
        self.bodies[key] = body
        self.sizes[key] = len(body)
        return key

    def presigned_put_url(self, key, *, content_type=None, expires_in=600):
        self.signed.append({"key": key, "content_type": content_type, "expires_in": expires_in})
        return f"https://bucket.test/{key}?sig=fake"

    def head_object_size(self, key):
        return self.sizes.get(key)

    def presigned_get_url(self, key, *, expires_in=900):
        return f"https://bucket.test/{key}?get=fake"

    def delete_object(self, key):
        self.deleted.append(key)

    def list_object_keys(self, prefix, *, max_keys=1000, page_size=1000):
        return [entry for entry in self.objects if entry[0].startswith(prefix)][:max_keys]


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key, seconds):
        return True


@pytest.fixture
async def env(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/media.sqlite")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    # Remote storage "on" without real credentials: sign is allowed to run.
    monkeypatch.setattr(settings, "jc_s3_access_key", "test-ak")
    monkeypatch.setattr(settings, "jc_s3_secret_key", "test-sk")

    store = FakeObjectStore()
    redis = FakeRedis()
    # One patch covers both consumers: MediaService._object_store and the GC
    # each resolve jc.storage_client.get_object_store at call time.
    monkeypatch.setattr("jc.storage_client.get_object_store", lambda: store)
    monkeypatch.setattr(media_service, "get_redis", lambda: redis)
    # GC opens its own sessions through the module attribute; point it here.
    monkeypatch.setattr("jc.db.session.AsyncSessionLocal", sessions)

    actor = {"current": OWNER}
    app = FastAPI()
    register_exception_handlers(app)
    register_profile_exception_handlers(app)
    register_media_exception_handlers(app)
    app.include_router(media_router, prefix="/api/v1")
    app.dependency_overrides[get_actor] = lambda: actor["current"]

    async def _db():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = _db

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://fixture"
    ) as client:
        yield SimpleNamespace(
            sessions=sessions, client=client, store=store, redis=redis, actor=actor, engine=engine
        )
    await engine.dispose()


async def sign(client, *, scene="chat-image", content_type="image/jpeg", size=50_000):
    return await client.post(
        "/api/v1/media/sign",
        json={"scene": scene, "contentType": content_type, "sizeBytes": size},
    )


async def issued_row(sessions, key):
    async with sessions() as db:
        return await db.get(MediaUpload, key)


# ------------------------------- sign -------------------------------


async def test_sign_happy_path_records_issuance_and_always_signs_content_type(env):
    response = await sign(env.client)
    assert response.status_code == 200, response.text
    body = response.json()

    key = body["objectKey"]
    assert key.startswith("jc/dev/uploads/usr_owner/chat-image/")
    assert key.endswith(".jpg")
    assert "/" not in key.split("chat-image/", 1)[1].rsplit("/", 1)[-1]  # single file segment

    # The Content-Type signature hole flagged in review: our call site must
    # always pass it, so the PUT cannot arrive with a spoofed type.
    (signed,) = env.store.signed
    assert signed["content_type"] == "image/jpeg"
    assert signed["expires_in"] == settings.jc_media_sign_ttl_sec

    assert body["upload"]["method"] == "PUT"
    assert body["upload"]["url"].startswith("https://bucket.test/")
    assert body["upload"]["headers"] == {"Content-Type": "image/jpeg"}
    assert body["limits"]["maxBytes"] == 8 * 1024 * 1024

    row = await issued_row(env.sessions, key)
    assert row is not None
    assert row.state == MediaUploadState.ISSUED
    assert row.actor_id == "usr_owner" and row.actor_kind == "user"
    assert row.scene == "chat-image" and row.content_type == "image/jpeg"
    assert row.declared_size == 50_000 and row.actual_size is None
    assert row.expires_at > datetime.now(UTC)


async def test_sign_accepts_guest_actor(env):
    env.actor["current"] = GuestActor(guest_session_id="gst_abc")
    response = await sign(env.client)
    assert response.status_code == 200
    assert "gst_abc" in response.json()["objectKey"]


async def test_sign_rejects_unknown_scene(env):
    response = await sign(env.client, scene="smuggle-exe")
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_scene"


async def test_sign_rejects_content_type_outside_scene(env):
    response = await sign(env.client, scene="chat-image", content_type="audio/mpeg")
    assert response.status_code == 400
    assert response.json()["code"] == "unsupported_content_type"

    # SVG must not ride in on an image/ prefix — explicit whitelist, not prefix.
    response = await sign(env.client, scene="chat-image", content_type="image/svg+xml")
    assert response.status_code == 400


async def test_sign_rejects_declared_size_over_scene_cap(env):
    response = await sign(env.client, size=9 * 1024 * 1024)
    assert response.status_code == 400
    assert response.json()["code"] == "size_over_limit"


async def test_sign_returns_503_when_direct_upload_disabled(env):
    monkey_off = settings.model_copy()
    monkey_off.jc_s3_secret_key = ""
    from jc.services import media_service as ms

    original = ms.settings
    ms.settings = monkey_off
    try:
        response = await sign(env.client)
    finally:
        ms.settings = original
    assert response.status_code == 503
    assert response.json()["code"] == "direct_upload_disabled"


async def test_sign_rate_limits_per_actor(env, monkeypatch):
    monkeypatch.setattr(settings, "jc_media_sign_rate_limit_per_min", 2)
    assert (await sign(env.client)).status_code == 200
    assert (await sign(env.client)).status_code == 200
    third = await sign(env.client)
    assert third.status_code == 429
    assert third.json()["code"] == "rate_limited"
    # Another actor is unaffected: the window is per actor, not global.
    env.actor["current"] = OTHER
    assert (await sign(env.client)).status_code == 200


async def test_each_sign_gets_a_fresh_key(env):
    keys = {(await sign(env.client)).json()["objectKey"] for _ in range(3)}
    assert len(keys) == 3
    # keyId entropy: 22 urlsafe chars, no collision-prone truncation.
    key_ids = [k.rsplit("/", 1)[1].split(".")[0] for k in keys]
    assert all(len(kid) == 22 for kid in key_ids)


# ------------------------------- bind -------------------------------


async def make_issued(
    env,
    *,
    scene="chat-image",
    actor=OWNER,
    content_type="image/jpeg",
    expires_offset_sec=600,
    object_key=None,
    state=MediaUploadState.ISSUED,
):
    key = object_key or f"jc/dev/uploads/{actor.actor_id}/{scene}/2026/11/17/{new_key_id()}.jpg"
    async with env.sessions() as db:
        db.add(
            MediaUpload(
                object_key=key,
                actor_id=actor.actor_id,
                actor_kind=actor.kind,
                scene=scene,
                content_type=content_type,
                declared_size=1000,
                state=state,
                expires_at=datetime.now(UTC) + timedelta(seconds=expires_offset_sec),
            )
        )
        await db.commit()
    return key


async def test_bind_happy_path_consumes_the_key(env):
    key = await make_issued(env)
    env.store.sizes[key] = 123_456
    async with env.sessions() as db:
        bound = await MediaService(db).bind(
            actor=OWNER,
            object_key=key,
            scene="chat-image",
            bound_ref="msg_1",
        )
        await db.commit()
    assert bound.size_bytes == 123_456
    # The mime the ledger will trust is the sign-time one, not any later claim.
    assert bound.content_type == "image/jpeg"
    row = await issued_row(env.sessions, key)
    assert row.state == MediaUploadState.BOUND
    assert row.actual_size == 123_456
    assert row.bound_ref == "msg_1" and row.bound_at is not None


async def test_bind_rejects_foreign_key_with_403(env):
    key = await make_issued(env, actor=OWNER)
    env.store.sizes[key] = 100
    async with env.sessions() as db:
        with pytest.raises(ForbiddenError) as exc:
            await MediaService(db).bind(
                actor=OTHER,
                object_key=key,
                scene="chat-image",
                bound_ref="msg_x",
            )
    assert exc.value.code == "foreign_upload"
    row = await issued_row(env.sessions, key)
    assert row.state == MediaUploadState.ISSUED  # rejection changes nothing


async def test_bind_rejects_unknown_key(env):
    async with env.sessions() as db:
        with pytest.raises(NotFoundError):
            await MediaService(db).bind(
                actor=OWNER,
                object_key="jc/dev/uploads/usr_owner/chat-image/2026/11/17/nope.jpg",
                scene="chat-image",
                bound_ref="msg_x",
            )


async def test_bind_rejects_scene_mismatch(env):
    # A key issued for chat-audio cannot be laundered into profile-source.
    key = await make_issued(env, scene="chat-audio", content_type="audio/webm")
    env.store.sizes[key] = 100
    async with env.sessions() as db:
        with pytest.raises(ForbiddenError) as exc:
            await MediaService(db).bind(
                actor=OWNER,
                object_key=key,
                scene="profile-source",
                bound_ref="src_1",
            )
    assert exc.value.code == "scene_mismatch"


async def test_bind_rejects_expired_and_marks_the_row(env):
    key = await make_issued(env, expires_offset_sec=-1)
    async with env.sessions() as db:
        with pytest.raises(GoneError):
            await MediaService(db).bind(
                actor=OWNER,
                object_key=key,
                scene="chat-image",
                bound_ref="msg_x",
            )
    row = await issued_row(env.sessions, key)
    assert row.state == MediaUploadState.EXPIRED


async def test_bind_rejects_double_bind(env):
    key = await make_issued(env)
    env.store.sizes[key] = 100
    async with env.sessions() as db:
        await MediaService(db).bind(
            actor=OWNER,
            object_key=key,
            scene="chat-image",
            bound_ref="msg_1",
        )
        await db.commit()
    async with env.sessions() as db:
        with pytest.raises(ConflictError) as exc:
            await MediaService(db).bind(
                actor=OWNER,
                object_key=key,
                scene="chat-image",
                bound_ref="msg_2",
            )
    assert exc.value.code == "already_bound"
    # The first binding is untouched by the second attempt.
    row = await issued_row(env.sessions, key)
    assert row.bound_ref == "msg_1"


async def test_bind_rejects_when_object_was_never_put(env):
    key = await make_issued(env)  # store.sizes has no entry: HEAD says missing
    async with env.sessions() as db:
        with pytest.raises(NotFoundError) as exc:
            await MediaService(db).bind(
                actor=OWNER,
                object_key=key,
                scene="chat-image",
                bound_ref="msg_x",
            )
    assert exc.value.code == "upload_not_found"


async def test_bind_rejects_oversize_object_left_issued_for_gc(env):
    key = await make_issued(env)
    env.store.sizes[key] = 9 * 1024 * 1024  # declared small, PUT a monster
    async with env.sessions() as db:
        with pytest.raises(MediaSceneError) as exc:
            await MediaService(db).bind(
                actor=OWNER,
                object_key=key,
                scene="chat-image",
                bound_ref="msg_x",
            )
    assert exc.value.code == "uploaded_size_over_limit"
    row = await issued_row(env.sessions, key)
    assert row.state == MediaUploadState.ISSUED  # GC reaps the object later
    async with env.sessions() as db:
        assert (await db.get(MediaUpload, key)).actual_size is None


# -------------------------------- GC --------------------------------


async def insert(sessions, **kw) -> str:
    kw.setdefault("actor_id", "usr_owner")
    kw.setdefault("actor_kind", "user")
    kw.setdefault("scene", "chat-image")
    kw.setdefault("content_type", "image/jpeg")
    kw.setdefault("declared_size", 10)
    kw.setdefault("state", MediaUploadState.ISSUED)
    key = kw.pop("object_key", f"jc/dev/uploads/usr_owner/chat-image/2026/11/10/{new_key_id()}.jpg")
    async with sessions() as db:
        db.add(MediaUpload(object_key=key, **kw))
        await db.commit()
    return key


async def test_gc_deletes_expired_rows_and_their_objects_keeps_the_rest(env):
    now = datetime.now(UTC)
    old_expired = await insert(
        env.sessions, state=MediaUploadState.EXPIRED, expires_at=now - timedelta(days=2)
    )
    # 36h ago: past both the 10-min TTL and the 24h grace, so GC reaps it.
    # (1 day ago would sit inside the grace window — not reaping it is correct.)
    old_issued = await insert(
        env.sessions, state=MediaUploadState.ISSUED, expires_at=now - timedelta(hours=36)
    )
    fresh = await insert(env.sessions, expires_at=now + timedelta(minutes=10))
    bound = await insert(
        env.sessions,
        state=MediaUploadState.BOUND,
        expires_at=now - timedelta(days=3),
        actual_size=10,
        bound_ref="msg_keep",
        bound_at=now,
    )
    env.store.sizes.update({k: 5 for k in (old_expired, old_issued, fresh, bound)})

    removed = await sweep_media_uploads()

    assert removed["expired"] == 2
    assert sorted(env.store.deleted) == sorted([old_expired, old_issued])
    assert await issued_row(env.sessions, old_expired) is None
    assert await issued_row(env.sessions, old_issued) is None
    assert (await issued_row(env.sessions, fresh)).state == MediaUploadState.ISSUED
    assert (await issued_row(env.sessions, bound)).state == MediaUploadState.BOUND


async def test_gc_deletes_orphan_objects_the_table_never_heard_of(env):
    now = datetime.now(UTC)
    known = await insert(env.sessions, expires_at=now + timedelta(minutes=10))
    orphan_old = "jc/dev/uploads/usr_victim/chat-image/2026/11/01/orphan111111111111.jpg"
    orphan_fresh = "jc/dev/uploads/usr_victim/chat-image/2026/11/17/orphan2222222222.jpg"
    env.store.objects = [
        (known, now - timedelta(days=10)),
        (orphan_old, now - timedelta(days=10)),
        (orphan_fresh, now - timedelta(minutes=5)),
    ]

    removed = await sweep_media_uploads()

    assert removed["orphans"] == 1
    assert orphan_old in env.store.deleted
    assert known not in env.store.deleted and orphan_fresh not in env.store.deleted
    assert await issued_row(env.sessions, known) is not None  # the row itself stays


async def test_gc_dry_run_touches_nothing(env):
    now = datetime.now(UTC)
    old = await insert(
        env.sessions,
        state=MediaUploadState.EXPIRED,
        expires_at=now - timedelta(days=2),
    )
    env.store.objects = [(old, now - timedelta(days=2))]
    removed = await sweep_media_uploads(dry_run=True)
    assert removed["expired"] >= 1
    assert env.store.deleted == []
    assert await issued_row(env.sessions, old) is not None


# ==================== §6-C: chat attachments via direct keys ====================
#
# Everything above proves the media-service boundary. Everything below proves
# the CHAT wiring on top of it: prepare binds → reads back → inlines server
# mime; offload persists the BOUND key and never re-PUTs; every bind-visible
# failure surfaces as an AppError BEFORE the SSE stream, and the uncommitted
# bind rolls back so the row stays ISSUED for GC.


@pytest.fixture(autouse=True)
def _storage_backend_uses_fake_store(env, monkeypatch):
    # StorageBackend is a process singleton frozen to remote/local at first
    # construction, so patching settings is not enough here: the chat path
    # reads bytes through agent_attachment_service.get_storage_backend, and
    # that is what must point at the fake.
    monkeypatch.setattr(agent_attachment_service, "get_storage_backend", lambda: env.store)


# Magic-bytes-accurate payloads: the sniff `prepare` runs is prefix-only (its
# docstring says "no parser"), so the fixtures test exactly what production
# tests — a real header that passes, and a lying body that does not.
JPEG = b"\xff\xd8\xff\xe0" + bytes(range(120)) + b"\xff\xd9"
WEBM = b"\x1a\x45\xdf\xa3" + bytes(range(40))
SVG = b"<svg onload='alert(1)'></svg>"


def att(**kw) -> AgentAttachment:
    base = {"kind": "image", "name": "p.jpg", "mime_type": "image/jpeg"}
    base.update(kw)
    return AgentAttachment(**base)


def put_blob(env, key, body) -> None:  # noqa: ANN001
    env.store.bodies[key] = body
    env.store.sizes[key] = len(body)


async def _prepare(env, attachments, *, actor=OWNER, session_id="agsn_s1", commit=False):  # noqa: ANN001
    """Mirror the route: one request-scoped session, commit only on success."""
    db = env.sessions()
    try:
        out = await prepare_direct_attachments(
            attachments, db=db, actor=actor, session_id=session_id
        )
        if commit:
            await db.commit()
        return out
    finally:
        await db.close()


# ------------------------- schema-level exclusivity -------------------------


def test_object_key_and_data_url_are_mutually_exclusive():
    with pytest.raises(ValueError):
        att(
            object_key="jc/dev/uploads/usr_owner/chat-image/2026/11/18/k.jpg",
            data_url="data:image/jpeg;base64,AAAA",
        )


def test_file_attachments_cannot_be_direct():
    with pytest.raises(ValueError):
        att(
            kind="file",
            name="x.pdf",
            object_key="jc/dev/uploads/usr_owner/chat-image/2026/11/18/k.jpg",
        )


# ------------------------------ the pass side ------------------------------


async def test_direct_key_binds_hydrates_and_persists_the_bound_key(env):
    key = await make_issued(env)  # row says image/jpeg
    put_blob(env, key, JPEG)
    # Client lies about the mime; the sign-time record must win everywhere.
    prepared = await _prepare(env, [att(object_key=key, mime_type="image/png")], commit=True)

    (hydrated,) = prepared
    assert hydrated.object_key == key
    assert hydrated.mime_type == "image/jpeg"
    assert hydrated.data_url == f"data:image/jpeg;base64,{base64.b64encode(JPEG).decode()}"

    row = await issued_row(env.sessions, key)
    assert row.state == MediaUploadState.BOUND
    assert row.actual_size == len(JPEG)
    assert row.bound_ref == "agsn:agsn_s1"

    # Persistence: the bound key is the durable record, re-signed on replay,
    # and the bytes are NEVER copied a second time under agent/.
    env.store.puts.clear()
    (stored,) = await offload_for_persistence(prepared, session_id="agsn_s1", message_id="agm_m1")
    assert stored["storage_key"] == key
    assert stored["size_bytes"] == len(JPEG)
    assert stored["download_url"] == f"https://bucket.test/{key}?get=fake"
    assert "data_url" not in stored  # the whole point of this module
    assert env.store.puts == []


async def test_audio_attachment_binds_chat_audio_scene(env):
    key = await make_issued(env, scene="chat-audio", content_type="audio/webm")
    put_blob(env, key, WEBM)
    prepared = await _prepare(
        env, [att(kind="audio", name="v.webm", mime_type="audio/webm", object_key=key)]
    )
    assert prepared[0].data_url.startswith("data:audio/webm;base64,")
    assert prepared[0].mime_type == "audio/webm"


async def test_prepare_is_a_noop_passthrough_without_keys(env):
    plain = att()
    assert await _prepare(env, [plain]) == [plain]


# ----------------------------- the reject side -----------------------------


async def test_foreign_key_is_403_and_binds_nothing(env):
    key = await make_issued(env)
    put_blob(env, key, JPEG)
    with pytest.raises(ForbiddenError) as exc:
        await _prepare(env, [att(object_key=key)], actor=OTHER)
    assert exc.value.code == "foreign_upload"
    assert (await issued_row(env.sessions, key)).state == MediaUploadState.ISSUED


async def test_unknown_key_is_rejected(env):
    unknown = "jc/dev/uploads/usr_owner/chat-image/2026/11/18/nope.jpg"
    with pytest.raises(NotFoundError):
        await _prepare(env, [att(object_key=unknown)])


async def test_expired_key_is_gone(env):
    key = await make_issued(env, expires_offset_sec=-10)
    put_blob(env, key, JPEG)
    with pytest.raises(GoneError):
        await _prepare(env, [att(object_key=key)])


async def test_never_uploaded_object_is_rejected_before_readback(env):
    key = await make_issued(env)  # no bodies/sizes: HEAD says missing
    with pytest.raises(NotFoundError) as exc:
        await _prepare(env, [att(object_key=key)])
    assert exc.value.code == "upload_not_found"


async def test_double_use_of_one_key_conflicts(env):
    key = await make_issued(env)
    put_blob(env, key, JPEG)
    await _prepare(env, [att(object_key=key)], commit=True)
    with pytest.raises(ConflictError) as exc:
        await _prepare(env, [att(object_key=key)], session_id="agsn_s2")
    assert exc.value.code == "already_bound"


async def test_spoofed_content_under_own_key_is_rejected_and_row_stays_issued(env):
    # P1-2 closed the inline path (svg bytes as image/jpeg reached the ledger);
    # the direct path must not reopen it. The row legitimately says image/jpeg
    # — sign whitelists by contentType — so the sniff must fire on the readback.
    key = await make_issued(env)
    put_blob(env, key, SVG)
    with pytest.raises(AttachmentRejectedError):
        await _prepare(env, [att(object_key=key)])
    # The bind was never committed (route commits with the user row), so the
    # close rolled it back: GC still owns the object.
    assert (await issued_row(env.sessions, key)).state == MediaUploadState.ISSUED


async def test_empty_object_is_rejected(env):
    key = await make_issued(env)
    put_blob(env, key, b"")
    with pytest.raises(AttachmentRejectedError):
        await _prepare(env, [att(object_key=key)])
    assert (await issued_row(env.sessions, key)).state == MediaUploadState.ISSUED


async def test_object_over_scene_cap_is_rejected_at_bind(env):
    # Chat scene cap and chat per-file cap coincide at 8 MiB today; bind's HEAD
    # is what fires, and the row stays ISSUED so GC reclaims the object.
    key = await make_issued(env)
    put_blob(env, key, JPEG + b"\x00" * (8 * 1024 * 1024))
    from jc.services.media_scene import MediaSceneError

    with pytest.raises(MediaSceneError) as exc:
        await _prepare(env, [att(object_key=key)])
    assert exc.value.code == "uploaded_size_over_limit"
    assert (await issued_row(env.sessions, key)).state == MediaUploadState.ISSUED


async def test_image_kind_cannot_consume_an_audio_scene_key(env):
    # The scene is chosen from the attachment KIND server-side; claiming a
    # legitimately-owned chat-audio key for a photo is a mismatch, never an
    # implicit upgrade.
    key = await make_issued(env, scene="chat-audio", content_type="audio/webm")
    put_blob(env, key, JPEG)
    with pytest.raises(ForbiddenError) as exc:
        await _prepare(env, [att(object_key=key)])
    assert exc.value.code == "scene_mismatch"


async def test_direct_and_inline_attachments_count_against_the_combined_cap(env):
    # Exactly 8 MiB each: per-file caps pass (the check is strictly `>`), so
    # the only thing that can stop 4 of them is the message total.
    eight_mib = JPEG + b"\x00" * (8 * 1024 * 1024 - len(JPEG))
    assert len(eight_mib) == 8 * 1024 * 1024
    inline = att(data_url=f"data:image/jpeg;base64,{base64.b64encode(eight_mib).decode()}")
    keys = []
    for _ in range(3):
        key = await make_issued(env)
        put_blob(env, key, eight_mib)
        keys.append(key)
    with pytest.raises(AttachmentTooLargeError):
        await _prepare(env, [inline, *(att(object_key=key) for key in keys)])
    # Nothing bound survives a rejected message: binds rolled back with the
    # request transaction, GC owns all three objects.
    for key in keys:
        assert (await issued_row(env.sessions, key)).state == MediaUploadState.ISSUED
