"""Application funnel schemas and status contract."""

from jobcome.models.enums import ApplicationStatus
from jobcome.schemas.job import ApplicationPatchRequest, ApplicationResponse


def test_application_status_values() -> None:
    assert {s.value for s in ApplicationStatus} == {
        "evaluated",
        "skipped",
        "applied",
        "interviewing",
        "rejected",
        "offer",
    }


def test_patch_request_accepts_skip_and_follow_up() -> None:
    body = ApplicationPatchRequest(status="skipped", note="方向不对", follow_up_on="")
    assert body.status == "skipped"
    assert body.note == "方向不对"
    assert body.follow_up_on == ""


def test_application_response_defaults() -> None:
    row = ApplicationResponse(
        id="appl_x",
        job_id="job_x",
        profile_id="prof_x",
        resume_variant_id=None,
        applied_at=None,
        note=None,
    )
    assert row.status == "evaluated"
    assert row.follow_up_on is None
