"""Chat attachments: the bytes must not reach the message row, and only once to vision.

Both defects covered here were invisible to the rest of the suite:

* The double-OCR one looked like correct code at each call site. `agent_service`
  flattened the message, then handed the same attachments to the harness, which
  flattened again — so every image was transcribed (and paid for) twice and the OCR
  text appeared twice in the prompt. Nothing asserted how many times vision was called.
* The oversized-payload one cannot fail on SQLite, which is what the suite runs on:
  its TEXT column has no length limit, while MySQL `TEXT` stops at 65,535 bytes. The
  assertion therefore has to be about the string we are about to store, not about the
  database accepting it.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from jc.agent import message_content
from jc.agent.message_content import build_user_message_content
from jc.paths import PROJECT_ROOT
from jc.schemas.agent import AgentAttachment
from jc.services import agent_attachment_service as svc
from jc.services import agent_service as agent_service_module

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
)


def data_url(mime: str, raw: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def image_attachment(raw: bytes = PNG_1X1, *, name: str = "jd.png") -> AgentAttachment:
    return AgentAttachment(
        kind="image",
        name=name,
        label=name,
        mime_type="image/png",
        data_url=data_url("image/png", raw),
    )


class _RecordingStore:
    """Stands in for TOS / the local filesystem backend."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, key: str, body: bytes, *, content_type: str | None = None) -> str:
        self.objects[key] = body
        return key


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> _RecordingStore:
    recording = _RecordingStore()
    monkeypatch.setattr(svc, "get_storage_backend", lambda: recording)
    monkeypatch.setattr(svc, "download_url_for_key", lambda key, **_: f"https://cdn.test/{key}")
    return recording


# --- decode ---------------------------------------------------------------------


def test_decode_data_url_returns_bytes_and_mime() -> None:
    blob = svc.decode_data_url(data_url("image/png", PNG_1X1))
    assert blob.raw == PNG_1X1
    assert blob.mime == "image/png"
    assert blob.extension == ".png"


def test_decode_rejects_non_media_mime() -> None:
    with pytest.raises(svc.AttachmentRejectedError):
        svc.decode_data_url(data_url("application/zip", b"PK\x03\x04"))


def test_decode_rejects_non_base64_payload() -> None:
    # A percent-encoded `data:` URL is legal in the spec; accepting it would be a
    # second way to get bytes in, and nothing in JC produces one.
    with pytest.raises(svc.AttachmentRejectedError):
        svc.decode_data_url("data:image/png,%89PNG")


def test_decode_rejects_corrupt_base64() -> None:
    with pytest.raises(svc.AttachmentRejectedError):
        svc.decode_data_url("data:image/png;base64,!!!!not base64!!!!")


# --- validation happens before the model runs -----------------------------------


def test_oversized_attachment_is_refused_with_its_own_name() -> None:
    big = b"\x00" * (svc.MAX_ATTACHMENT_BYTES + 1)
    with pytest.raises(svc.AttachmentTooLargeError) as err:
        svc.validate_inline_attachments([image_attachment(big, name="huge.png")])
    assert "huge.png" in str(err.value)
    assert err.value.code == "attachment_too_large"


def test_attachments_that_only_add_up_to_too_much_are_refused() -> None:
    half = b"\x00" * (svc.MAX_ATTACHMENT_BYTES - 1024)
    many = [image_attachment(half, name=f"p{i}.png") for i in range(5)]
    with pytest.raises(svc.AttachmentTooLargeError):
        svc.validate_inline_attachments(many)


def test_reasonable_attachments_pass() -> None:
    svc.validate_inline_attachments([image_attachment(), image_attachment(name="b.png")])


def test_document_attachment_without_data_url_is_not_inspected() -> None:
    # A .docx arrives as `text_preview`, never as a `data:` URL.
    svc.validate_inline_attachments(
        [AgentAttachment(kind="file", name="resume.docx", text_preview="内容")]
    )


# --- offload: the row that goes to MySQL ----------------------------------------


async def test_offloaded_row_carries_the_key_and_not_the_bytes(store: _RecordingStore) -> None:
    rows = await svc.offload_for_persistence(
        [image_attachment()], session_id="ags_1", message_id="agm_1"
    )
    assert "data_url" not in rows[0]
    assert rows[0]["storage_key"] == "jc/dev/agent/ags_1/attachments/agm_1-0.png"
    assert rows[0]["size_bytes"] == len(PNG_1X1)
    assert store.objects["jc/dev/agent/ags_1/attachments/agm_1-0.png"] == PNG_1X1


async def test_persisted_payload_stays_far_under_the_mysql_text_limit(
    store: _RecordingStore,
) -> None:
    """The regression that SQLite cannot express.

    A 1280x720 camera frame is ~300 KB, so ~400 KB as base64 — six times what MySQL
    `TEXT` holds. Serialize the payload the way `AgentMessageStore.append` does and
    assert on its length directly.
    """
    camera_frame = b"\xff\xd8\xff" + b"\x00" * (300 * 1024)
    rows = await svc.offload_for_persistence(
        [
            AgentAttachment(
                kind="image",
                name="camera.jpg",
                mime_type="image/jpeg",
                data_url=data_url("image/jpeg", camera_frame),
            )
        ],
        session_id="ags_1",
        message_id="agm_1",
    )
    serialized = json.dumps({"attachments": rows}, ensure_ascii=False)
    assert "data:" not in serialized
    assert len(serialized.encode()) < 65_535


async def test_upload_failure_keeps_the_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """The turn has already run; a failed upload must not raise over the answer."""

    class _BrokenStore:
        def put_object(self, key: str, body: bytes, *, content_type: str | None = None) -> str:
            raise RuntimeError("TOS unreachable")

    monkeypatch.setattr(svc, "get_storage_backend", _BrokenStore)
    rows = await svc.offload_for_persistence(
        [image_attachment()], session_id="ags_1", message_id="agm_1"
    )
    assert rows[0]["storage_key"] is None
    assert rows[0]["name"] == "jd.png"


async def test_document_attachment_keeps_its_text_preview(store: _RecordingStore) -> None:
    rows = await svc.offload_for_persistence(
        [AgentAttachment(kind="file", name="jd.txt", text_preview="岗位要求")],
        session_id="ags_1",
        message_id="agm_1",
    )
    assert rows[0]["text_preview"] == "岗位要求"
    assert "storage_key" not in rows[0]
    assert store.objects == {}


async def test_upload_does_not_block_the_request_loop(
    monkeypatch: pytest.MonkeyPatch, store: _RecordingStore
) -> None:
    """`put_object` is a blocking network call and must not run on the loop.

    The chat path already serializes agent runs behind a process-wide lock, so an
    upload of up to `MAX_MESSAGE_ATTACHMENT_BYTES` executed inline would stall every
    other request too. Asserting the thread identity rather than reading the source
    keeps this true if the call moves.
    """
    import threading

    loop_thread = threading.current_thread().ident
    upload_threads: list[int | None] = []

    original = store.put_object

    def recording(key: str, body: bytes, *, content_type: str | None = None) -> str:
        upload_threads.append(threading.current_thread().ident)
        return original(key, body, content_type=content_type)

    monkeypatch.setattr(store, "put_object", recording)
    await svc.offload_for_persistence(
        [image_attachment()], session_id="ags_1", message_id="agm_1"
    )
    assert upload_threads and all(tid != loop_thread for tid in upload_threads)


# --- replay: signed URLs expire, transcripts do not -----------------------------


def test_replay_resigns_from_the_stored_key(store: _RecordingStore) -> None:
    payload: dict[str, Any] = {
        "attachments": [
            {
                "kind": "image",
                "name": "jd.png",
                "storage_key": "jc/dev/agent/ags_1/attachments/agm_1-0.png",
                "download_url": "https://cdn.test/expired-two-days-ago",
            }
        ]
    }
    refreshed = svc.resign_persisted_attachments(payload)
    assert refreshed is not None
    assert (
        refreshed["attachments"][0]["download_url"]
        == "https://cdn.test/jc/dev/agent/ags_1/attachments/agm_1-0.png"
    )


def test_replay_leaves_rows_without_a_key_alone(store: _RecordingStore) -> None:
    payload = {"ui_context": {"page": "resume-agent"}}
    assert svc.resign_persisted_attachments(payload) == payload
    assert svc.resign_persisted_attachments(None) is None

# --- vision must be paid for once ------------------------------------------------


async def test_photo_intent_skips_vision_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    from jc.agent import message_content

    async def fail_describe(*_a: Any, **_k: Any) -> str:
        raise AssertionError("vision should not run for avatar-only turns")

    monkeypatch.setattr(message_content, "describe_image", fail_describe)
    monkeypatch.setattr(message_content.settings, "jc_llm_enabled", True)

    attachments = [image_attachment(name="camera.jpg")]
    out = await message_content.flatten_message_for_text_agent(
        "把这张图片设置为头像",
        attachments,
    )
    assert "jc_profile_photo_set" in out
    assert "camera.jpg" in out


async def test_flattening_twice_duplicates_the_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Why the call site below matters: flatten is not idempotent.

    `flatten_message_for_text_agent` appends the OCR text to the message. Running it on
    its own output appends a second copy and calls vision a second time. This test
    records that behaviour so the guard underneath it reads as a consequence rather
    than a preference.
    """
    from jc.agent import message_content

    calls: list[str] = []

    async def fake_describe(ref: Any, *, purpose: str) -> str:
        calls.append(purpose)
        return "OCR TEXT"

    monkeypatch.setattr(message_content, "describe_image", fake_describe)
    monkeypatch.setattr(message_content.settings, "jc_llm_enabled", True)

    attachments = [image_attachment(name="a.png")]
    once = await message_content.flatten_message_for_text_agent("hi", attachments)
    twice = await message_content.flatten_message_for_text_agent(once, attachments)

    assert once.count("OCR TEXT") == 1
    assert twice.count("OCR TEXT") == 2
    assert len(calls) == 2


def test_agent_service_does_not_hand_attachments_to_an_already_flattened_turn() -> None:
    """The regression guard.

    `AgentService.stream_message` flattens the message itself, so the harness must get
    text only. Passing `attachments=` as well is what made the harness flatten a second
    time. Checked on the syntax tree because the defect is a kwarg at one call site; a
    behavioural test would have to stand up the whole harness to see it.
    """
    import ast
    import inspect

    from jc.services import agent_service

    tree = ast.parse(inspect.getsource(agent_service))
    stream_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "stream_message"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "client"
    ]
    assert stream_calls, "expected AgentService to call client.stream_message"
    for call in stream_calls:
        kwargs = {kw.arg for kw in call.keywords}
        assert "attachments" not in kwargs


# --- voice: the words and the recording must stay together ----------------------
#
# There is no server-side STT in this version. The browser recognizes the speech and
# sends both the clip and its transcript, which makes two things true at once: the
# transcript is the *only* readable form of the recording, and it is usually already
# the message text because dictation types into the composer. Everything below is
# about not losing it and not storing it twice.


def voice_attachment(
    *,
    transcript: str | None = "上个季度我把结算延迟从 8 小时压到 20 分钟",
    duration_ms: int | None = 7400,
) -> AgentAttachment:
    return AgentAttachment(
        kind="audio",
        name="voice.webm",
        label="语音",
        mime_type="audio/webm",
        data_url=data_url("audio/webm", b"OggS" + b"\x01" * 2048),
        transcript=transcript,
        duration_ms=duration_ms,
    )


async def test_offloaded_voice_row_keeps_the_transcript(store: _RecordingStore) -> None:
    """A clip in storage with its words lost is an audio player nobody can read."""
    rows = await svc.offload_for_persistence(
        [voice_attachment()], session_id="ags_1", message_id="agm_1"
    )
    row = rows[0]
    assert row["storage_key"] == "jc/dev/agent/ags_1/attachments/agm_1-0.webm"
    assert row["transcript"] == "上个季度我把结算延迟从 8 小时压到 20 分钟"
    assert row["duration_ms"] == 7400
    assert "data_url" not in row


async def test_voice_row_without_a_transcript_omits_the_key(store: _RecordingStore) -> None:
    """Safari has no SpeechRecognition; the row should not claim empty words."""
    rows = await svc.offload_for_persistence(
        [voice_attachment(transcript=None, duration_ms=None)],
        session_id="ags_1",
        message_id="agm_1",
    )
    assert "transcript" not in rows[0]
    assert "duration_ms" not in rows[0]
    assert rows[0]["storage_key"] is not None


async def test_failed_voice_upload_is_flagged_and_logged(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A storage outage used to be indistinguishable from "the user sent no media".

    Two consequences, both covered here: an operator cannot count the damage, and the
    bubble renders a dead `<audio>` element. The transcript survives either way, which
    is what makes the message still worth showing.
    """
    class _BrokenStore:
        def put_object(self, key: str, body: bytes, *, content_type: str | None = None) -> str:
            raise RuntimeError("TOS unreachable")

    monkeypatch.setattr(svc, "get_storage_backend", _BrokenStore)
    with caplog.at_level("WARNING"):
        rows = await svc.offload_for_persistence(
            [voice_attachment()], session_id="ags_1", message_id="agm_1"
        )
    row = rows[0]
    assert row["storage_key"] is None
    assert row["storage_error"] is True
    assert row["transcript"] == "上个季度我把结算延迟从 8 小时压到 20 分钟"
    assert any("attachment offload failed" in rec.message for rec in caplog.records)
    # The blob must never reach the log.
    assert not any("OggS" in rec.getMessage() for rec in caplog.records)


def test_model_reads_the_spoken_words_not_the_file_name() -> None:
    """`[Voice message: voice.webm]` taught the agent to ask the user to repeat."""
    built = build_user_message_content("", [voice_attachment()])
    assert isinstance(built, str)
    assert "上个季度我把结算延迟从 8 小时压到 20 分钟" in built
    assert "voice.webm" not in built


def test_dictated_words_are_not_sent_twice() -> None:
    """Dictation types into the composer, so the transcript is usually already the text.

    Appending it again put the user's sentence in the prompt twice — reads as the user
    repeating themselves, and doubles the token bill on every voice turn.
    """
    said = "上个季度我把结算延迟从 8 小时压到 20 分钟"
    built = build_user_message_content(said, [voice_attachment(transcript=said)])
    assert isinstance(built, str)
    assert built.count("结算延迟") == 1


def test_edited_text_still_carries_what_was_said() -> None:
    """The user can clear or rewrite the box after dictating; then the clip is the record."""
    built = build_user_message_content("帮我改一下", [voice_attachment()])
    assert isinstance(built, str)
    assert "帮我改一下" in built
    assert "上个季度我把结算延迟从 8 小时压到 20 分钟" in built


def test_unreadable_clip_tells_the_agent_it_cannot_hear_it() -> None:
    """Silently dropping it made the agent answer a message it never received."""
    built = build_user_message_content("", [voice_attachment(transcript=None)])
    assert isinstance(built, str)
    assert message_content.AUDIO_UNREADABLE_SUFFIX in built


def test_stored_turn_does_not_repeat_the_dictated_sentence() -> None:
    """What the user sees when reopening the session."""
    said = "上个季度我把结算延迟从 8 小时压到 20 分钟"
    stored = agent_service_module._format_user_message(said, [voice_attachment(transcript=said)])
    assert stored.count("结算延迟") == 1


def test_stored_turn_keeps_words_the_text_lost() -> None:
    stored = agent_service_module._format_user_message(
        "帮我改一下", [voice_attachment()]
    )
    assert "帮我改一下" in stored
    assert "上个季度我把结算延迟从 8 小时压到 20 分钟" in stored


def test_stored_turn_never_shows_the_models_english_attachment_markers() -> None:
    """Regression: the history row leaked prompt-only markers into the user's own bubble.

    `[Attached image: x.png]` / `[Attached voice: ...]` / `[Attached file: ...]` are
    labels the model-facing flattener uses so the agent knows an attachment exists.
    They used to also get written into this row's text, which `AgentUserBubble`
    renders verbatim as plain prose — so a user who sent only a photo, or a voice clip
    that failed to transcribe, saw raw English brackets sitting where their own words
    should be. Every one of these kinds already has its own structured bubble
    (thumbnail, voice player, file chip) built from `attachments`, so this row's text
    must carry only what the user actually said or typed — nothing else.
    """
    image_only = agent_service_module._format_user_message("", [image_attachment()])
    assert "Attached" not in image_only
    assert "[" not in image_only

    file_only = agent_service_module._format_user_message(
        "", [AgentAttachment(kind="file", name="resume.docx", text_preview="内容")]
    )
    assert "Attached" not in file_only
    assert "[" not in file_only

    unreadable_voice = agent_service_module._format_user_message(
        "", [voice_attachment(transcript=None)]
    )
    assert "Attached" not in unreadable_voice
    assert "[" not in unreadable_voice
    # Nothing was said and nothing was typed — the voice bubble alone carries the
    # "could not transcribe" state; this row has no text to show.
    assert unreadable_voice == ""


def test_replay_resigns_a_voice_clip_and_keeps_its_words(store: _RecordingStore) -> None:
    payload: dict[str, Any] = {
        "attachments": [
            {
                "kind": "audio",
                "name": "voice.webm",
                "transcript": "我带了 12 个人",
                "duration_ms": 4100,
                "storage_key": "jc/dev/agent/ags_1/attachments/agm_1-0.webm",
                "download_url": "https://cdn.test/expired",
            }
        ]
    }
    refreshed = svc.resign_persisted_attachments(payload)
    assert refreshed is not None
    row = refreshed["attachments"][0]
    assert row["download_url"].endswith("agm_1-0.webm")
    assert row["transcript"] == "我带了 12 个人"


def test_voice_bubble_survives_a_lost_recording() -> None:
    """Frontend contract: filtering audio on having a playable source hid the message.

    Read from source because there is no JS test runner in this project, and the defect
    is a one-line filter predicate.
    """
    bubble = (PROJECT_ROOT / "frontend/web/lib/agent-ui-kit/conversation/AgentUserBubble.tsx").read_text()
    assert 'a.kind === "audio" && (attachmentSrc(a) || a.transcript?.trim())' in bubble
    assert "transcript={audio.transcript}" in bubble


def test_composer_sends_only_this_recording_words() -> None:
    """Reading the input box at send time attached the wrong words to the clip.

    The box may already hold typed text and stays editable afterwards, so the composer
    accumulates the current recording's final chunks separately.
    """
    # AgentComposer.tsx now delegates rendering to agent-ui-kit; the recording
    # accumulation logic this test guards lives in the kit implementation.
    composer = (
        PROJECT_ROOT / 'frontend/web/lib/agent-ui-kit/composer/AgentComposer.tsx'
    ).read_text()
    assert "dictatedRef" in composer
    assert "transcript: said || null" in composer
    assert "duration_ms: clip.durationMs" in composer
