"""Headshot pipeline: normalisation guards, the display switch, and render inlining.

These cover the parts that are only wrong once it is too late to notice — a photo
that prints sideways, a toggle that destroys the upload, an export that renders a
blank box where the face should be. Each one had been verified by hand during
development; this file is what keeps them verified.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agentkit.web.auth import UserActor
from PIL import Image

from jc.models.profile import Profile
from jc.schemas.profile_payload import ProfilePayload, ProfilePhoto
from jc.services import profile_photo_service as photo_svc
from jc.services.profile_photo_service import (
    MAX_EDGE_PX,
    PhotoRejectedError,
    _normalise_image,
    photo_data_uri,
    resign_photo,
)
from jc.services.profile_service import ProfileService


def _jpeg(width: int, height: int, colour: str = "red") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="JPEG")
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# _normalise_image
# --------------------------------------------------------------------------- #


def test_normalise_keeps_small_image_dimensions() -> None:
    raw, width, height = _normalise_image(_jpeg(800, 1000))
    assert (width, height) == (800, 1000)
    assert Image.open(io.BytesIO(raw)).format == "JPEG"


def test_normalise_bounds_the_longest_edge() -> None:
    """A phone photo must come back inside the print ceiling, aspect intact."""
    _, width, height = _normalise_image(_jpeg(4000, 3000))
    assert max(width, height) == MAX_EDGE_PX
    assert width / height == pytest.approx(4000 / 3000, rel=1e-3)


def test_normalise_flattens_alpha_onto_white() -> None:
    """JPEG has no alpha. White, not black: it matches the printed page."""
    buffer = io.BytesIO()
    Image.new("RGBA", (120, 150), (0, 0, 0, 0)).save(buffer, format="PNG")

    raw, _, _ = _normalise_image(buffer.getvalue())

    out = Image.open(io.BytesIO(raw))
    assert out.mode == "RGB"
    assert out.getpixel((5, 5)) == (255, 255, 255)


def test_normalise_applies_exif_orientation_and_drops_the_tag() -> None:
    """The single most common headshot complaint: a portrait that prints sideways.

    Orientation 6 means "rotate 90° CW to display". A renderer that ignores EXIF —
    which is most PDF and DOCX paths — would draw the stored pixels as-is, so the
    rotation has to be baked in here and the tag removed so nothing rotates twice.
    """
    buffer = io.BytesIO()
    image = Image.new("RGB", (900, 600), "blue")
    exif = image.getexif()
    exif[274] = 6
    image.save(buffer, format="JPEG", exif=exif)

    raw, width, height = _normalise_image(buffer.getvalue())

    assert (width, height) == (600, 900), "orientation was not applied"
    assert Image.open(io.BytesIO(raw)).getexif().get(274) in (None, 1)


def test_normalise_rejects_unsupported_format() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100), "green").save(buffer, format="BMP")
    with pytest.raises(PhotoRejectedError):
        _normalise_image(buffer.getvalue())


def test_normalise_rejects_non_image_bytes() -> None:
    with pytest.raises(PhotoRejectedError):
        _normalise_image(b"this is not an image at all")


def test_normalise_rejects_a_decompression_bomb() -> None:
    """Refused from the *declared* size, before any pixels are allocated.

    A few hundred KB of uniform PNG declares 144 megapixels. Decoding it first to
    find out how big it is would be the denial of service.
    """
    buffer = io.BytesIO()
    Image.new("RGB", (12_000, 12_000), "white").save(buffer, format="PNG")
    payload = buffer.getvalue()

    with pytest.raises(PhotoRejectedError) as excinfo:
        _normalise_image(payload)
    assert "分辨率" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# renderable / data URI
# --------------------------------------------------------------------------- #


def test_photo_defaults_to_not_rendered() -> None:
    """Uploading must never silently change an export. Off is the default."""
    photo = ProfilePayload.model_validate({}).contact.photo
    assert photo.enabled is False
    assert photo.renderable is False


@pytest.mark.parametrize(
    ("enabled", "key", "expected"),
    [(True, "k", True), (False, "k", False), (True, None, False), (False, None, False)],
)
def test_renderable_requires_both_switch_and_upload(
    enabled: bool, key: str | None, expected: bool
) -> None:
    assert ProfilePhoto(enabled=enabled, storage_key=key).renderable is expected


# --------------------------------------------------------------------------- #
# locale rule
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("locale", ["en-US", "en", "EN_us", "en-GB"])
def test_the_english_track_never_renders_a_headshot(locale: str) -> None:
    """Not a preference — a hard rule.

    US / UK / EU screening guidance commonly instructs recruiters to discard or
    redact a resume carrying a photo, to limit bias exposure. A user who turned the
    photo on for their Chinese resume and then exports English would otherwise ship
    the one thing that gets the application binned, which is why no flag overrides
    this.
    """
    photo = ProfilePhoto(storage_key="k", enabled=True, show_in_bilingual=True)
    assert photo.renders_for_locale(locale) is False


def test_the_chinese_track_follows_the_users_switch() -> None:
    assert ProfilePhoto(storage_key="k", enabled=True).renders_for_locale("zh-CN") is True
    assert ProfilePhoto(storage_key="k", enabled=False).renders_for_locale("zh-CN") is False


def test_the_bilingual_track_is_opt_in() -> None:
    """A bilingual document exists because someone English-reading will read it, so
    inheriting the Chinese switch would export a photo abroad by accident."""
    on_for_chinese = ProfilePhoto(storage_key="k", enabled=True)
    assert on_for_chinese.show_in_bilingual is False
    assert on_for_chinese.renders_for_locale("zh-en") is False
    assert on_for_chinese.model_copy(update={"show_in_bilingual": True}).renders_for_locale(
        "zh-en"
    ) is True


def test_bilingual_opt_in_still_needs_the_photo_switched_on() -> None:
    """`show_in_bilingual` widens where a shown photo appears; it is not a second
    way to turn the photo on."""
    photo = ProfilePhoto(storage_key="k", enabled=False, show_in_bilingual=True)
    assert photo.renders_for_locale("zh-en") is False


def test_an_unknown_locale_is_treated_as_chinese() -> None:
    """`normalize_track` defaults to zh-CN, and the whole product is Chinese-first;
    a typo'd track must not quietly change what the resume looks like."""
    photo = ProfilePhoto(storage_key="k", enabled=True)
    assert photo.renders_for_locale(None) is True
    assert photo.renders_for_locale("zh-Hans") is True


def test_draft_builder_drops_the_photo_on_the_english_track(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rule has to hold at the only place the export reads it, not just on the
    model: this is what keeps PDF, DOCX and HTML from drifting apart."""
    from jc.services import resume_draft_builder as builder_mod

    monkeypatch.setattr(
        photo_svc,
        "get_storage_backend",
        lambda: SimpleNamespace(get_object_bytes=lambda key: b"\xff\xd8\xff\xd9"),
    )
    payload = ProfilePayload.model_validate({"contact": {"name": "测试"}})
    payload.contact.photo = ProfilePhoto(
        storage_key="k", enabled=True, mime_type="image/jpeg"
    )

    zh, _ = builder_mod.ResumeDraftBuilder().build(
        payload, elevation_level="verified", locale="zh-CN"
    )
    en, _ = builder_mod.ResumeDraftBuilder().build(
        payload, elevation_level="verified", locale="en-US"
    )
    bilingual, _ = builder_mod.ResumeDraftBuilder().build(
        payload, elevation_level="verified", locale="zh-en"
    )

    assert zh["header"].get("photo_data_uri", "").startswith("data:image/jpeg;base64,")
    assert "photo_data_uri" not in en["header"]
    assert "photo_data_uri" not in bilingual["header"]


def test_photo_data_uri_inlines_the_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exports must inline, not link.

    `ResumeRenderEngine.render_pdf` aborts every request from the print page, so a
    remote `<img src>` renders as an empty box. The HTML export separately promises
    to be a self-contained single file.
    """
    monkeypatch.setattr(
        photo_svc,
        "get_storage_backend",
        lambda: SimpleNamespace(get_object_bytes=lambda key: b"\xff\xd8\xff\xd9"),
    )
    uri = photo_data_uri(
        ProfilePhoto(storage_key="k", enabled=True, mime_type="image/jpeg"), locale="zh-CN"
    )
    assert uri is not None and uri.startswith("data:image/jpeg;base64,")


def test_photo_data_uri_is_none_when_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        photo_svc,
        "get_storage_backend",
        lambda: SimpleNamespace(get_object_bytes=lambda key: b"bytes"),
    )
    assert photo_data_uri(ProfilePhoto(storage_key="k", enabled=False)) is None


def test_photo_data_uri_swallows_storage_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A decorative element must never fail an export the user is waiting on."""

    def explode(key: str) -> bytes:
        raise RuntimeError("storage down")

    monkeypatch.setattr(
        photo_svc,
        "get_storage_backend",
        lambda: SimpleNamespace(get_object_bytes=explode),
    )
    assert photo_data_uri(ProfilePhoto(storage_key="k", enabled=True)) is None


def test_resign_replaces_the_persisted_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stored URL is always treated as expired; the key is the durable record."""
    monkeypatch.setattr(photo_svc, "download_url_for_key", lambda key: f"https://signed/{key}")
    resigned = resign_photo(ProfilePhoto(storage_key="k", download_url="https://stale/old"))
    assert resigned is not None
    assert resigned.download_url == "https://signed/k"


def test_resign_tolerates_a_signing_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(key: str) -> str:
        raise RuntimeError("no credentials")

    monkeypatch.setattr(photo_svc, "download_url_for_key", explode)
    resigned = resign_photo(ProfilePhoto(storage_key="k"))
    assert resigned is not None
    assert resigned.download_url is None
    assert resigned.storage_key == "k"


# --------------------------------------------------------------------------- #
# ProfileService: the switch
# --------------------------------------------------------------------------- #


def _service(profile: Profile) -> ProfileService:
    service = object.__new__(ProfileService)
    service._profiles = SimpleNamespace(get_by_id=AsyncMock(return_value=profile))
    service._db = SimpleNamespace(commit=AsyncMock())
    return service


def _profile_with_photo(*, enabled: bool, key: str | None = "profiles/p/photo.jpg") -> Profile:
    payload = ProfilePayload.model_validate({"contact": {"name": "测试"}})
    payload.contact.photo = ProfilePhoto(storage_key=key, enabled=enabled)
    # `status` / `created_at` / `updated_at` are set explicitly: these columns get
    # their values from the DB on a real insert, and `_to_response` validates them.
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return Profile(
        id="prof_photo",
        user_id="usr_a",
        guest_session_id=None,
        status="draft",
        locale="zh-CN",
        version=4,
        payload=payload.model_dump(mode="json"),
        sources=[],
        created_at=now,
        updated_at=now,
    )


ACTOR = UserActor(user_id="usr_a", session_id="sess_x")


@pytest.mark.asyncio
async def test_toggle_off_keeps_the_upload() -> None:
    """Hiding the photo must not destroy it — the user may re-enable it at once."""
    profile = _profile_with_photo(enabled=True)
    service = _service(profile)

    await service.set_photo_enabled("prof_photo", actor=ACTOR, enabled=False)

    photo = ProfilePayload.model_validate(profile.payload).contact.photo
    assert photo.enabled is False
    assert photo.storage_key == "profiles/p/photo.jpg"
    assert profile.version == 5


@pytest.mark.asyncio
async def test_toggle_to_the_same_state_is_a_no_op() -> None:
    """A double-clicked switch must not manufacture snapshot history."""
    profile = _profile_with_photo(enabled=True)
    service = _service(profile)

    await service.set_photo_enabled("prof_photo", actor=ACTOR, enabled=True)

    assert profile.version == 4
    service._db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_enabling_without_an_upload_is_rejected() -> None:
    from jc.exceptions import NotFoundError

    profile = _profile_with_photo(enabled=False, key=None)
    service = _service(profile)

    with pytest.raises(NotFoundError) as excinfo:
        await service.set_photo_enabled("prof_photo", actor=ACTOR, enabled=True)

    assert excinfo.value.code == "photo_not_uploaded"
    assert profile.version == 4


@pytest.mark.asyncio
async def test_delete_clears_the_payload_but_not_the_object() -> None:
    """Version history can roll back to a payload referencing this key.

    A restore that produced a broken image would be worse than an orphaned object,
    so object lifecycle stays a storage-retention concern.
    """
    profile = _profile_with_photo(enabled=True)
    service = _service(profile)
    deleted: list[str] = []
    service._storage = SimpleNamespace(delete_object=deleted.append)

    await service.delete_photo("prof_photo", actor=ACTOR)

    photo = ProfilePayload.model_validate(profile.payload).contact.photo
    assert photo.storage_key is None
    assert photo.enabled is False
    assert deleted == []
    assert profile.version == 5


@pytest.mark.asyncio
async def test_delete_without_a_photo_does_not_bump_the_version() -> None:
    profile = _profile_with_photo(enabled=False, key=None)
    service = _service(profile)

    await service.delete_photo("prof_photo", actor=ACTOR)

    assert profile.version == 4
    service._db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejected_upload_leaves_no_version_bump(monkeypatch: pytest.MonkeyPatch) -> None:
    """Normalisation runs before the transaction, so a bad file changes nothing."""
    profile = _profile_with_photo(enabled=False, key=None)
    service = _service(profile)

    with pytest.raises(PhotoRejectedError):
        await service.set_photo(
            "prof_photo", actor=ACTOR, raw=b"definitely not an image", enabled=True
        )

    assert profile.version == 4
    service._db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_photo_stores_and_enables(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = _profile_with_photo(enabled=False, key=None)
    service = _service(profile)
    stored: dict[str, bytes] = {}

    monkeypatch.setattr(
        photo_svc,
        "get_storage_backend",
        lambda: SimpleNamespace(
            put_object=lambda key, body, content_type=None: stored.__setitem__(key, body)
        ),
    )
    monkeypatch.setattr(photo_svc, "download_url_for_key", lambda key: f"https://signed/{key}")

    await service.set_photo("prof_photo", actor=ACTOR, raw=_jpeg(600, 750), enabled=True)

    photo = ProfilePayload.model_validate(profile.payload).contact.photo
    assert photo.enabled is True
    assert photo.storage_key in stored
    assert photo.mime_type == "image/jpeg"
    assert (photo.width, photo.height) == (600, 750)
    assert profile.version == 5
    # Re-encoded on the way in: a JPEG comes back out, whatever arrived.
    assert Image.open(io.BytesIO(stored[photo.storage_key])).format == "JPEG"


@pytest.mark.asyncio
async def test_set_photo_can_store_without_showing(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = _profile_with_photo(enabled=False, key=None)
    service = _service(profile)
    monkeypatch.setattr(
        photo_svc,
        "get_storage_backend",
        lambda: SimpleNamespace(put_object=lambda key, body, content_type=None: None),
    )
    monkeypatch.setattr(photo_svc, "download_url_for_key", lambda key: None)

    await service.set_photo("prof_photo", actor=ACTOR, raw=_jpeg(300, 375), enabled=False)

    photo = ProfilePayload.model_validate(profile.payload).contact.photo
    assert photo.storage_key is not None
    assert photo.enabled is False
    assert photo.renderable is False


@pytest.mark.asyncio
async def test_photo_actions_reject_a_different_owner() -> None:
    from jc.exceptions import ForbiddenError

    profile = _profile_with_photo(enabled=True)
    service = _service(profile)
    intruder = UserActor(user_id="usr_b", session_id="sess_y")

    for call in (
        service.set_photo_enabled("prof_photo", actor=intruder, enabled=False),
        service.delete_photo("prof_photo", actor=intruder),
    ):
        with pytest.raises(ForbiddenError):
            await call

    assert profile.version == 4


# --------------------------------------------------------------------------- #
# i18n overlay
# --------------------------------------------------------------------------- #


def test_i18n_overlay_preserves_the_photo() -> None:
    """`overlay_profile` round-trips through `model_dump`, so a field it does not
    know about could silently vanish. The English export reads the photo *after*
    the overlay runs, so losing it here would drop the headshot from one locale
    only — the kind of bug that only shows up in the finished PDF."""
    from jc.services.profile_i18n import overlay_profile

    payload = ProfilePayload.model_validate(
        {
            "contact": {"name": "测试"},
            "i18n": {"en-US": {"summary": "An English summary."}},
        }
    )
    payload.contact.photo = ProfilePhoto(
        storage_key="profiles/p/photo.jpg", enabled=True, mime_type="image/jpeg"
    )

    overlaid = overlay_profile(payload, "en-US")

    assert overlaid.summary == "An English summary."
    assert overlaid.contact.photo.storage_key == "profiles/p/photo.jpg"
    assert overlaid.contact.photo.renderable is True


# --------------------------------------------------------------------------- #
# templates
# --------------------------------------------------------------------------- #


def test_masthead_omits_the_photo_when_absent() -> None:
    """No photo means byte-identical output to before the feature existed."""
    from jc.services.resume_render_engine import ResumeRenderEngine

    html = ResumeRenderEngine().render_html(
        {"header": {"name": "张三", "contact_line": "a@b.c"}},
        template_id="zh-one-page",
    )
    # The class names always appear in the stylesheet; what matters is the element.
    assert '<header class="masthead">' in html
    assert "<img" not in html


def test_masthead_renders_an_inlined_photo() -> None:
    from jc.services.resume_render_engine import ResumeRenderEngine

    html = ResumeRenderEngine().render_html(
        {
            "header": {
                "name": "张三",
                "contact_line": "a@b.c",
                "photo_data_uri": "data:image/jpeg;base64,AAAA",
            }
        },
        template_id="zh-one-page",
    )
    assert '<header class="masthead masthead--with-photo">' in html
    assert 'src="data:image/jpeg;base64,AAAA"' in html
    # Empty alt: the name is adjacent, so announcing it repeats the identity.
    assert 'alt=""' in html


# --------------------------------------------------------------------------- #
# DOCX
# --------------------------------------------------------------------------- #


def _docx_media(blob: bytes) -> list[str]:
    import zipfile

    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return [name for name in archive.namelist() if name.startswith("word/media/")]


def test_docx_embeds_the_photo() -> None:
    from jc.services.resume_render_engine import ResumeRenderEngine

    buffer = io.BytesIO()
    Image.new("RGB", (300, 375), "red").save(buffer, format="JPEG")
    import base64

    uri = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()

    blob = ResumeRenderEngine().render_docx(
        {"header": {"name": "张三", "photo_data_uri": uri}, "locale": "zh-CN"}
    )

    assert _docx_media(blob), "no image was embedded in the docx"


def test_docx_without_a_photo_embeds_nothing() -> None:
    from jc.services.resume_render_engine import ResumeRenderEngine

    blob = ResumeRenderEngine().render_docx({"header": {"name": "张三"}, "locale": "zh-CN"})
    assert _docx_media(blob) == []


def test_docx_survives_a_malformed_data_uri() -> None:
    """A broken photo must not cost the user their download."""
    from jc.services.resume_render_engine import ResumeRenderEngine

    blob = ResumeRenderEngine().render_docx(
        {"header": {"name": "张三", "photo_data_uri": "data:image/jpeg;base64,!!!not-b64"}},
    )
    assert _docx_media(blob) == []
    assert len(blob) > 0


def _zh_sections_with_photo() -> dict[str, object]:
    """A Chinese-track draft that legitimately carries a headshot."""
    return {
        "header": {"name": "张三", "photo_data_uri": "data:image/jpeg;base64,AAAA"},
        "summary": "摘要",
        "experience_blocks": [],
        "education_blocks": [],
        "skills_block": {},
    }


def test_bilingual_strips_the_photo_when_the_opt_in_is_off() -> None:
    """The bilingual wrapper is assembled from the zh draft, which is allowed to carry
    a photo — so without an explicit strip the opt-out silently published it."""
    from jc.services.resume_service import compose_bilingual_sections

    sections = compose_bilingual_sections(
        _zh_sections_with_photo(),
        {"header": {"name": "Zhang San"}},
        zh_draft_id="rdft_zh",
        en_draft_id="rdft_en",
        show_photo=False,
    )

    assert "photo_data_uri" not in sections["header"]
    # The template renders the nested half, not the flattened copy, so both have to
    # be clean for the photo to actually be absent from the page.
    assert "photo_data_uri" not in sections["zh_sections"]["header"]


def test_bilingual_keeps_the_photo_when_opted_in() -> None:
    from jc.services.resume_service import compose_bilingual_sections

    sections = compose_bilingual_sections(
        _zh_sections_with_photo(),
        {"header": {"name": "Zhang San"}},
        zh_draft_id="rdft_zh",
        en_draft_id="rdft_en",
        show_photo=True,
    )

    assert sections["header"]["photo_data_uri"].startswith("data:image/jpeg")
    assert sections["zh_sections"]["header"]["photo_data_uri"].startswith("data:image/jpeg")


def test_bilingual_strip_does_not_mutate_the_source_draft() -> None:
    """The zh draft is a persisted row's `sections`; stripping the wrapper's copy must
    not remove the photo from the Chinese resume it was built for."""
    from jc.services.resume_service import compose_bilingual_sections

    zh = _zh_sections_with_photo()
    compose_bilingual_sections(
        zh,
        {"header": {"name": "Zhang San"}},
        zh_draft_id="rdft_zh",
        en_draft_id="rdft_en",
        show_photo=False,
    )

    assert zh["header"]["photo_data_uri"].startswith("data:image/jpeg")


def test_bilingual_default_is_no_photo() -> None:
    """`show_photo` defaults off so a caller that forgets to pass the opt-in leaks
    nothing — the failure mode of the default has to be the private one."""
    from jc.services.resume_service import compose_bilingual_sections

    sections = compose_bilingual_sections(
        _zh_sections_with_photo(),
        {"header": {"name": "Zhang San"}},
        zh_draft_id="rdft_zh",
        en_draft_id="rdft_en",
    )

    assert "photo_data_uri" not in sections["header"]


# --------------------------------------------------------------------------- #
# Render-time resolution: preview and export must agree
# --------------------------------------------------------------------------- #


def test_set_header_photo_removes_an_inherited_uri() -> None:
    """A draft generated while the switch was on keeps the key forever, so "no photo"
    has to be something the render step can assert, not just decline to add."""
    from jc.services.profile_photo_service import set_header_photo

    out = set_header_photo(_zh_sections_with_photo(), None)

    assert "photo_data_uri" not in out["header"]


def test_set_header_photo_does_not_mutate_the_input() -> None:
    from jc.services.profile_photo_service import set_header_photo

    stored = _zh_sections_with_photo()
    set_header_photo(stored, None)

    assert stored["header"]["photo_data_uri"].startswith("data:image/jpeg")


def test_set_header_photo_tolerates_a_missing_header() -> None:
    from jc.services.profile_photo_service import set_header_photo

    out = set_header_photo({"summary": "x"}, "data:image/jpeg;base64,AAAA")

    assert out["header"]["photo_data_uri"] == "data:image/jpeg;base64,AAAA"


def _photo_profile(enabled: bool, *, bilingual: bool = False) -> ProfilePayload:
    return ProfilePayload.model_validate(
        {
            "contact": {
                "name": "张三",
                "photo": {
                    "storage_key": "k",
                    "mime_type": "image/jpeg",
                    "enabled": enabled,
                    "show_in_bilingual": bilingual,
                },
            },
            "experiences": [],
            "educations": [],
        }
    )


def _service_with_photo_bytes(monkeypatch: pytest.MonkeyPatch) -> object:
    """A `ResumeService` whose storage returns real JPEG bytes, DB untouched.

    `_with_live_photo` is pure apart from the storage read, so constructing the
    service with a sentinel session is enough to exercise it.
    """
    from jc.services.resume_service import ResumeService

    monkeypatch.setattr(
        photo_svc,
        "get_storage_backend",
        lambda: SimpleNamespace(get_object_bytes=lambda key: _jpeg(80, 100)),
    )
    return ResumeService.__new__(ResumeService)


def test_live_photo_adds_the_headshot_for_the_chinese_track(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The preview used to rebuild the header from a text whitelist and drop the
    photo, so the switch looked broken until the user downloaded the file."""
    service = _service_with_photo_bytes(monkeypatch)

    out = service._with_live_photo(  # noqa: SLF001
        {"header": {"name": "张三"}}, _photo_profile(True), locale="zh-CN"
    )

    assert out["header"]["photo_data_uri"].startswith("data:image/jpeg;base64,")


def test_live_photo_removes_a_stale_headshot_when_switched_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drafts are snapshots: turning the switch off has to take effect on the next
    render rather than waiting for a regeneration."""
    service = _service_with_photo_bytes(monkeypatch)

    out = service._with_live_photo(  # noqa: SLF001
        _zh_sections_with_photo(), _photo_profile(False), locale="zh-CN"
    )

    assert "photo_data_uri" not in out["header"]


def test_live_photo_never_draws_on_the_english_track(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service_with_photo_bytes(monkeypatch)

    out = service._with_live_photo(  # noqa: SLF001
        _zh_sections_with_photo(), _photo_profile(True), locale="en-US"
    )

    assert "photo_data_uri" not in out["header"]


def test_live_photo_writes_both_bilingual_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`render_html` renders `zh_sections`, not the flattened copy, so writing only
    one of the two leaves the page unchanged."""
    from jc.services.resume_service import compose_bilingual_sections

    service = _service_with_photo_bytes(monkeypatch)
    wrapper = compose_bilingual_sections(
        _zh_sections_with_photo(),
        {"header": {"name": "Zhang San"}},
        zh_draft_id="rdft_zh",
        en_draft_id="rdft_en",
        show_photo=False,
    )

    out = service._with_live_photo(  # noqa: SLF001
        wrapper, _photo_profile(True, bilingual=True), locale="zh-en"
    )

    assert out["header"]["photo_data_uri"].startswith("data:image/jpeg")
    assert out["zh_sections"]["header"]["photo_data_uri"].startswith("data:image/jpeg")


def test_live_photo_keeps_bilingual_private_without_the_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jc.services.resume_service import compose_bilingual_sections

    service = _service_with_photo_bytes(monkeypatch)
    wrapper = compose_bilingual_sections(
        _zh_sections_with_photo(),
        {"header": {"name": "Zhang San"}},
        zh_draft_id="rdft_zh",
        en_draft_id="rdft_en",
        show_photo=True,
    )

    out = service._with_live_photo(  # noqa: SLF001
        wrapper, _photo_profile(True, bilingual=False), locale="zh-en"
    )

    assert "photo_data_uri" not in out["header"]
    assert "photo_data_uri" not in out["zh_sections"]["header"]


def test_live_photo_does_not_mutate_the_stored_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The argument is a persisted row's `sections`; baking a render-time decision
    into it would persist today's switch state."""
    service = _service_with_photo_bytes(monkeypatch)
    stored = {"header": {"name": "张三"}}

    service._with_live_photo(stored, _photo_profile(True), locale="zh-CN")  # noqa: SLF001

    assert "photo_data_uri" not in stored["header"]


def test_export_quality_ignores_the_photo_blob() -> None:
    """The retention check compares expected strings against text extracted from the
    file. A base64 URI can never come back out of a PDF, so counting it as an
    expected field failed every export that carried a headshot."""
    from jc.services.export_quality import expected_text

    values = expected_text(
        {
            "header": {"name": "张三", "photo_data_uri": "data:image/jpeg;base64,AAAA"},
            "summary": "摘要",
        }
    )

    assert "张三" in values
    assert not any(v.startswith("data:") for v in values)
