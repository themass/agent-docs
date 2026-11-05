"""Which line of work a mock interview is for.

The interviewer and the reviewer are told where to probe and what a good answer shows for a family
(`RolePlaybook.as_interview_block`). The family is the job's, not the candidate's: a backend
engineer going for a product job is interviewed as a product manager. Only when the job says
nothing usable does the candidate's own work stand in, and when that says nothing either the family
is the neutral one, which adds no guidance and so cannot send the interview the wrong way.
"""

from __future__ import annotations

from jc.domain.role_families import resolve_role_family


def mock_role_family(
    *,
    job_category: str | None = None,
    job_title: str | None = None,
    profile_titles: tuple[str | None, ...] = (),
) -> str:
    """The family id for an interview. A stored job category wins, then the job's title, then the
    titles of the candidate's own recent jobs."""
    return resolve_role_family(
        override=None,
        job_category=job_category,
        job_title=job_title,
        profile_titles=profile_titles,
    )


async def family_of_session(db, session) -> str:
    """The family for a stored mock session: its job when it has one, else the profile's recent
    titles. A job that belongs to another profile is not consulted."""
    from jc.models.job import Job
    from jc.models.profile import Profile
    from jc.schemas.profile_payload import ProfilePayload

    job = await db.get(Job, session.job_id) if session.job_id else None
    if job is not None and job.profile_id != session.profile_id:
        job = None
    titles: tuple[str | None, ...] = ()
    profile = await db.get(Profile, session.profile_id)
    if profile is not None:
        try:
            payload = ProfilePayload.model_validate(profile.payload or {})
            titles = tuple(experience.title for experience in payload.experiences[:3])
        except Exception:  # noqa: BLE001 — a profile that does not parse just adds no titles
            titles = ()
    return mock_role_family(
        job_category=job.role_category if job is not None else None,
        job_title=job.title if job is not None else None,
        profile_titles=titles,
    )
