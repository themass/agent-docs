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
from jc.services import media_service
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

    def presigned_put_url(self, key, *, content_type=None, expires_in=600):
        self.signed.append({"key": key, "content_type": content_type, "expires_in": expires_in})
        return f"https://bucket.test/{key}?sig=fake"

    def head_object_size(self, key):
        return self.sizes.get(key)

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
        size = await MediaService(db).bind(
            actor=OWNER,
            object_key=key,
            scene="chat-image",
            bound_ref="msg_1",
        )
        await db.commit()
    assert size == 123_456
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
