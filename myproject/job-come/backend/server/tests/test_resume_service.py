import pytest


@pytest.fixture(autouse=True)
def confirmation_projection(monkeypatch):
    from jc.services import resume_service

    async def project(_db, _profile_id, payload):
        return payload

    monkeypatch.setattr(resume_service, "with_confirmed_fields", project)



@pytest.mark.asyncio
async def test_elevate_releases_db_connection_before_slow_generation():
    """A slow model call must not retain a remote MySQL transaction/connection."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from jc.services.resume_service import ResumeService

    events: list[str] = []

    async def rollback():
        events.append("rollback")

    async def build_sections(*_args, **_kwargs):
        events.append("build_sections")
        return {"header": {}}, []

    from jc.schemas.profile_payload import ProfilePayload
    from jc.services.resume_service import JobHints

    service = object.__new__(ResumeService)
    service._db = SimpleNamespace()
    service._profiles = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(payload=ProfilePayload(), version=3)
        )
    )
    service._job_hints = AsyncMock(return_value=JobHints())
    service._elevator = SimpleNamespace(build_sections=build_sections)
    service._resumes = SimpleNamespace(create_draft=AsyncMock())
    service._to_draft_response = lambda draft, **_kw: SimpleNamespace(id=draft.id)
    service._db = SimpleNamespace(
        rollback=rollback,
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )

    await service.elevate(
        "prof_test",
        actor=SimpleNamespace(),
        elevation_level="elevated",
        locale="zh-CN",
    )

    assert events == ["rollback", "build_sections"]
    service._db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_review_draft_releases_db_connection_before_review_call():
    """The reviewer model call must not hold the pooled MySQL connection."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from jc.models.enums import ReviewerStatus
    from jc.services.resume_service import ResumeService

    events: list[str] = []

    async def rollback():
        events.append("rollback")

    async def review(*, sections, source_profile, role_family=None):
        events.append("review")
        assert sections == {"header": {"name": "A"}}
        assert source_profile == {"contact": {}}
        # The draft carries no family, so the reviewer must still be told which
        # playbook to apply rather than silently defaulting to engineering rules.
        assert role_family == "general"
        return SimpleNamespace(
            status=ReviewerStatus.PASSED, notes=None, issues=[], available=True
        )

    service = object.__new__(ResumeService)
    service._db = SimpleNamespace()
    service._reviewer = SimpleNamespace(review=review)
    service._db = SimpleNamespace(rollback=rollback)

    draft = SimpleNamespace(
        id="rdft_1",
        profile_id="prof_1",
        profile_version=1,
        locale="zh-CN",
        sections={"header": {"name": "A"}},
    )

    import jc.stores.profile_store as profile_store_module

    original_store = profile_store_module.ProfileStore
    profile_store_module.ProfileStore = lambda _db: SimpleNamespace(  # type: ignore[assignment]
        get_by_id=AsyncMock(return_value=SimpleNamespace(payload={"contact": {}}))
    )
    try:
        result = await service._review_draft(draft)
    finally:
        profile_store_module.ProfileStore = original_store  # type: ignore[assignment]

    assert events == ["rollback", "review"]
    assert result["status"] == "passed"
    assert result["reviewed"] is True
    assert result["blocking_issue_count"] == 0


@pytest.mark.asyncio
async def test_review_for_export_reloads_draft_after_review():
    """Writing reviewer status must use a draft re-loaded in a fresh transaction."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from jc.models.enums import ReviewerStatus
    from jc.services.resume_service import ResumeService

    stale = SimpleNamespace(
        id="rdft_1", profile_id="prof_1", locale="zh-CN", sections={}, job_id=None
    )
    fresh = SimpleNamespace(
        id="rdft_1",
        profile_id="prof_1",
        profile_version=1,
        locale="zh-CN",
        sections={},
        job_id=None,
        reviewer_status=None,
        reviewer_notes=None,
    )

    from jc.services.resume_service import JobHints

    service = object.__new__(ResumeService)
    service._db = SimpleNamespace()
    service._profiles = SimpleNamespace(get=AsyncMock())
    service._job_hints = AsyncMock(return_value=JobHints())
    service._resumes = SimpleNamespace(
        get_draft_by_id=AsyncMock(side_effect=[stale, fresh]),
        get_latest_draft=AsyncMock(),
    )
    service._review_draft = AsyncMock(
        return_value={"can_export": True, "notes": "ok", "status": "passed", "issues": []}
    )
    service._db = SimpleNamespace(commit=AsyncMock())

    result = await service.review_for_export(
        "prof_1", actor=SimpleNamespace(user_id="u1"), draft_id="rdft_1"
    )

    assert result["draft_id"] == "rdft_1"
    # Screening diagnostics and the coverage audit ride along with the review so step 4
    # can answer "will this be read", "is this honest" and "did it keep my career".
    assert "estimated_pages" in result["diagnostics"]
    assert "source_highlights" in result["coverage"]
    assert fresh.reviewer_status == ReviewerStatus.PASSED
    assert fresh.reviewer_notes == "ok"
    assert not hasattr(stale, "reviewer_status")


@pytest.mark.asyncio
async def test_prepare_tracks_releases_connection_before_generating_drafts():
    """Track generation must release the pooled MySQL connection before model calls."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from jc.services.resume_service import ResumeService

    events: list[str] = []

    async def rollback():
        events.append("rollback")

    async def build_sections(_payload, *, elevation_level, locale):
        events.append(f"build:{locale}")
        return {"header": {"locale": locale}}, []

    async def commit():
        events.append("commit")

    row = SimpleNamespace(
        payload={"meta": {}, "contact": {}},
        version=2,
        locale=None,
    )

    service = object.__new__(ResumeService)
    service._db = SimpleNamespace()
    service._elevator = SimpleNamespace(build_sections=build_sections)
    service._localizer = SimpleNamespace(translate=AsyncMock(return_value={}))
    service._resumes = SimpleNamespace(
        get_latest_draft=AsyncMock(return_value=None),
        create_draft=AsyncMock(),
    )
    service._db = SimpleNamespace(rollback=rollback, commit=commit)

    import jc.services.resume_service as resume_service_module

    original_store = resume_service_module.ProfileStore
    resume_service_module.ProfileStore = lambda _db: SimpleNamespace(  # type: ignore[assignment]
        get_by_id=AsyncMock(return_value=row)
    )
    try:
        await service.prepare_tracks("prof_1", elevation_level="conservative")
    finally:
        resume_service_module.ProfileStore = original_store  # type: ignore[assignment]

    # Both track generations run after the connection is released, writes happen afterwards.
    rollback_at = events.index("rollback")
    build_positions = [i for i, e in enumerate(events) if e.startswith("build:")]
    assert build_positions, "expected track generation"
    assert all(pos > rollback_at for pos in build_positions)
    assert events[-1] == "commit"
    assert service._resumes.create_draft.await_count == 2


@pytest.mark.asyncio
async def test_job_hints_carry_fit_gaps_into_the_writer() -> None:
    """fit_score already names what the JD wants and the resume does not show.

    Those gaps were produced and stored, then never used. The writer needs them to go
    looking for existing support in the profile, which is the whole point of scoring.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from jc.services.resume_service import ResumeService

    job = SimpleNamespace(
        id="job_1",
        profile_id="prof_1",
        title="后端技术专家",
        role_category="backend",
        requirements={"keywords": ["可观测性"], "must_have_skills": ["Go"]},
        fit_gaps=["缺少可观测性体系的证据"],
        fit_report={"elevate_hints": ["把监控埋点体系前置到第一条"]},
    )

    service = object.__new__(ResumeService)
    service._db = SimpleNamespace()
    service._db = SimpleNamespace()

    import jc.stores.job_store as job_store_module

    original = job_store_module.JobStore
    job_store_module.JobStore = lambda _db: SimpleNamespace(  # type: ignore[assignment]
        get_by_id=AsyncMock(return_value=job)
    )
    try:
        hints = await service._job_hints("prof_1", "job_1")
    finally:
        job_store_module.JobStore = original  # type: ignore[assignment]

    assert hints.keywords == ["可观测性", "Go"]
    assert hints.title == "后端技术专家"
    assert hints.role_category == "backend"
    assert hints.gaps == ["缺少可观测性体系的证据"]
    assert hints.elevate_hints == ["把监控埋点体系前置到第一条"]


@pytest.mark.asyncio
async def test_draft_role_family_falls_back_to_the_stored_preference() -> None:
    """Drafts written before role_family existed must still be reviewed correctly."""
    from jc.services.resume_service import ResumeService

    assert (
        ResumeService._draft_role_family({"role_family": "design"}, {"preferences": {}})
        == "design"
    )
    assert (
        ResumeService._draft_role_family(
            {}, {"preferences": {"role_family": "legal"}, "experiences": []}
        )
        == "legal"
    )
    assert (
        ResumeService._draft_role_family(
            {}, {"preferences": {}, "experiences": [{"title": "数据分析师"}]}
        )
        == "data"
    )
    assert (
        ResumeService._draft_role_family(
            {"track": "bilingual", "zh_sections": {"role_family": "pm"}}, None
        )
        == "pm"
    )


@pytest.mark.asyncio
async def test_preview_reports_coverage_and_length_at_step_three() -> None:
    """Step 3 must carry both signals the user can still act on.

    Finding a dropped accomplishment or a half-page resume on the download screen is
    too late: regenerating, changing the framing angle and answering an evidence
    question all live at step 3.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from jc.schemas.profile_payload import ProfileExperience, ProfilePayload
    from jc.services.resume_service import JobHints, ResumeService

    payload = ProfilePayload(
        experiences=[
            ProfileExperience(
                id="exp_1",
                company="某公司",
                title="后端技术专家",
                start_date="2020-01",
                highlights=[
                    "主导订单服务从单体拆分为 6 个微服务，发布耗时从 40 分钟降到 6 分钟",
                    "搭建统一配置中心，覆盖 120 多个服务",
                ],
            )
        ]
    )
    sections = {
        "header": {"name": "张三"},
        "experience_blocks": [
            {
                "company": "某公司",
                "title": "后端技术专家",
                "bullets": [
                    "主导订单服务从单体拆分为 6 个微服务，把发布耗时从 40 分钟压缩到 6 分钟",
                ],
            }
        ],
    }

    draft = SimpleNamespace(
        id="rdft_1",
        profile_id="prof_1",
        profile_version=1,
        locale="zh-CN",
        template_id="zh-one-page",
        job_id=None,
        sections=sections,
        elevation_map=[],
    )

    service = object.__new__(ResumeService)
    service._db = SimpleNamespace()
    service._profiles = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(payload=payload, version=1))
    )
    service._job_hints = AsyncMock(return_value=JobHints())
    service._resumes = SimpleNamespace(get_latest_draft=AsyncMock(return_value=draft))
    service._renderer = SimpleNamespace(render_html=lambda *_a, **_k: "<html></html>")
    service._normalize_sections = lambda s, _p, locale=None: s
    from datetime import UTC, datetime

    from jc.schemas.resume import ResumeDraftResponse

    service._to_draft_response = lambda d, **_kw: ResumeDraftResponse(
        id=d.id,
        profile_id=d.profile_id,
        profile_version=1,
        elevation_level="elevated",
        locale=d.locale,
        template_id=d.template_id,
        sections=d.sections,
        elevation_map=[],
        reviewer_status="pending",
        created_at=datetime.now(UTC),
    )

    resp = await service.preview(
        "prof_1", actor=SimpleNamespace(), elevation_level="elevated", locale="zh-CN"
    )

    assert resp.coverage is not None
    assert resp.coverage["source_highlights"] == 2
    # The配置中心 highlight has no counterpart in the draft, so it must be named.
    assert [d["text"] for d in resp.coverage["dropped"]] == [
        "搭建统一配置中心，覆盖 120 多个服务"
    ]
    assert resp.diagnostics is not None
    assert resp.diagnostics["bullet_count"] == 1
    # A one-bullet document is thin, and the estimate never reports a bare 0 pages.
    assert resp.diagnostics["estimated_pages"] >= 0.1
    assert any("偏薄" in note for note in resp.diagnostics["notes"])


@pytest.mark.asyncio
async def test_invariant_findings_are_appended_as_advice_not_as_a_blocker() -> None:
    """A deterministic check must never be able to lock a user out of their document.

    The reviewer stays the gate. This layer only adds what arithmetic can prove — a
    number with no support anywhere in the profile — and it arrives as `warning`, because
    legitimate writing (merging two highlights) breaks attribution and would otherwise
    produce a hard block on correct output.
    """
    from jc.services.resume_service import ResumeService

    source_profile = {
        "experiences": [
            {
                "id": "exp_1",
                "company": "某公司",
                "title": "后端工程师",
                "start_date": "2020-01",
                "highlights": ["负责订单服务拆分，拆成微服务"],
            }
        ]
    }
    sections = {
        "experience_blocks": [
            {"bullets": ["负责订单服务拆分为微服务，发布耗时下降 70%"]}
        ]
    }

    issues = ResumeService._with_invariant_issues([], sections, source_profile)

    assert len(issues) == 1
    assert issues[0]["severity"] == "warning"
    assert issues[0]["code"] == "invariant_unsupported_number"
    assert issues[0]["field"] == "experience_blocks[0].bullets[0]"
    assert "70%" in issues[0]["message"]


@pytest.mark.asyncio
async def test_the_reviewer_keeps_the_field_when_it_already_named_the_defect() -> None:
    """Reading the same problem twice in different words reads like two problems."""
    from jc.services.resume_service import ResumeService

    source_profile = {
        "experiences": [
            {
                "id": "exp_1",
                "company": "某公司",
                "title": "后端工程师",
                "start_date": "2020-01",
                "highlights": ["负责订单服务拆分，拆成微服务"],
            }
        ]
    }
    sections = {
        "experience_blocks": [
            {"bullets": ["负责订单服务拆分为微服务，发布耗时下降 70%"]}
        ]
    }
    reviewer_issues = [
        {
            "severity": "error",
            "field": "experience_blocks[0].bullets[0]",
            "message": "`70%` 在档案里没有依据。",
        }
    ]

    issues = ResumeService._with_invariant_issues(
        reviewer_issues, sections, source_profile
    )

    assert issues == reviewer_issues


@pytest.mark.asyncio
async def test_honest_writing_adds_no_issues() -> None:
    """The baseline: if rewriting triggered findings, every export would show noise."""
    from jc.services.resume_service import ResumeService

    source_profile = {
        "experiences": [
            {
                "id": "exp_1",
                "company": "某公司",
                "title": "后端工程师",
                "start_date": "2020-01",
                "highlights": ["负责订单服务拆分，发布耗时从 40 分钟降到 6 分钟"],
            }
        ]
    }
    sections = {
        "experience_blocks": [
            {"bullets": ["负责订单服务拆分，把发布耗时从 40 分钟压缩到 6 分钟"]}
        ]
    }

    assert ResumeService._with_invariant_issues([], sections, source_profile) == []


@pytest.mark.asyncio
async def test_a_malformed_source_payload_does_not_break_the_export_review() -> None:
    """The reviewer already reports a missing/broken profile. This layer must not turn
    that into a 500 on the download screen."""
    from jc.services.resume_service import ResumeService

    sections = {"experience_blocks": [{"bullets": ["负责订单服务拆分"]}]}
    assert ResumeService._with_invariant_issues([], sections, None) == []
    assert (
        ResumeService._with_invariant_issues([], sections, {"experiences": "broken"})
        == []
    )


def test_export_review_says_what_the_file_is_before_it_reaches_an_employer() -> None:
    """Two defects about how the document was produced, not about how it reads.

    `source_layout` means the writer chain failed and this is the profile's own wording
    laid out — the preview panel said so, the export screen read no such field, so a
    failed optimization downloaded under the same filename as a successful one. That is
    what makes "优化效果不好" indistinguishable from "优化根本没发生".

    `（待补充经历要点）` is written by our own builder, so the reviewer's placeholder rule
    — which reads the draft as model output — never sees it, and it printed straight into
    the delivered PDF.

    Both advisory, like every other deterministic finding here: a structural judgement
    must not withhold the user's own file. What changed is that the export screen can no
    longer be silent about it.
    """
    from jc.services.resume_service import ResumeService

    sections = {
        "generation": {"mode": "source_layout", "warning": "AI 写作未完成，当前显示档案原文排版；"},
        "experience_blocks": [
            {"id": "e1", "bullets": ["负责订单服务拆分"]},
            {"id": "e2", "bullets": ["（待补充经历要点）"]},
        ],
        "project_blocks": [{"id": "p1", "bullets": ["(Add experience highlights)"]}],
    }
    issues = ResumeService._with_delivery_issues([], sections)
    assert all(i["severity"] == "warning" for i in issues)

    not_optimized = [i for i in issues if i["code"] == "generation_not_optimized"]
    assert len(not_optimized) == 1
    assert "AI 写作未完成" in not_optimized[0]["message"]
    assert "重新生成" in not_optimized[0]["message"]

    assert [i["field"] for i in issues if i["code"] == "placeholder_bullet"] == [
        "experience_blocks[1].bullets[0]", "project_blocks[0].bullets[0]"
    ]
    # A normally generated draft says nothing at all.
    assert ResumeService._with_delivery_issues([], {"experience_blocks": []}) == []


def _draft_response_stub(d, sections=None):
    from datetime import UTC, datetime

    from jc.schemas.resume import ResumeDraftResponse

    return ResumeDraftResponse(
        id=d.id,
        profile_id=d.profile_id,
        profile_version=1,
        elevation_level="elevated",
        locale=d.locale,
        template_id=d.template_id,
        sections=d.sections if sections is None else sections,
        elevation_map=[],
        reviewer_status="pending",
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_preview_regenerates_when_the_framing_angle_changed() -> None:
    """Changing angles in `WritingOptionsPanel` saves to the profile and asks the
    frontend to reload the preview -- but a GET that only checked `template_id` kept
    serving the old draft, so switching angles visibly did nothing.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from jc.schemas.profile_payload import ProfilePayload, ProfilePreferences
    from jc.services.resume_service import JobHints, ResumeService

    # Resolved role family for an empty `ProfilePayload` with no overrides/hints is
    # "general" (see `resolve_role_family`); the stamp below is deliberately wrong
    # for *that*, to isolate this test to the emphases changing.
    stale_draft = SimpleNamespace(
        id="rdft_old",
        profile_id="prof_1",
        profile_version=1,
        locale="zh-CN",
        template_id="zh-one-page",
        job_id=None,
        sections={
            "header": {},
            "role_family": "general",
            "framing_emphases": ["collaboration"],
        },
        elevation_map=[],
    )
    fresh_draft = SimpleNamespace(
        id="rdft_new",
        profile_id="prof_1",
        profile_version=1,
        locale="zh-CN",
        template_id="zh-one-page",
        job_id=None,
        sections={
            "header": {},
            "role_family": "general",
            "framing_emphases": ["ownership"],
        },
        elevation_map=[],
    )

    service = object.__new__(ResumeService)
    service._db = SimpleNamespace()
    # The user switched the angle to "ownership" after the stale draft was written.
    payload = ProfilePayload(preferences=ProfilePreferences(framing_emphases=["ownership"]))
    service._profiles = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(payload=payload, version=1))
    )
    service._job_hints = AsyncMock(return_value=JobHints())
    service._resumes = SimpleNamespace(
        get_latest_draft=AsyncMock(return_value=stale_draft),
        get_draft_by_id=AsyncMock(return_value=fresh_draft),
    )
    service._renderer = SimpleNamespace(render_html=lambda *_a, **_k: "<html></html>")
    service._normalize_sections = lambda s, _p, locale=None: s
    service.elevate = AsyncMock(return_value=SimpleNamespace(id="rdft_new"))
    service._to_draft_response = _draft_response_stub

    resp = await service.preview(
        "prof_1", actor=SimpleNamespace(), elevation_level="elevated", locale="zh-CN"
    )

    service.elevate.assert_awaited_once()
    assert resp.draft.id == "rdft_new"


@pytest.mark.asyncio
async def test_preview_reuses_the_draft_when_options_are_unchanged() -> None:
    """The common case -- re-opening the page without touching any setting -- must
    not pay for a fresh model call on every load."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from jc.schemas.profile_payload import ProfilePayload, ProfilePreferences
    from jc.services.resume_service import JobHints, ResumeService

    draft = SimpleNamespace(
        id="rdft_same",
        profile_id="prof_1",
        profile_version=1,
        locale="zh-CN",
        template_id="zh-one-page",
        job_id=None,
        sections={
            "header": {},
            "role_family": "general",
            "framing_emphases": ["ownership"],
        },
        elevation_map=[],
    )

    service = object.__new__(ResumeService)
    service._db = SimpleNamespace()
    payload = ProfilePayload(preferences=ProfilePreferences(framing_emphases=["ownership"]))
    service._profiles = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(payload=payload, version=1))
    )
    service._job_hints = AsyncMock(return_value=JobHints())
    service._resumes = SimpleNamespace(get_latest_draft=AsyncMock(return_value=draft))
    service._renderer = SimpleNamespace(render_html=lambda *_a, **_k: "<html></html>")
    service._normalize_sections = lambda s, _p, locale=None: s
    service.elevate = AsyncMock()
    service._to_draft_response = _draft_response_stub

    resp = await service.preview(
        "prof_1", actor=SimpleNamespace(), elevation_level="elevated", locale="zh-CN"
    )

    service.elevate.assert_not_awaited()
    assert resp.draft.id == "rdft_same"


@pytest.mark.asyncio
async def test_preview_does_not_regenerate_a_draft_predating_the_stamp() -> None:
    """A draft written before `role_family`/`framing_emphases` were stamped on
    `sections` has neither key. Treat it as fresh rather than forcing every resume
    ever written before this check shipped to regenerate on its next view."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from jc.schemas.profile_payload import ProfilePayload
    from jc.services.resume_service import JobHints, ResumeService

    draft = SimpleNamespace(
        id="rdft_legacy",
        profile_id="prof_1",
        profile_version=1,
        locale="zh-CN",
        template_id="zh-one-page",
        job_id=None,
        sections={"header": {}},
        elevation_map=[],
    )

    service = object.__new__(ResumeService)
    service._db = SimpleNamespace()
    service._profiles = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(payload=ProfilePayload(), version=1))
    )
    service._job_hints = AsyncMock(return_value=JobHints())
    service._resumes = SimpleNamespace(get_latest_draft=AsyncMock(return_value=draft))
    service._renderer = SimpleNamespace(render_html=lambda *_a, **_k: "<html></html>")
    service._normalize_sections = lambda s, _p, locale=None: s
    service.elevate = AsyncMock()
    service._to_draft_response = _draft_response_stub

    resp = await service.preview(
        "prof_1", actor=SimpleNamespace(), elevation_level="elevated", locale="zh-CN"
    )

    service.elevate.assert_not_awaited()
    assert resp.draft.id == "rdft_legacy"

@pytest.mark.asyncio
async def test_old_profile_version_invalidates_even_a_legacy_unstamped_draft():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from jc.schemas.profile_payload import ProfilePayload
    from jc.services.resume_service import ResumeService

    service = object.__new__(ResumeService)
    service._db = SimpleNamespace()
    service._profiles = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(payload=ProfilePayload(), version=26))
    )
    service._job_hints = AsyncMock()
    draft = SimpleNamespace(profile_version=25, sections={})
    assert await service._is_stale_for_profile(draft, profile_id="p", actor=SimpleNamespace())
    service._job_hints.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_has_total_deadline_and_reports_no_verdict_not_failure(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from jc.config import settings
    from jc.services.resume_service import ResumeService

    monkeypatch.setattr(settings, "jc_export_review_timeout_seconds", 0.01)
    cancelled = False

    async def slow_review(**kwargs):
        nonlocal cancelled
        try:
            await asyncio.sleep(10)
        finally:
            cancelled = True

    source = {"contact": {}, "experiences": []}
    monkeypatch.setattr("jc.stores.profile_store.ProfileStore", lambda _db: SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(payload=source))
    ))
    service = object.__new__(ResumeService)
    service._db = SimpleNamespace()
    service._db = SimpleNamespace(rollback=AsyncMock())
    service._reviewer = SimpleNamespace(review=slow_review)
    draft = SimpleNamespace(id="draft", profile_id="p", locale="zh-CN", sections={})
    result = await asyncio.wait_for(service._review_draft(draft), timeout=1)
    assert cancelled
    assert result["status"] == "unavailable" and result["reviewed"] is False
    assert result["can_export"] is True
    assert any(i["code"] == "reviewer_timeout" for i in result["issues"])
    service._db.rollback.assert_awaited_once()
