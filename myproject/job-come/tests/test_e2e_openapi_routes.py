"""OpenAPI includes Week-1+ routes."""

from jobcome.main import app


def test_openapi_jobs_and_campaign_routes() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/jobs/profiles/{profile_id}/parse" in paths
    assert "/api/v1/jobs/profiles/{profile_id}/apply-pipeline" in paths
    assert "/api/v1/jobs/profiles/{profile_id}/parse-url" in paths
    assert "/api/v1/jobs/profiles/{profile_id}/applications" in paths
    assert "/api/v1/jobs/profiles/{profile_id}/applications/{application_id}" in paths
    assert "/api/v1/campaign/profiles/{profile_id}" in paths
    assert "/api/v1/agent/sessions" in paths
    assert "/api/v1/coach/questions/{question_id}" in paths
    assert "/api/v1/coach/mock/sessions" in paths
    assert "/api/v1/coach/mock/sessions/{session_id}" in paths
    assert "/api/v1/coach/profiles/{profile_id}/questions" in paths
    assert "/api/v1/auth/change-password" in paths
