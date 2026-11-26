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


# ---- SSE 流式通道（POST /solve/stream）----

STREAM_URL = "/v1/photosolve/solve/stream?client_request_id=android-123&subject=math"


class StreamModel(Model):
    """astream 把同一份 JSON 切成小片吐出；error 在流尾抛出（模拟中途失败）。"""

    def __init__(self, content=None, error=None, pieces=None):
        super().__init__(content, error)
        self.pieces = pieces

    async def astream(self, messages):
        self.calls.append(messages)
        chunks = self.pieces if self.pieces is not None else [
            self.content[i:i + 7] for i in range(0, len(self.content), 7)] if isinstance(self.content, str) else []
        for piece in chunks:
            yield SimpleNamespace(content=piece)
        if self.error:
            raise self.error


def sse_frames(body: str) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for block in body.split("\n\n"):
        event, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if event is not None:  # 注释帧（keepalive）没有 event 行，跳过
            out.append((event, data))
    return out


def stream(client, url=STREAM_URL, content=None, headers=None):
    with client.stream("POST", url, content=content if content is not None else image_bytes(),
                       headers=headers or HEADERS) as response:
        return response.status_code, response.headers, "".join(response.iter_text())


def test_stream_event_sequence_and_done_matches_full_result():
    model = StreamModel()
    http = client(model)
    status, headers, body = stream(http)
    assert status == 200
    assert headers["content-type"].startswith("text/event-stream")
    assert headers["x-accel-buffering"] == "no"
    frames = sse_frames(body)
    names = [name for name, _ in frames]
    assert names[0] == "meta"
    assert names.index("step_start") < names.index("step_delta") < names.index("step_end")
    assert names[-1] == "done"
    assert frames[0][1] == {"questionFound": True}
    # done 帧带完整结果 JSON——与全量端点同一份形状（客户端据此收敛对账）
    full = client(model).post(URL, content=image_bytes(), headers=HEADERS).json()
    assert frames[-1][1] == full
    # step_end 带校验后的整步
    step_end = next(data for name, data in frames if name == "step_end")
    assert step_end["step"]["text"] == "两个一相加"
    # answer 在 done 之前、按题发出
    answer = next(data for name, data in frames if name == "answer")
    assert answer == {"questionIndex": 0, "finalAnswer": "2", "finalAnswerLatex": ""}


def test_stream_reassembly_obeys_step_boundaries():
    """step_delta 拼接 == step_end 的内容：块内增量、块间不重叠，客户端可安全渲染。"""
    pieces = ['{"questionFound": true, "questions": [{"index": 1, "text": "1+1', '=?", "steps": ',
              '[{"index": 1, "text": "相加 $1+', '1$", "latex": "$1+1=', '2$"}], "finalAnswer": "2"}]}']
    _, _, body = stream(client(StreamModel(pieces=pieces)))
    frames = sse_frames(body)
    assert frames[-1][0] == "done"
    rebuilt = "".join(d["text"] for n, d in frames if n == "step_delta" and d["field"] == "text")
    step_end = next(d for n, d in frames if n == "step_end")
    assert rebuilt == step_end["step"]["text"] == "相加 $1+1$"
    # 公式不被切开：任何 delta 里的未转义 `$` 都成对
    import re
    for n, d in frames:
        if n == "step_delta":
            assert len(re.findall(r"(?<!\\)\$", d["text"])) % 2 == 0, d


def test_stream_no_question_emits_meta_and_done_only():
    model = StreamModel(json.dumps({"questionFound": False, "questions": []}))
    _, _, body = stream(client(model))
    frames = sse_frames(body)
    assert [name for name, _ in frames] == ["meta", "done"]
    assert frames[0][1] == {"questionFound": False}


def test_stream_idempotent_replays_cached_result_without_model():
    model = StreamModel()
    http = client(model)
    _, _, first = stream(http)
    _, _, second = stream(http)
    assert len(model.calls) == 1
    first_frames, second_frames = sse_frames(first), sse_frames(second)
    # 回放与直播的 delta 粒度可以不同（直播跟模型 chunk 走，回放按字段整块），
    # 但 done 的全量对账帧必须一模一样。
    assert first_frames[-1] == second_frames[-1] and first_frames[-1][0] == "done"
    rebuilt = "".join(d["text"] for n, d in second_frames if n == "step_delta" and d["field"] == "text")
    step_end = next(d for n, d in second_frames if n == "step_end")
    assert rebuilt == step_end["step"]["text"] == "两个一相加"
    # 回放对全量端点同样生效：同一个缓存结果
    assert http.post(URL, content=image_bytes(), headers=HEADERS).json() == second_frames[-1][1]
    assert len(model.calls) == 1


def test_full_then_stream_shares_the_same_cache():
    model = StreamModel()
    http = client(model)
    full = http.post(URL, content=image_bytes(), headers=HEADERS).json()
    _, _, body = stream(http)
    assert sse_frames(body)[-1][1] == full
    assert len(model.calls) == 1


@pytest.mark.parametrize("data,status", [(b"", 422), (b"not an image", 422)])
def test_stream_rejects_bad_image_before_opening_the_stream(data, status):
    model = StreamModel()
    response = client(model).post(STREAM_URL, content=data, headers=HEADERS)
    assert response.status_code == status and response.json()["detail"]["code"] == 40003
    assert not model.calls


def test_stream_validates_parameters_like_full_endpoint():
    response = client(StreamModel()).post("/v1/photosolve/solve/stream?subject=english",
                                          content=image_bytes(), headers=HEADERS)
    assert response.status_code == 400 and response.json()["detail"]["code"] == 40003


def test_stream_body_bound_still_applies():
    model = StreamModel()
    headers = dict(HEADERS)
    headers["Content-Length"] = str(MAX_BYTES + 1)
    response = client(model).post(STREAM_URL, content=iter([b"x" * MAX_BYTES, b"x"]), headers=headers)
    assert response.status_code == 413 and response.json()["detail"]["code"] == 40003
    assert not model.calls


def test_stream_model_failure_emits_error_event_then_closes():
    error = RuntimeError("private upstream detail")
    error.status_code = 429
    model = StreamModel(error=error)
    status, _, body = stream(client(model))
    assert status == 200  # 流已开，状态码改不了——错误在流内表达
    frames = sse_frames(body)
    assert frames[-1] == ("error", {"code": 42901, "message": "请求过于频繁，请稍后重试",
                                    "retryable": True})
    assert "private" not in body


def test_stream_malformed_model_output_is_error_event_50001():
    # 非法转义在解析器处炸：语义与全量路径的 50001 一致，不发半截 done。
    pieces = ['{"questionFound": true, "questions": [{"index": 1, "text": "a\\qb"',
              ', "finalAnswer": "x"}]}']
    status, _, body = stream(client(StreamModel(pieces=pieces)))
    assert status == 200
    frames = sse_frames(body)
    assert frames[-1][0] == "error" and frames[-1][1]["code"] == 50001
    assert all(name != "done" for name, _ in frames)


def test_stream_error_is_not_cached_so_retry_recomputes():
    class FailOnce(StreamModel):
        async def astream(self, messages):
            self.calls.append(messages)
            if len(self.calls) == 1:
                raise RuntimeError("gone")
            for piece in [self.content[i:i + 7] for i in range(0, len(self.content), 7)]:
                yield SimpleNamespace(content=piece)

    model = FailOnce()
    http = client(model)
    _, _, first = stream(http)
    assert sse_frames(first)[-1][0] == "error"
    _, _, second = stream(http)
    assert sse_frames(second)[-1][0] == "done"
    assert len(model.calls) == 2


def test_stream_first_token_timeout_closes_with_error(monkeypatch):
    import asyncio
    import companion.service.photosolve as photosolve
    monkeypatch.setattr(photosolve, "FIRST_TOKEN_TIMEOUT_SECONDS", 0.05)
    class Silent:
        async def astream(self, messages):
            await asyncio.Event().wait()
            yield None  # pragma: no cover
    _, _, body = stream(client(service=PhotoSolveService(lambda: Silent())))
    frames = sse_frames(body)
    assert frames == [("error", {"code": 50001, "message": "解题服务暂时不可用，请稍后重试",
                                 "retryable": True})]


async def test_full_and_stream_share_one_inflight_model_call():
    """同 requestId 的并发请求单飞：后到的挂在先到的上面，模型只打一次。"""
    import asyncio
    started, release = asyncio.Event(), asyncio.Event()

    class Gated(StreamModel):
        async def ainvoke(self, messages):
            self.calls.append(messages)
            started.set()
            await release.wait()
            return SimpleNamespace(content=self.content)

    model = Gated()
    service = PhotoSolveService(lambda: model)
    url = await service.prepare(image_bytes())

    async def collect(gen):
        return [event async for event in gen]

    leader = asyncio.create_task(service.solve(image_bytes(), request_id="shared-1"))
    await started.wait()
    joiner = asyncio.create_task(collect(service.solve_stream(url, request_id="shared-1")))
    await asyncio.sleep(0)  # 让 joiner 走到 await future
    release.set()
    full = await leader
    events = await joiner
    assert len(model.calls) == 1
    assert events[-1] == ("done", full)  # 回放与全量结果一致


def test_create_app_registers_stream_route(monkeypatch):
    from companion.bootstrap import app as bootstrap
    from companion.config import Settings
    monkeypatch.setattr(bootstrap, "settings", Settings(_env_file=None, companion_env="dev",
                        companion_auth_verifier="allow_all", companion_redis_url="",
                        companion_room_store="memory"))
    default = bootstrap.create_app(verifier=Auth(), livekit_url="")
    assert "/v1/photosolve/solve/stream" in default.openapi()["paths"]
