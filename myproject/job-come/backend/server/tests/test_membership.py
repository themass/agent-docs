"""Download quota, redeem codes, and the admin side of both. SQLite, no network."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401 — registers every table on Base.metadata
from jc.db.base import Base
from jc.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from jc.models.membership import AdminAuditLog, MembershipLedger, RedeemCode
from jc.models.profile import Profile
from jc.models.resume import ExportJob, ResumeDraft
from jc.models.user import User
from jc.schemas.resume import ExportRequest
from jc.services.membership_service import (
    REDEEM_MAX_FAILURES,
    RESERVATION_TTL,
    MembershipService,
    normalize_code,
)
from jc.services.profile_service import ProfileService
from jc.services.redeem_admin_service import RedeemAdminService
from jc.services.resume_render_engine import ResumeRenderEngine
from jc.services.resume_service import ResumeService
from jc.stores.resume_store import ResumeStore
from test_export_lifecycle import FIXTURE_SECTIONS


@pytest.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/membership.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def db(sessions):
    async with sessions() as session:
        yield session


async def _user(db, uid, *, role="user", vip_expires_at=None, free_used=None):
    db.add(
        User(
            id=uid,
            email=f"{uid}@example.test",
            password_hash="x",
            role=role,
            vip_expires_at=vip_expires_at,
            free_download_used_at=free_used,
        )
    )
    await db.commit()


async def _code(db, value, *, status="unused", expires_at=None, days=30):
    db.add(
        RedeemCode(
            id=f"rdc_{value}",
            code=value,
            batch_id="rdb_test",
            plan="monthly",
            duration_days=days,
            status=status,
            expires_at=expires_at,
            created_by="admin_test",
        )
    )
    await db.commit()


async def _reload(db, uid) -> User:
    stmt = select(User).where(User.id == uid).execution_options(populate_existing=True)
    return (await db.execute(stmt)).scalar_one()


def _now() -> datetime:
    return datetime.now(UTC)


def _close(value: datetime | None, expected: datetime) -> bool:
    return value is not None and abs(value - expected) < timedelta(minutes=1)


async def test_free_user_gets_one_download(db):
    await _user(db, "free")
    service = MembershipService(db)
    await service.claim_download("free", "expj_1")
    await service.consume_download("free", "expj_1")
    await db.commit()

    snapshot = await service.snapshot("free")
    assert snapshot.tier == "free" and not snapshot.free_download_available
    with pytest.raises(ForbiddenError) as exc:
        await service.claim_download("free", "expj_2")
    assert exc.value.code == "download_quota_exhausted"


async def test_failed_export_gives_the_download_back(db):
    await _user(db, "retry")
    service = MembershipService(db)
    await service.claim_download("retry", "expj_1")
    await service.release_download("retry", "expj_1")
    await db.commit()

    await service.claim_download("retry", "expj_2")
    await db.commit()
    assert (await _reload(db, "retry")).free_download_job_id == "expj_2"


async def test_overlapping_export_is_told_to_wait(db):
    await _user(db, "busy")
    service = MembershipService(db)
    await service.claim_download("busy", "expj_1")
    with pytest.raises(ForbiddenError) as exc:
        await service.claim_download("busy", "expj_2")
    assert exc.value.code == "download_quota_pending"


async def test_stale_reservation_is_taken_over(db):
    await _user(db, "crashed")
    service = MembershipService(db)
    await service.claim_download("crashed", "expj_1")
    await db.execute(
        update(User)
        .where(User.id == "crashed")
        .values(free_download_reserved_at=_now() - RESERVATION_TTL - timedelta(minutes=1))
    )
    await db.commit()

    await service.claim_download("crashed", "expj_2")
    await db.commit()
    assert (await _reload(db, "crashed")).free_download_job_id == "expj_2"


async def test_members_never_touch_the_free_download(db):
    await _user(db, "member", vip_expires_at=_now() + timedelta(days=5))
    service = MembershipService(db)
    for job in ("expj_1", "expj_2", "expj_3"):
        await service.claim_download("member", job)
        await service.consume_download("member", job)
    await db.commit()

    user = await _reload(db, "member")
    assert user.free_download_used_at is None and user.free_download_job_id is None
    assert (await service.snapshot("member")).tier == "vip"


async def test_admin_is_unlimited(db):
    await _user(db, "boss", role="admin", free_used=_now())
    service = MembershipService(db)
    await service.claim_download("boss", "expj_1")
    await service.claim_download("boss", "expj_2")
    assert (await service.snapshot("boss")).tier == "admin"


async def test_redeem_grants_one_month_and_only_once(db):
    await _user(db, "buyer")
    await _user(db, "second")
    await _code(db, "ABCD2345EFGH6789")
    service = MembershipService(db)

    snapshot = await service.redeem("buyer", "ABCD2345EFGH6789")
    assert snapshot.tier == "vip"
    assert _close((await _reload(db, "buyer")).vip_expires_at, _now() + timedelta(days=30))

    with pytest.raises(ConflictError) as exc:
        await service.redeem("second", "ABCD2345EFGH6789")
    assert exc.value.code == "redeem_code_used"

    ledger = (await db.execute(select(MembershipLedger))).scalars().all()
    assert len(ledger) == 1 and ledger[0].user_id == "buyer" and ledger[0].days == 30


async def test_stale_read_cannot_grant_a_code_twice(db, monkeypatch):
    """Two requests read the code as unused before either commits; the UPDATE is the guard."""
    await _user(db, "racer_a")
    await _user(db, "racer_b")
    await _code(db, "RACE00000000H004")
    service = MembershipService(db)
    await service.redeem("racer_a", "RACE00000000H004")

    monkeypatch.setattr(MembershipService, "_redeem_problem", staticmethod(lambda code, now: None))
    with pytest.raises(ConflictError) as exc:
        await service.redeem("racer_b", "RACE00000000H004")
    assert exc.value.code == "redeem_code_used"
    assert (await _reload(db, "racer_b")).vip_expires_at is None
    assert len((await db.execute(select(MembershipLedger))).scalars().all()) == 1


async def test_redeem_extends_from_current_expiry(db):
    current = _now() + timedelta(days=10)
    await _user(db, "renew", vip_expires_at=current)
    await _code(db, "RENEW0000000000A")

    await MembershipService(db).redeem("renew", "RENEW0000000000A")
    assert _close((await _reload(db, "renew")).vip_expires_at, current + timedelta(days=30))


async def test_expired_membership_does_not_backfill(db):
    await _user(db, "lapsed", vip_expires_at=_now() - timedelta(days=5))
    await _code(db, "LAPSED00000000B1")

    await MembershipService(db).redeem("lapsed", "LAPSED00000000B1")
    assert _close((await _reload(db, "lapsed")).vip_expires_at, _now() + timedelta(days=30))


async def test_redeem_accepts_typed_variants(db):
    await _user(db, "typist")
    await _code(db, "TYPE00000000C0D1")

    assert normalize_code(" type-0000 0000-c0d1 ") == "TYPE00000000C0D1"
    snapshot = await MembershipService(db).redeem("typist", "type-0000 0000-c0d1")
    assert snapshot.tier == "vip"


async def test_void_and_expired_codes_are_rejected(db):
    await _user(db, "unlucky")
    await _code(db, "VOID000000000E01", status="void")
    await _code(db, "OLD0000000000F02", expires_at=_now() - timedelta(hours=1))
    service = MembershipService(db)

    with pytest.raises(ConflictError) as voided:
        await service.redeem("unlucky", "VOID000000000E01")
    assert voided.value.code == "redeem_code_void"
    with pytest.raises(ConflictError) as expired:
        await service.redeem("unlucky", "OLD0000000000F02")
    assert expired.value.code == "redeem_code_expired"


async def test_repeated_wrong_codes_lock_redeeming(db):
    await _user(db, "guesser")
    await _code(db, "REAL000000000G03")
    service = MembershipService(db)

    for _ in range(REDEEM_MAX_FAILURES):
        with pytest.raises(AppError) as exc:
            await service.redeem("guesser", "NOTAREALCODE0000")
        assert exc.value.code == "redeem_code_invalid"

    with pytest.raises(ForbiddenError) as locked:
        await service.redeem("guesser", "REAL000000000G03")
    assert locked.value.code == "redeem_locked"


async def test_batch_codes_are_unique_and_audited(db):
    admin = RedeemAdminService(db)
    batch = await admin.create_batch(
        actor_user_id="admin_1", count=40, note="咸鱼 第一批", expires_at=None
    )

    assert batch.count == 40 and len(set(batch.codes)) == 40
    assert all(len(code) == 19 and code.count("-") == 3 for code in batch.codes)
    rows = (
        (await db.execute(select(RedeemCode).where(RedeemCode.batch_id == batch.batch_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 40 and {row.status for row in rows} == {"unused"}
    audits = (await db.execute(select(AdminAuditLog))).scalars().all()
    assert [a.action for a in audits] == ["redeem_batch.create"]
    assert audits[0].detail["count"] == 40 and not any(
        code in str(audits[0].detail) for code in batch.codes
    )


async def test_only_unused_codes_can_be_voided_or_deleted(db):
    admin = RedeemAdminService(db)
    batch = await admin.create_batch(actor_user_id="admin_1", count=2, note=None, expires_at=None)
    keep, drop = batch.codes
    keep_row = (
        await admin.list_codes(status=None, batch_id=None, search=keep, limit=10, offset=0)
    ).items[0]
    drop_row = (
        await admin.list_codes(status=None, batch_id=None, search=drop, limit=10, offset=0)
    ).items[0]

    voided = await admin.void_code(actor_user_id="admin_1", code_id=keep_row.id)
    assert voided.status == "void" and voided.voided_at is not None
    with pytest.raises(ConflictError):
        await admin.void_code(actor_user_id="admin_1", code_id=keep_row.id)

    await admin.delete_code(actor_user_id="admin_1", code_id=drop_row.id)
    assert (
        await admin.list_codes(status=None, batch_id=None, search=None, limit=10, offset=0)
    ).total == 1


async def test_redeemed_codes_cannot_be_voided_or_deleted(db):
    await _user(db, "holder")
    admin = RedeemAdminService(db)
    batch = await admin.create_batch(actor_user_id="admin_1", count=1, note=None, expires_at=None)
    code_row = (
        await admin.list_codes(status=None, batch_id=batch.batch_id, search=None, limit=5, offset=0)
    ).items[0]
    await MembershipService(db).redeem("holder", batch.codes[0])

    with pytest.raises(ConflictError) as voided:
        await admin.void_code(actor_user_id="admin_1", code_id=code_row.id)
    assert voided.value.code == "redeem_code_not_voidable"
    with pytest.raises(ConflictError) as deleted:
        await admin.delete_code(actor_user_id="admin_1", code_id=code_row.id)
    assert deleted.value.code == "redeem_code_not_deletable"

    listing = await admin.list_codes(status=None, batch_id=None, search=None, limit=5, offset=0)
    assert (
        listing.stats.redeemed == 1 and listing.items[0].redeemed_by_email == "holder@example.test"
    )


async def test_csv_export_defaults_to_unused_codes(db):
    admin = RedeemAdminService(db)
    batch = await admin.create_batch(actor_user_id="admin_1", count=3, note=None, expires_at=None)
    first = (
        await admin.list_codes(status=None, batch_id=batch.batch_id, search=None, limit=1, offset=0)
    ).items[0]
    await admin.void_code(actor_user_id="admin_1", code_id=first.id)

    rows = await admin.export_csv_rows(actor_user_id="admin_1", status=None, batch_id=None)
    assert len(rows) == 2 and all(row.status == "unused" for row in rows)


async def test_purchase_url_must_be_http_or_https(db):
    admin = RedeemAdminService(db)
    with pytest.raises(AppError) as exc:
        await admin.set_purchase_url(actor_user_id="admin_1", url="javascript:alert(1)")
    assert exc.value.code == "invalid_purchase_url"

    await admin.set_purchase_url(actor_user_id="admin_1", url="https://m.tb.cn/h.jguIPNU")
    assert await admin.get_purchase_url() == "https://m.tb.cn/h.jguIPNU"


# -- end to end through the real export path -------------------------------------------


@pytest.fixture
async def export_env(sessions):
    async with sessions() as db:
        db.add(User(id="u", email="u@example.test", password_hash="x"))
        await db.flush()
        db.add(
            Profile(
                id="p",
                user_id="u",
                owner_kind="user",
                payload={"contact": {"name": "Fixture"}, "summary": "Original text"},
                version=1,
            )
        )
        await db.flush()
        db.add(
            ResumeDraft(
                id="d",
                profile_id="p",
                profile_version=1,
                elevation_level="elevated",
                locale="zh-CN",
                template_id="zh-one-page",
                sections=FIXTURE_SECTIONS,
                reviewer_status="failed",
                reviewer_notes="Keep findings",
            )
        )
        await db.commit()
    yield


def _resume_service(db, uploaded: list[str]) -> ResumeService:
    svc = object.__new__(ResumeService)
    svc._db = db
    svc._profiles = ProfileService(db)
    svc._resumes = ResumeStore(db)
    svc._renderer = ResumeRenderEngine()
    svc._review_draft = AsyncMock(side_effect=AssertionError("No paid calls during exports"))
    svc._storage = SimpleNamespace(put_object=lambda key, content, **kwargs: uploaded.append(key))
    return svc


async def test_successful_export_spends_the_free_download(sessions, export_env, monkeypatch):
    monkeypatch.setattr("jc.services.resume_service.download_url_for_key", lambda key: f"/f/{key}")
    uploaded: list[str] = []
    actor = UserActor(user_id="u", session_id="s")
    body = ExportRequest(draft_id="d", format="docx")

    async with sessions() as db:
        first = await _resume_service(db, uploaded).export("p", actor=actor, body=body)
        assert first.status == "done"
        with pytest.raises(ForbiddenError) as exc:
            await _resume_service(db, uploaded).export("p", actor=actor, body=body)
        assert exc.value.code == "download_quota_exhausted"

    async with sessions() as db:
        user = await _reload(db, "u")
        assert user.free_download_used_at is not None and user.free_download_job_id is None
        assert len((await db.execute(select(ExportJob))).scalars().all()) == 1
    assert len(uploaded) == 1


async def test_failed_export_leaves_the_free_download_available(sessions, export_env, monkeypatch):
    monkeypatch.setattr("jc.services.resume_service.download_url_for_key", lambda key: f"/f/{key}")
    uploaded: list[str] = []
    actor = UserActor(user_id="u", session_id="s")
    body = ExportRequest(draft_id="d", format="docx")

    async with sessions() as db:
        svc = _resume_service(db, uploaded)

        def broken_render(_sections):
            raise ValueError("render broke")

        svc._renderer.render_docx = broken_render
        failed = await svc.export("p", actor=actor, body=body)
        assert failed.status == "failed"

    async with sessions() as db:
        user = await _reload(db, "u")
        assert user.free_download_used_at is None and user.free_download_job_id is None

    async with sessions() as db:
        retried = await _resume_service(db, uploaded).export("p", actor=actor, body=body)
        assert retried.status == "done"


# -- admin gifts ------------------------------------------------------------------------


async def test_gift_grants_days_and_records_the_grant(db):
    await _user(db, "target")
    admin = RedeemAdminService(db)

    result = await admin.gift_membership(
        actor_user_id="admin_1", email="target@example.test", days=30, note="补偿一次导出失败"
    )

    assert result.user_id == "target" and result.days == 30
    assert _close((await _reload(db, "target")).vip_expires_at, _now() + timedelta(days=30))
    assert (await MembershipService(db).snapshot("target")).tier == "vip"

    row = (await db.execute(select(RedeemCode).where(RedeemCode.id == result.code_id))).scalar_one()
    assert row.status == "redeemed" and row.plan == "gift" and row.redeemed_by_user_id == "target"
    assert row.created_by == "admin_1" and row.note == "补偿一次导出失败"
    ledger = (await db.execute(select(MembershipLedger))).scalars().all()
    assert [(entry.source, entry.user_id, entry.days) for entry in ledger] == [
        ("gift", "target", 30)
    ]
    audits = (await db.execute(select(AdminAuditLog))).scalars().all()
    assert [a.action for a in audits] == ["membership.gift"]
    assert audits[0].target_id == "target" and audits[0].detail["days"] == 30


async def test_gift_stacks_on_a_live_membership(db):
    current = _now() + timedelta(days=12)
    await _user(db, "member", vip_expires_at=current)

    await RedeemAdminService(db).gift_membership(
        actor_user_id="admin_1", email="member@example.test", days=7, note=None
    )
    assert _close((await _reload(db, "member")).vip_expires_at, current + timedelta(days=7))


async def test_gift_after_lapse_starts_from_now(db):
    await _user(db, "lapsed2", vip_expires_at=_now() - timedelta(days=40))

    await RedeemAdminService(db).gift_membership(
        actor_user_id="admin_1", email="lapsed2@example.test", days=10, note=None
    )
    assert _close((await _reload(db, "lapsed2")).vip_expires_at, _now() + timedelta(days=10))


async def test_gift_matches_email_ignoring_case_and_spaces(db):
    await _user(db, "casey")

    result = await RedeemAdminService(db).gift_membership(
        actor_user_id="admin_1", email="  CASEY@Example.TEST ", days=5, note=None
    )
    assert result.user_id == "casey"


async def test_gift_to_unknown_or_deleted_account_changes_nothing(db):
    await _user(db, "gone")
    await db.execute(update(User).where(User.id == "gone").values(deleted_at=_now()))
    await db.commit()
    admin = RedeemAdminService(db)

    for address in ("nobody@example.test", "gone@example.test"):
        with pytest.raises(NotFoundError) as exc:
            await admin.gift_membership(actor_user_id="admin_1", email=address, days=30, note=None)
        assert exc.value.code == "gift_user_not_found"

    assert (await db.execute(select(RedeemCode))).scalars().all() == []
    assert (await db.execute(select(MembershipLedger))).scalars().all() == []
    assert (await db.execute(select(AdminAuditLog))).scalars().all() == []


@pytest.mark.parametrize("days", [0, -3, 366])
async def test_gift_rejects_out_of_range_days(db, days):
    await _user(db, "ranged")
    with pytest.raises(AppError) as exc:
        await RedeemAdminService(db).gift_membership(
            actor_user_id="admin_1", email="ranged@example.test", days=days, note=None
        )
    assert exc.value.code == "invalid_gift_days"
    assert (await _reload(db, "ranged")).vip_expires_at is None


async def test_gifts_never_appear_in_the_default_csv_or_count_as_unused(db):
    await _user(db, "recipient")
    admin = RedeemAdminService(db)
    await admin.create_batch(actor_user_id="admin_1", count=2, note=None, expires_at=None)
    await admin.gift_membership(
        actor_user_id="admin_1", email="recipient@example.test", days=30, note=None
    )

    rows = await admin.export_csv_rows(actor_user_id="admin_1", status=None, batch_id=None)
    assert len(rows) == 2 and all(row.plan == "monthly" for row in rows)
    listing = await admin.list_codes(status=None, batch_id=None, search=None, limit=10, offset=0)
    assert listing.stats.unused == 2 and listing.stats.redeemed == 1
