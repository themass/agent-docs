"""Offline endpoint contract: fake auth/model, real shared image normalization."""

import base64
import io
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from companion.api.http.deps import build_current_user
from companion.api.http.routers.photosolve import build_router
from companion.service.auth.port import AuthUnavailable, IdentityError
from companion.service.photosolve import PhotoSolveService
from companion.service.uploads.policy import MAX_BYTES

URL = "/v1/photosolve/solve?client_request_id=android-123&subject=math"
HEADERS = {"Authorization": "Bearer login-token", "Content-Type": "image/jpeg"}
VALID = {"questionFound": True, "questions": [{"index": 1, "text": "1+1=?",
         "steps": [{"index": 1, "text": "两个一相加"}], "finalAnswer": "2", "confidence": 0.99}]}


class Auth:
    async def verify(self, authorization):
        if authorization != "Bearer login-token":
            raise IdentityError("login required")
        return "1001"


class Model:
    def __init__(self, content=None, error=None):
        self.content = json.dumps(VALID) if content is None else content
        self.error = error
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return SimpleNamespace(content=self.content)


def image_bytes(size=(12, 8)):
    out = io.BytesIO()
    image = Image.new("RGB", size, "white")
    exif = Image.Exif()
    exif[270] = "private metadata"
    image.save(out, "PNG", exif=exif)
    return out.getvalue()


def client(model=None, *, verifier=None, service=None):
    app = FastAPI()
    app.include_router(build_router(service or PhotoSolveService(lambda: model),
                                    build_current_user(verifier or Auth())))
    return TestClient(app)


def test_success_matches_android_and_normalizes_before_multimodal_call():
    model = Model()
    response = client(model).post(URL, content=image_bytes((3000, 100)), headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"requestId", "providerUsed", "subject", "questionFound", "questions"}
    assert body["requestId"] == "android-123" and body["subject"] == "math"
    question = body["questions"][0]
    assert question["finalAnswer"] == "2" and question["thinking"] == ""
    assert question["finalAnswerLatex"] == "" and question["steps"][0]["latex"] == ""
    messages = model.calls[0]
    url = messages[1]["content"][1]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    with Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))) as normalized:
        assert normalized.format == "JPEG" and max(normalized.size) == 2048
        assert not normalized.getexif()


def test_no_question_is_success_for_android_mapper():
    model = Model(json.dumps({"questionFound": False, "questions": []}))
    response = client(model).post(URL, content=image_bytes(), headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["questionFound"] is False


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}])
def test_auth_before_normalization_or_model(headers):
    model = Model()
    def forbidden(_):
        pytest.fail("unauthenticated image was normalized")
    service = PhotoSolveService(lambda: model, normalize=forbidden)
    response = client(service=service).post(URL, content=b"invalid", headers=headers)
    assert response.status_code == 401
    assert not model.calls


def test_auth_unavailable():
    class Offline:
        async def verify(self, authorization):
            raise AuthUnavailable("redis unavailable")
    response = client(Model(), verifier=Offline()).post(URL, content=b"", headers=HEADERS)
    assert response.status_code == 503


@pytest.mark.parametrize("data", [b"", b"not an image", b"\x89PNG\r\n\x1a\ncorrupt"])
def test_invalid_images_are_safe_422(data):
    model = Model()
    response = client(model).post(URL, content=data, headers=HEADERS)
    assert response.status_code == 422 and response.json()["detail"]["code"] == 40003
    assert not model.calls


def test_image_dimensions_rejected():
    response = client(Model()).post(URL, content=image_bytes((8193, 1)), headers=HEADERS)
    assert response.status_code == 422


@pytest.mark.parametrize("declared", [None, str(MAX_BYTES + 1)])
def test_body_bound_with_and_without_content_length(declared):
    model = Model()
    headers = dict(HEADERS)
    if declared:
        headers["Content-Length"] = declared
    response = client(model).post(URL, content=iter([b"x" * MAX_BYTES, b"x"]), headers=headers)
    assert response.status_code == 413 and response.json()["detail"]["code"] == 40003
    assert not model.calls


@pytest.mark.parametrize("query", ["", "?client_request_id=", "?client_request_id=x&subject=english",
                                    "?client_request_id=" + "x" * 129])
def test_bad_parameters(query):
    response = client(Model()).post("/v1/photosolve/solve" + query, content=b"", headers=HEADERS)
    assert response.status_code == 400 and response.json()["detail"]["code"] == 40003


@pytest.mark.parametrize("content", [
    "not json", "{}", "[]", '{"questionFound":"true","questions":[]}',
    '{"questionFound":true,"questions":[]}',
    '{"questionFound":false,"questions":[{}]}',
    json.dumps({"questionFound": True, "questions": [{"index": 1, "text": "q", "finalAnswer": " "}]}),
    json.dumps({"questionFound": True, "questions": [{"index": 1, "text": "q", "finalAnswer": "a", "confidence": 2}]}),
    json.dumps({"questionFound": True, "questions": [{"index": 1, "text": "q", "finalAnswer": "a", "confidence": float("nan")}]}),
    "x" * (128 * 1024 + 1), None,
])
def test_malformed_model_results(content):
    model = Model()
    model.content = content
    response = client(model).post(URL, content=image_bytes(), headers=HEADERS)
    assert response.status_code == 502 and response.json()["detail"]["code"] == 50001


def test_text_content_blocks_and_json_fence():
    model = Model([{"type": "reasoning", "text": "ignore"},
                   {"type": "text", "text": "```json\n" + json.dumps(VALID) + "\n```"}])
    assert client(model).post(URL, content=image_bytes(), headers=HEADERS).status_code == 200


@pytest.mark.parametrize("error,status,code", [(RuntimeError("secret upstream detail"), 502, 50001),
                                                (TimeoutError(), 502, 50001)])
def test_model_failure_is_sanitized(error, status, code):
    response = client(Model(error=error)).post(URL, content=image_bytes(), headers=HEADERS)
    assert response.status_code == status and response.json()["detail"]["code"] == code
    assert "secret" not in response.text


def test_upstream_quota():
    error = RuntimeError("private")
    error.status_code = 429
    response = client(Model(error=error)).post(URL, content=image_bytes(), headers=HEADERS)
    assert response.status_code == 429 and response.json()["detail"]["code"] == 42901


def test_create_app_registers_without_platform_or_gateway(monkeypatch):
    from companion.bootstrap import app as bootstrap
    from companion.config import Settings
    monkeypatch.setattr(bootstrap, "settings", Settings(_env_file=None, companion_env="dev",
                        companion_auth_verifier="allow_all", companion_redis_url="",
                        companion_room_store="memory"))
    app = bootstrap.create_app(verifier=Auth(), livekit_url="", photosolve=PhotoSolveService(lambda: Model()))
    response = TestClient(app).post(URL, content=image_bytes(), headers=HEADERS)
    assert response.status_code == 200
    # The production default is also registered but constructs no gateway at startup.
    default = bootstrap.create_app(verifier=Auth(), livekit_url="")
    assert "/v1/photosolve/solve" in default.openapi()["paths"]


def test_normalization_rejection_never_calls_model():
    from companion.service.uploads.policy import UploadRejected
    model = Model()
    def reject(_):
        raise UploadRejected("cannot decode image")
    service = PhotoSolveService(lambda: model, normalize=reject)
    response = client(service=service).post(URL, content=image_bytes(), headers=HEADERS)
    assert response.status_code == 422 and not model.calls


async def test_total_model_deadline(monkeypatch):
    import asyncio
    import companion.service.photosolve as photosolve
    class Slow:
        async def ainvoke(self, messages):
            await asyncio.Event().wait()
    monkeypatch.setattr(photosolve, "MODEL_TIMEOUT_SECONDS", 0.01)
    with pytest.raises(photosolve.PhotoSolveError) as failure:
        await PhotoSolveService(lambda: Slow()).solve(image_bytes(), request_id="deadline")
    assert (failure.value.status, failure.value.code) == (502, 50001)


@pytest.mark.parametrize("scenarios,expected", [(["photosolve"], "photosolve"),
                                               (["companion_chat"], "companion_chat")])
def test_bootstrap_uses_nonstreaming_photosolve_scenario(monkeypatch, scenarios, expected):
    from companion.bootstrap import models
    calls = []
    router = SimpleNamespace(scenarios=scenarios)
    monkeypatch.setattr(models, "LLMRouter", lambda path: router)
    def build(actual_router, scenario, *, streaming):
        calls.append((actual_router, scenario, streaming))
        return Model()
    monkeypatch.setattr(models, "scenario_model", build)
    service = models.photosolve_service(SimpleNamespace(companion_llm_routing_path="unused"))
    assert not calls
    assert client(service=service).post(URL, content=image_bytes(), headers=HEADERS).status_code == 200
    assert calls == [(router, expected, False)]
    assert client(service=service).post(URL, content=image_bytes(), headers=HEADERS).status_code == 200
    assert len(calls) == 1  # Successful model construction is cached, not per-request.
