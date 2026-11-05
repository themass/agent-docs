"""Writing options: presentation levers the user controls directly."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from jc.schemas.profile_payload import (
    ProfileExperience,
    ProfilePayload,
    ProfilePreferences,
)
from jc.schemas.writing_options import WritingOptionsRequest
from jc.services.framing_presets import recommended_for
from jc.services.writing_options_service import WritingOptionsService


def _exp(title: str = "后端工程师") -> ProfileExperience:
    return ProfileExperience(
        id="e1", company="某公司", title=title, start_date="2020-01", highlights=["负责订单服务"]
    )


def _service(payload: ProfilePayload):
    row = SimpleNamespace(payload=payload.model_dump(mode="json"), version=3)
    service = object.__new__(WritingOptionsService)
    service._db = SimpleNamespace(commit=AsyncMock())
    service._profiles = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(id="prof_1", payload=payload, version=3))
    )
    service._store = SimpleNamespace(get_by_id=AsyncMock(return_value=row))
    return service, row


@pytest.mark.asyncio
async def test_defaults_come_from_the_inferred_family_and_are_marked_as_defaults() -> None:
    """The UI must be able to say "推荐" rather than implying the user chose this."""
    payload = ProfilePayload(experiences=[_exp()])
    service, _ = _service(payload)
    resp = await service.get("prof_1", actor=SimpleNamespace())

    assert resp.role_family == "backend"
    assert resp.framing_emphases == recommended_for("backend")
    assert resp.role_family_explicit is False
    assert resp.framing_explicit is False


@pytest.mark.asyncio
async def test_an_explicit_family_is_persisted_and_flagged() -> None:
    payload = ProfilePayload(experiences=[_exp()])
    service, row = _service(payload)
    resp = await service.update(
        "prof_1", actor=SimpleNamespace(), body=WritingOptionsRequest(role_family="pm")
    )

    assert resp.role_family == "pm"
    assert resp.role_family_explicit is True
    assert row.payload["preferences"]["role_family"] == "pm"
    assert row.version == 4


@pytest.mark.asyncio
async def test_switching_family_re_recommends_angles_until_the_user_picks_their_own() -> None:
    payload = ProfilePayload(experiences=[_exp()])
    service, _ = _service(payload)
    resp = await service.update(
        "prof_1", actor=SimpleNamespace(), body=WritingOptionsRequest(role_family="legal")
    )
    assert resp.framing_emphases == recommended_for("legal")
    assert resp.framing_explicit is False


@pytest.mark.asyncio
async def test_a_stale_client_cannot_persist_an_unknown_family() -> None:
    """Ignored rather than rejected: a bad dropdown value must not fail the request."""
    payload = ProfilePayload(
        experiences=[_exp()], preferences=ProfilePreferences(role_family="pm")
    )
    service, row = _service(payload)
    resp = await service.update(
        "prof_1", actor=SimpleNamespace(), body=WritingOptionsRequest(role_family="wat")
    )
    assert resp.role_family == "pm"
    assert row.payload["preferences"]["role_family"] == "pm"


@pytest.mark.asyncio
async def test_clearing_the_family_hands_the_decision_back_to_inference() -> None:
    payload = ProfilePayload(
        experiences=[_exp()], preferences=ProfilePreferences(role_family="pm")
    )
    service, row = _service(payload)
    resp = await service.update(
        "prof_1", actor=SimpleNamespace(), body=WritingOptionsRequest(role_family="")
    )
    assert resp.role_family == "backend"
    assert resp.role_family_explicit is False
    assert row.payload["preferences"]["role_family"] is None


@pytest.mark.asyncio
async def test_angles_are_capped_and_unknown_ids_dropped() -> None:
    payload = ProfilePayload(experiences=[_exp()])
    service, row = _service(payload)
    resp = await service.update(
        "prof_1",
        actor=SimpleNamespace(),
        body=WritingOptionsRequest(
            framing_emphases=["depth", "bogus", "ownership", "scope"]
        ),
    )
    assert resp.framing_emphases == ["depth", "ownership"]
    assert resp.framing_explicit is True
    assert row.payload["preferences"]["framing_emphases"] == ["depth", "ownership"]


@pytest.mark.asyncio
async def test_clearing_angles_falls_back_to_the_role_default_not_to_none() -> None:
    payload = ProfilePayload(
        experiences=[_exp()],
        preferences=ProfilePreferences(framing_emphases=["depth"]),
    )
    service, _ = _service(payload)
    resp = await service.update(
        "prof_1", actor=SimpleNamespace(), body=WritingOptionsRequest(framing_emphases=[])
    )
    assert resp.framing_emphases == recommended_for("backend")
    assert resp.framing_explicit is False


@pytest.mark.asyncio
async def test_omitted_fields_leave_the_other_setting_untouched() -> None:
    payload = ProfilePayload(
        experiences=[_exp()],
        preferences=ProfilePreferences(role_family="pm", framing_emphases=["depth"]),
    )
    service, row = _service(payload)
    resp = await service.update(
        "prof_1", actor=SimpleNamespace(), body=WritingOptionsRequest(framing_emphases=["scope"])
    )
    assert resp.role_family == "pm"
    assert row.payload["preferences"]["role_family"] == "pm"
    assert resp.framing_emphases == ["scope"]


@pytest.mark.asyncio
async def test_the_target_job_category_outranks_the_profile_title() -> None:
    payload = ProfilePayload(experiences=[_exp()])
    service, _ = _service(payload)
    service._job_context = AsyncMock(return_value=("pm", "高级产品经理"))
    resp = await service.get("prof_1", actor=SimpleNamespace(), job_id="job_1")
    assert resp.role_family == "pm"
    assert resp.role_family_explicit is False
