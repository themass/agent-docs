"""Attachment intake guards, both sides of each gate.

Production test 2026-11-18 (附录 B / Cursor P1-1 + P1-2) proved two holes:

* oversized uploads reached the client as "200 + closed SSE stream" because the
  service's size check runs inside the async generator, after the SSE headers
  are already on the wire;
* bytes whose contents contradicted their declared mime (SVG posted as
  `image/jpeg`) were stored in the ledger as photos.

Every case below asserts BOTH directions where the gate has one: the reject
path returns a 4xx JSON error (never an opened SSE stream), and a legitimate
payload of the same category still passes. A test that only asserts the reject
side would pass even if the whole route started returning 400.
"""

from __future__ import annotations

import base64

import httpx
import pytest
from agentkit.web.auth import UserActor
from fastapi import FastAPI

from jc.api.agent_router import router as agent_router
from jc.api.auth_router import register_exception_handlers
from jc.api.deps import get_actor, get_agent_service
from jc.exceptions import AppError
from jc.services.agent_attachment_service import (
    MAX_ATTACHMENT_BYTES,
    AttachmentRejectedError,
    decode_data_url,
)

PNG = bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 40
GIF = b"GIF89a" + b"\x00" * 40
WEBP = b"RIFF" + (44).to_bytes(4, "little") + b"WEBP" + b"\x00" * 40
OggS = b"OggS" + b"\x00" * 40
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 40
M4A = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 40


def _data_url(mime: str, raw: bytes) -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def _jpeg(size: int) -> bytes:
    body = b"\x00" * max(0, size - 3)
    return b"\xff\xd8\xff" + body


def _fake_jpeg(svg: bytes) -> str:
    return _data_url("image/jpeg", svg)


# --- decode_data_url: magic bytes vs declared mime (unit, both sides) ---


def test_genuine_images_and_audio_decode():
    """Pass side: browser-produced bytes for every declared category accepted."""
    for mime, raw in [
        ("image/jpeg", _jpeg(500)),
        ("image/png", PNG),
        ("image/gif", GIF),
        ("image/webp", WEBP),
        ("audio/ogg", OggS),
        ("audio/webm", WEBM),
        ("audio/m4a", M4A),
    ]:
        blob = decode_data_url(_data_url(mime, raw))
        assert blob.raw == raw and blob.mime == mime


def test_svg_masquerading_as_jpeg_is_rejected():
    """Reject side: the exact P1-2 payload from production."""
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    with pytest.raises(AttachmentRejectedError):
        decode_data_url(_fake_jpeg(svg))


def test_html_masquerading_as_png_is_rejected():
    with pytest.raises(AttachmentRejectedError):
        decode_data_url(_data_url("image/png", b"<html><body>hi</body></html>"))


def test_text_masquerading_as_ogg_is_rejected():
    with pytest.raises(AttachmentRejectedError):
        decode_data_url(_data_url("audio/ogg", b"not an ogg stream at all"))


# --- HTTP boundary: 4xx JSON before the stream opens (both sides) ---


class _StubAgents:
    def __init__(self) -> None:
        self.calls = 0

    async def stream_message(self, session_id, **kwargs):  # noqa: ANN001, ANN003
        self.calls += 1
        yield {"type": "done"}


@pytest.fixture
async def env():
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(agent_router, prefix="/api/v1")
    stub = _StubAgents()
    app.dependency_overrides[get_actor] = lambda: UserActor(user_id="u1", session_id="s1")
    app.dependency_overrides[get_agent_service] = lambda: stub
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://fixture"
    ) as client:
        yield client, stub


async def _post_message(client: httpx.AsyncClient, attachments: list[dict]) -> httpx.Response:
    # no `async with client.stream`: httpx only reads the status/headers on send,
    # which is exactly the wire state the test is about.
    return await client.post(
        "/api/v1/agent/sessions/as1/messages",
        json={"content": "看图", "attachments": attachments},
    )


async def test_oversized_attachment_gets_400_not_an_opened_sse_stream(env):
    """Reject side (P1-1): >8MB must fail as 4xx JSON before any SSE headers."""
    client, stub = env
    r = await _post_message(
        client,
        [
            {
                "kind": "image",
                "name": "big.jpg",
                "mime_type": "image/jpeg",
                "data_url": _data_url("image/jpeg", _jpeg(MAX_ATTACHMENT_BYTES + 1)),
            },
        ],
    )
    assert r.status_code == 400, r.text[:200]
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["code"] == "attachment_too_large"
    assert stub.calls == 0  # the turn never even started


async def test_combined_over_cap_gets_400(env):
    """Reject side: each file passes the per-file gate but the message is over cap.

    4x7MB = 28MB > the 24MB combined cap. Exactly-on-cap (3x8MB) is NOT rejected:
    both caps compare with `>`, matching the per-file boundary the other tests pin.
    """
    client, _ = env
    per_file = 7 * 1024 * 1024
    r = await _post_message(
        client,
        [
            {
                "kind": "image",
                "name": f"b{i}.jpg",
                "mime_type": "image/jpeg",
                "data_url": _data_url("image/jpeg", _jpeg(per_file)),
            }
            for i in range(4)
        ],
    )
    assert r.status_code == 400
    assert r.json()["code"] == "attachment_too_large"


async def test_masquerading_mime_gets_400_not_stored(env):
    """Reject side (P1-2): SVG as jpeg now dies at the intake, not in the ledger."""
    client, stub = env
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><circle/></svg>'
    r = await _post_message(
        client,
        [
            {
                "kind": "image",
                "name": "photo.jpg",
                "mime_type": "image/jpeg",
                "data_url": _fake_jpeg(svg),
            },
        ],
    )
    assert r.status_code == 400
    assert r.json()["code"] == "attachment_rejected"
    assert stub.calls == 0


async def test_legitimate_image_still_opens_the_stream(env):
    """Pass side: exactly the per-file cap and real bytes still run the turn (8MB is
    NOT >8MB, so the boundary belongs to the pass side)."""
    client, stub = env
    async with client.stream(
        "POST",
        "/api/v1/agent/sessions/as1/messages",
        json={
            "content": "看图",
            "attachments": [
                {
                    "kind": "image",
                    "name": "ok.jpg",
                    "mime_type": "image/jpeg",
                    "data_url": _data_url("image/jpeg", _jpeg(MAX_ATTACHMENT_BYTES)),
                },
            ],
        },
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = [line async for line in r.aiter_lines()]
    assert any('"type": "done"' in line or '"type":"done"' in line for line in events)
    assert stub.calls == 1


async def test_plain_text_message_unaffected(env):
    """Pass side: the no-attachment path is untouched by the new gate."""
    client, stub = env
    async with client.stream(
        "POST",
        "/api/v1/agent/sessions/as1/messages",
        json={"content": "你好"},
    ) as r:
        assert r.status_code == 200
    assert stub.calls == 1


def test_app_error_is_the_400_carrier():
    """The gate's contract with the wire: AppError subclasses map to 400 via the
    registered handler; pin the class so a refactor that stops inheriting AppError
    gets caught here instead of turning intake failures back into 500s."""
    assert issubclass(AttachmentRejectedError, AppError)
