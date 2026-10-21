"""OpenAPI schema smoke tests."""

from jc.main import app


def test_openapi_schema_has_api_routes() -> None:
    schema = app.openapi()
    assert schema["info"]["title"] == "JC API"
    paths = schema["paths"]
    assert "/api/v1/auth/context" in paths
    assert "/api/v1/profiles/upload" in paths
    assert "/api/v1/auth/account" in paths
    assert "/api/v1/auth/verify-email-code" in paths
    assert "/api/v1/profiles/{profile_id}/export" in paths
    # The three ways into a profile are all contract surface: a file, pasted text, and
    # the interview. Listing them here is what keeps "we have a route for that" from
    # being true only in a service method no client can reach.
    assert "/api/v1/profiles/from-text" in paths
    upload_post = paths["/api/v1/profiles/upload"]["post"]
    assert upload_post.get("summary") == "上传简历"
    assert paths["/api/v1/profiles/from-text"]["post"].get("summary") == "粘贴内容建档"


def test_docs_urls_under_api_prefix() -> None:
    assert app.docs_url == "/api/v1/docs"
    assert app.openapi_url == "/api/v1/openapi.json"
    assert app.redoc_url == "/api/v1/redoc"
