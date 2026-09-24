"""OpenAPI schema smoke tests."""

from jobcome.main import app


def test_openapi_schema_has_api_routes() -> None:
    schema = app.openapi()
    assert schema["info"]["title"] == "JobCome API"
    paths = schema["paths"]
    assert "/api/v1/auth/context" in paths
    assert "/api/v1/profiles/upload" in paths
    assert "/api/v1/profiles/{profile_id}/export" in paths
    upload_post = paths["/api/v1/profiles/upload"]["post"]
    assert upload_post.get("summary") == "上传简历"


def test_docs_urls_under_api_prefix() -> None:
    assert app.docs_url == "/api/v1/docs"
    assert app.openapi_url == "/api/v1/openapi.json"
    assert app.redoc_url == "/api/v1/redoc"
