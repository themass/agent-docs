import json
import struct
from dataclasses import FrozenInstanceError

import pytest

from companion.voice import (
    AudioChunk,
    FakeVoiceProvider,
    UnknownVoiceProvider,
    VoiceGateway,
    VoiceProviderError,
    VoiceRef,
    VoiceUnavailable,
    VolcengineConfig,
    VolcengineProvider,
    build_gateway,
)
from companion.voice.port import VoiceProvider, Transcript
from companion.voice.volcengine import (
    FLAG_LAST_NO_SEQUENCE,
    FLAG_POSITIVE_SEQUENCE,
    MSG_AUDIO_SERVER_RESPONSE,
    MSG_ERROR,
    MSG_FULL_CLIENT_REQUEST,
    MSG_FULL_SERVER_RESPONSE,
    ServerFrame,
    VolcengineProtocolError,
    build_auth_headers,
    build_frame,
    build_header,
    build_tts_frame,
    build_tts_payload,
    frame_format,
    parse_asr_response,
    parse_frame,
    parse_tts_response,
)


# ---- 构造 VoiceRef ----

def ref(provider="fake", voice_id="v1", **params):
    return VoiceRef(provider=provider, voice_id=voice_id, params=params)


def test_voice_ref_from_dict_requires_provider_and_voice_id():
    assert VoiceRef.from_dict({"provider": "volcengine", "voice_id": "a"}) == VoiceRef(
        provider="volcengine", voice_id="a", params={}
    )
    assert VoiceRef.from_dict({"voice_id": "a"}) is None
    assert VoiceRef.from_dict({"provider": "x"}) is None
    assert VoiceRef.from_dict(None) is None
    # 空字符串等同于缺失，不算「有声音」
    assert VoiceRef.from_dict({"provider": " ", "voice_id": "a"}) is None


def test_voice_ref_stable_key_ignores_param_order():
    a = VoiceRef("x", "v", {"speed": 1.2, "emotion": "joy"})
    b = VoiceRef("x", "v", {"emotion": "joy", "speed": 1.2})
    assert a.stable_key() == b.stable_key()


def test_ref_is_hashable_and_immutable():
    r = ref(emotion="joy")
    assert {r}
    assert {r} == {ref(emotion="joy")}
    with pytest.raises(FrozenInstanceError):
        r.provider = "other"  # type: ignore[misc]


# ---- 供应商选择 ----

async def collect_audio(agen):
    return [chunk async for chunk in agen]


async def test_selects_provider_from_voice_ref():
    fake = FakeVoiceProvider(name="fake")
    other = FakeVoiceProvider(name="other")
    gw = VoiceGateway({"fake": fake, "other": other})

    chunks = await collect_audio(gw.tts(aiter_of("你好呀。"), ref(provider="fake")))
    assert chunks
    assert fake.tts_calls and not other.tts_calls


async def test_unknown_provider_error_names_registered_ones():
    gw = VoiceGateway({"alpha": FakeVoiceProvider(name="alpha"), "beta": FakeVoiceProvider(name="beta")})
    with pytest.raises(UnknownVoiceProvider) as excinfo:
        gw.tts(aiter_of("hi"), ref(provider="gamma"))
    message = str(excinfo.value)
    assert "gamma" in message
    assert "alpha" in message and "beta" in message


async def test_empty_registry_is_rejected_at_construction():
    with pytest.raises(ValueError):
        VoiceGateway({})


async def test_registered_names_sorted():
    gw = VoiceGateway({"b": FakeVoiceProvider(name="b"), "a": FakeVoiceProvider(name="a")})
    assert gw.registered == ["a", "b"]


# ---- 断句 ----

async def test_splitter_feeds_whole_sentences_to_provider():
    fake = FakeVoiceProvider(name="fake")
    gw = VoiceGateway({"fake": fake})
    # 逐字喂，供应商应当收到整句
    stream = aiter_of("你好。", "今天", "好吗？")
    chunks = await collect_audio(gw.tts(stream, ref()))
    assert chunks
    assert [t for _, t in fake.tts_calls] == ["你好。", "今天好吗？"]


# ---- 缓存 ----

async def test_cache_hit_avoids_second_synthesis_call():
    fake = FakeVoiceProvider(name="fake")
    gw = VoiceGateway({"fake": fake})

    first = await collect_audio(gw.tts(aiter_of("你好呀。"), ref(voice_id="lin")))
    assert len(fake.synthesized_text) == 1
    second = await collect_audio(gw.tts(aiter_of("你好呀。"), ref(voice_id="lin")))

    assert second == first
    assert len(fake.synthesized_text) == 1, "第二次应当命中缓存"
    assert gw.cache_hits == 1


async def test_long_text_is_not_cached():
    fake = FakeVoiceProvider(name="fake")
    gw = VoiceGateway({"fake": fake}, max_phrase_chars=4)
    phrase = "这是一句很长的话。"
    await collect_audio(gw.tts(aiter_of(phrase), ref()))
    await collect_audio(gw.tts(aiter_of(phrase), ref()))
    assert len(fake.synthesized_text) == 2
    assert gw.cache_size == 0


async def test_cache_is_per_voice_and_per_provider():
    a = FakeVoiceProvider(name="a")
    b = FakeVoiceProvider(name="b")
    gw = VoiceGateway({"a": a, "b": b})

    await collect_audio(gw.tts(aiter_of("在的。"), ref(provider="a", voice_id="lin")))
    await collect_audio(gw.tts(aiter_of("在的。"), ref(provider="a", voice_id="su")))
    assert len(a.synthesized_text) == 2, "不同音色不能共用缓存"

    await collect_audio(gw.tts(aiter_of("在的。"), ref(provider="b", voice_id="lin")))
    assert len(b.synthesized_text) == 1
    assert gw.cache_hits == 0


async def test_precache_fills_cache_and_is_idempotent():
    fake = FakeVoiceProvider(name="fake")
    gw = VoiceGateway({"fake": fake})
    written = await gw.precache(["早上好呀。", "晚安。"], ref())
    assert written == 2
    assert await gw.precache(["早上好呀。"], ref()) == 0

    calls_before = len(fake.synthesized_text)
    await collect_audio(gw.tts(aiter_of("早上好呀。"), ref()))
    assert len(fake.synthesized_text) == calls_before
    assert gw.cache_hits == 1


async def test_cache_capacity_evicts_oldest():
    fake = FakeVoiceProvider(name="fake")
    gw = VoiceGateway({"fake": fake}, cache_capacity=2)
    for phrase in ("一。", "二。", "三。"):
        await collect_audio(gw.tts(aiter_of(phrase), ref()))
    assert gw.cache_size == 2


# ---- 故障切换 ----

async def test_fallback_after_consecutive_failures():
    primary = FakeVoiceProvider(name="primary", fail_times=2)
    backup = FakeVoiceProvider(name="backup")
    gw = VoiceGateway({"primary": primary, "backup": backup}, secondary="backup", failure_threshold=2)

    # 第一次调用就换人重说这一句：用户听不到报错，只需要等到音频
    chunks = await collect_audio(gw.tts(aiter_of("在的。"), ref(provider="primary")))
    assert chunks
    assert primary.tts_calls == [("v1", "在的。")], "阈值未到不该重打主供应商"
    assert backup.tts_calls == [("v1", "在的。")]
    assert gw.switches == [], "阈值未到，还不算切换"

    # 第二次连续失败：达到阈值，固定走备用并留下审计记录
    await collect_audio(gw.tts(aiter_of("还在吗。"), ref(provider="primary")))
    assert len(gw.switches) == 1
    switch = gw.switches[0]
    assert (switch.provider_from, switch.provider_to, switch.direction) == ("primary", "backup", "tts")
    assert switch.failures == 2
    assert gw.active_provider("tts") == "backup"

    # 之后直接走备用，不再惊动主供应商
    calls_before = len(primary.tts_calls)
    await collect_audio(gw.tts(aiter_of("真的还在吗。"), ref(provider="primary")))
    assert len(primary.tts_calls) == calls_before
    assert backup.synthesized_text[-1] == "真的还在吗。"


async def test_fallback_recovery_logs_single_switch(caplog):
    primary = FakeVoiceProvider(name="primary", fail_forever=True)
    backup = FakeVoiceProvider(name="backup")
    gw = VoiceGateway({"primary": primary, "backup": backup}, secondary="backup", failure_threshold=2)
    with caplog.at_level("ERROR", logger="companion.voice"):
        for phrase in ("一。", "二。", "三。"):
            await collect_audio(gw.tts(aiter_of(phrase), ref(provider="primary")))
    assert len(gw.switches) == 1, "切换只记一次，之后不再重复记账"
    assert sum(1 for r in caplog.records if "switched" in r.message) == 1
    assert all(c.data for c in await collect_audio(gw.tts(aiter_of("四。"), ref(provider="primary"))))


async def test_switch_is_logged(caplog):
    primary = FakeVoiceProvider(name="primary", fail_times=1)
    backup = FakeVoiceProvider(name="backup")
    gw = VoiceGateway({"primary": primary, "backup": backup}, secondary="backup", failure_threshold=1)
    with caplog.at_level("ERROR", logger="companion.voice"):
        await collect_audio(gw.tts(aiter_of("嗨。"), ref(provider="primary")))
    assert any("switched" in record.message for record in caplog.records)


async def test_retry_happens_only_when_nothing_was_emitted():
    class Halfway(FakeVoiceProvider):
        async def tts(self, text_stream, voice_ref):
            text = "".join([t async for t in text_stream])
            self.tts_calls.append((voice_ref.voice_id, text))
            yield AudioChunk(data=b"partial", sample_rate=1, format="pcm")
            raise VoiceProviderError("boom mid-stream", provider=self.name, direction="tts")

    primary = Halfway(name="primary")
    backup = FakeVoiceProvider(name="backup")
    gw = VoiceGateway({"primary": primary, "backup": backup}, secondary="backup", failure_threshold=1)

    received = []
    with pytest.raises(VoiceProviderError):
        async for chunk in gw.tts(aiter_of("半句话。"), ref(provider="primary")):
            received.append(chunk)
    assert received, "已经吐出的音频不撤回"
    assert backup.tts_calls == [], "混音色比报错更糟，不能中途换供应商"


async def test_no_fallback_configured_raises_provider_error():
    primary = FakeVoiceProvider(name="primary", fail_forever=True)
    gw = VoiceGateway({"primary": primary}, failure_threshold=1)
    with pytest.raises(VoiceProviderError):
        await collect_audio(gw.tts(aiter_of("嗨。"), ref(provider="primary")))
    assert gw.switches == []
    assert gw.active_provider("tts") is None


async def test_reset_fallback_returns_to_primary():
    primary = FakeVoiceProvider(name="primary", fail_times=1)
    backup = FakeVoiceProvider(name="backup")
    gw = VoiceGateway({"primary": primary, "backup": backup}, secondary="backup", failure_threshold=1)
    await collect_audio(gw.tts(aiter_of("嗨。"), ref(provider="primary")))
    assert gw.active_provider("tts") == "backup"
    gw.reset_fallback()
    assert gw.active_provider("tts") is None
    assert gw.switches, "切换记录不因恢复而清空"


async def test_secondary_must_be_registered_to_be_used():
    primary = FakeVoiceProvider(name="primary", fail_forever=True)
    gw = VoiceGateway({"primary": primary}, secondary="ghost", failure_threshold=1)
    with pytest.raises(VoiceProviderError):
        await collect_audio(gw.tts(aiter_of("嗨。"), ref(provider="primary")))
    assert gw.switches == []


# ---- ASR ----

async def test_asr_propagates_is_final():
    fake = FakeVoiceProvider(name="fake")
    gw = VoiceGateway({"fake": fake}, asr_provider="fake")
    results = [t async for t in gw.asr(aiter_of(b"abc", b"de"))]
    assert [r.is_final for r in results] == [False, False, True]
    assert results[-1].text == "done:5"
    assert all(isinstance(r, Transcript) for r in results)


async def test_asr_does_not_retry_midstream_because_frames_are_gone():
    primary = FakeVoiceProvider(name="primary")
    backup = FakeVoiceProvider(name="backup")
    gw = VoiceGateway({"primary": primary, "backup": backup}, primary="backup", asr_provider="primary", failure_threshold=1)

    class Breaks(FakeVoiceProvider):
        async def asr(self, audio_stream):
            async for _ in audio_stream:
                pass
            raise VoiceProviderError("asr broke", provider=self.name, direction="asr")
            yield  # pragma: no cover

    gw._providers["primary"] = Breaks(name="primary")
    with pytest.raises(VoiceProviderError):
        async for _ in gw.asr(aiter_of(b"a")):
            pass
    assert gw.switches and gw.switches[0].direction == "asr"
    assert gw.active_provider("asr") == "backup"


async def test_asr_unknown_provider_error():
    gw = VoiceGateway({"fake": FakeVoiceProvider(name="fake")}, asr_provider="nope")
    with pytest.raises(UnknownVoiceProvider):
        gw.asr(aiter_of(b"a"))


# ---- 火山协议：帧构造 ----

def test_header_layout_fixed_bytes():
    assert build_header(MSG_FULL_CLIENT_REQUEST) == bytes([0x11, 0x10, 0x10, 0x00])
    assert build_header(MSG_AUDIO_SERVER_RESPONSE, FLAG_LAST_NO_SEQUENCE) == bytes(
        [0x11, 0xB2, 0x10, 0x00]
    )


def test_header_rejects_out_of_range_fields():
    with pytest.raises(ValueError):
        build_header(0b10000)
    with pytest.raises(ValueError):
        build_header(0b0001, 0b10000)


def test_full_frame_with_sequence_and_payload():
    frame = build_frame(
        MSG_FULL_CLIENT_REQUEST, b"\xaa\xbb", flags=FLAG_POSITIVE_SEQUENCE, sequence=7
    )
    # 头 4 + 序号 4 + 长度 4 + 负载 2
    assert frame[:4] == bytes([0x11, 0x11, 0x10, 0x00])
    assert struct.unpack_from(">I", frame, 4)[0] == 7
    assert struct.unpack_from(">I", frame, 8)[0] == 2
    assert frame[12:] == b"\xaa\xbb"


def test_error_frame_carries_code_before_length():
    frame = build_frame(MSG_ERROR, b"bad", flags=0, error_code=4000)
    assert struct.unpack_from(">I", frame, 4)[0] == 4000
    assert struct.unpack_from(">I", frame, 8)[0] == 3
    assert frame[12:] == b"bad"


def test_frame_rejects_inconsistent_optional_fields():
    with pytest.raises(ValueError):
        build_frame(MSG_FULL_CLIENT_REQUEST, flags=FLAG_POSITIVE_SEQUENCE)  # 缺序号
    with pytest.raises(ValueError):
        build_frame(MSG_FULL_CLIENT_REQUEST, sequence=1)  # 无标志却给序号
    with pytest.raises(ValueError):
        build_frame(MSG_FULL_CLIENT_REQUEST, error_code=1)  # 非错误帧给错误码
    with pytest.raises(ValueError):
        build_frame(MSG_ERROR)  # 错误帧没错误码


def test_tts_payload_shape():
    payload = build_tts_payload(
        "你好", VoiceRef("volcengine", "zh_female_x", {"speed_ratio": 1.3, "emotion": "joy"}),
        app_id="app-1", cluster="volcano_tts",
    )
    assert payload["app"] == {"appid": "app-1", "cluster": "volcano_tts"}
    assert payload["audio"]["voice_type"] == "zh_female_x"
    assert payload["audio"]["speed_ratio"] == 1.3
    assert payload["audio"]["emotion"] == "joy"
    assert payload["request"]["text"] == "你好"
    assert payload["request"]["operation"] == "submit"


def test_tts_frame_roundtrips_as_json():
    frame = build_tts_frame("嗨", ref(provider="volcengine"), app_id="a", cluster="c")
    parsed = parse_frame(frame)
    assert parsed.message_type == MSG_FULL_CLIENT_REQUEST
    assert parsed.json_payload()["request"]["text"] == "嗨"


# ---- 火山协议：响应解析（固定字节） ----

def json_frame(payload: dict, message_type=MSG_FULL_SERVER_RESPONSE, flags=FLAG_LAST_NO_SEQUENCE,
               sequence=None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return build_frame(message_type, body, flags=flags, sequence=sequence)


def test_parse_audio_frame_fixed_fixture():
    # 0x11 头 / 0xB2 = 音频帧 + 末帧标志 / JSON / 无压缩 / 空 / 长度 3 / "abc"
    raw = bytes([0x11, 0xB2, 0x10, 0x00, 0x00, 0x00, 0x00, 0x03]) + b"abc"
    parsed = parse_frame(raw)
    assert parsed.is_audio and parsed.is_last
    assert parsed.payload == b"abc"
    audio, done = parse_tts_response(parsed)
    assert audio == b"abc" and done is True


def test_parse_non_last_audio_frame_fixed_fixture():
    raw = bytes([0x11, 0xB0, 0x10, 0x00, 0x00, 0x00, 0x00, 0x02]) + b"xy"
    audio, done = parse_tts_response(parse_frame(raw))
    assert audio == b"xy" and done is False


def test_parse_frame_with_sequence():
    raw = build_frame(
        MSG_AUDIO_SERVER_RESPONSE, b"z", flags=FLAG_POSITIVE_SEQUENCE, sequence=42
    )
    parsed = parse_frame(raw)
    assert parsed.sequence == 42
    assert parsed.is_last is False


def test_parse_error_frame_fixture():
    raw = build_frame(MSG_ERROR, b"denied", error_code=45000001)
    parsed = parse_frame(raw)
    assert parsed.is_error and parsed.error_code == 45000001
    with pytest.raises(VoiceProviderError) as excinfo:
        parse_tts_response(parsed)
    assert "45000001" in str(excinfo.value)


def test_parse_truncated_frames_raise():
    raw = bytes([0x11, 0xB2, 0x10, 0x00, 0x00, 0x00, 0x00, 0x05]) + b"ab"
    with pytest.raises(VolcengineProtocolError):
        parse_frame(raw)
    with pytest.raises(VolcengineProtocolError):
        parse_frame(b"\x11\x10")
    with pytest.raises(VolcengineProtocolError):
        parse_frame(bytes([0x12, 0xB2, 0x10, 0x00, 0, 0, 0, 0]))  # 头长 8，不支持


def test_parse_frame_rejects_truncated_sequence_and_error_code():
    with pytest.raises(VolcengineProtocolError):
        parse_frame(bytes([0x11, 0x11, 0x10, 0x00, 0x00]))
    with pytest.raises(VolcengineProtocolError):
        parse_frame(bytes([0x11, 0xF0, 0x10, 0x00, 0x00]))


def test_json_payload_rejects_non_json_serialization():
    parsed = ServerFrame(
        message_type=MSG_FULL_SERVER_RESPONSE, flags=0, serialization=0, compression=0, payload=b"\x00"
    )
    with pytest.raises(VolcengineProtocolError):
        parsed.json_payload()


def test_frame_format_reads_encoding_from_json():
    parsed = parse_frame(json_frame({"encoding": "ogg_opus"}))
    assert frame_format(parsed) == "ogg_opus"
    audio_only = parse_frame(build_frame(MSG_AUDIO_SERVER_RESPONSE, b"q"))
    assert frame_format(audio_only) == "pcm"


def test_parse_asr_response_variants():
    final = parse_frame(json_frame({"result": [{"text": "你好"}], "confidence": 0.87}))
    transcript = parse_asr_response(final)
    assert transcript.text == "你好" and transcript.is_final and transcript.confidence == 0.87

    partial = parse_frame(json_frame({"result": {"text": "你"}}, flags=FLAG_POSITIVE_SEQUENCE, sequence=3))
    assert parse_asr_response(partial).is_final is False

    flat = parse_frame(json_frame({"text": "嗯"}))
    assert parse_asr_response(flat).text == "嗯"


# ---- 鉴权与配置 ----

def test_auth_header_uses_semicolon_form():
    assert build_auth_headers("tok") == {"Authorization": "Bearer; tok"}


def test_auth_header_rejects_empty_token():
    with pytest.raises(VoiceUnavailable):
        build_auth_headers("  ")


def test_config_from_env_requires_all_tts_vars():
    with pytest.raises(VoiceUnavailable) as excinfo:
        VolcengineConfig.from_env({"VOLC_TTS_APP_ID": "a"})
    assert "VOLC_TTS_ACCESS_TOKEN" in str(excinfo.value)
    assert "VOLC_TTS_ENDPOINT" in str(excinfo.value)


def test_config_from_env_defaults_and_asr_inheritance():
    cfg = VolcengineConfig.from_env(
        {
            "VOLC_TTS_APP_ID": "app",
            "VOLC_TTS_ACCESS_TOKEN": "tok",
            "VOLC_TTS_ENDPOINT": "wss://example.invalid/tts",
        }
    )
    assert cfg.tts_cluster == "volcano_tts"
    assert cfg.asr_app_id == "app"  # 缺省复用
    assert cfg.asr_access_token == "tok"
    assert cfg.asr_endpoint == ""


# ---- 火山供应商：用假 socket 端到端 ----

class FakeSocket:
    def __init__(self, incoming):
        self.incoming = list(incoming)
        self.sent = []
        self.closed = False

    async def send(self, data):
        self.sent.append(data)

    async def recv(self):
        if not self.incoming:
            raise AssertionError("recv past end of fixture")
        return self.incoming.pop(0)

    async def close(self):
        self.closed = True


class FakeConnector:
    def __init__(self, socket):
        self.socket = socket
        self.calls = []

    async def connect(self, url, headers):
        self.calls.append((url, dict(headers)))
        return self.socket


def provider_with(socket, **cfg):
    base = {
        "app_id": "app",
        "access_token": "tok",
        "tts_endpoint": "wss://example.invalid/tts",
    }
    base.update(cfg)
    return VolcengineProvider(config=VolcengineConfig(**base), client=FakeConnector(socket))


async def test_volcengine_tts_streams_frames_to_audio():
    socket = FakeSocket(
        [
            build_frame(MSG_AUDIO_SERVER_RESPONSE, b"\x01\x02"),
            build_frame(MSG_AUDIO_SERVER_RESPONSE, b"\x03", flags=FLAG_LAST_NO_SEQUENCE),
        ]
    )
    provider = provider_with(socket)
    chunks = [c async for c in provider.tts(aiter_of("你好。"), VoiceRef("volcengine", "vc-1"))]

    assert [c.data for c in chunks] == [b"\x01\x02", b"\x03"]
    assert chunks[0].sample_rate == provider.sample_rate and chunks[0].format == "pcm"
    assert socket.closed is True
    connector = provider.client
    assert connector.calls[0][0] == "wss://example.invalid/tts"
    assert connector.calls[0][1] == {"Authorization": "Bearer; tok"}

    # 发出的请求帧能被自己的解析器读回
    sent = parse_frame(socket.sent[0])
    assert sent.json_payload()["audio"]["voice_type"] == "vc-1"


async def test_volcengine_tts_raises_on_error_frame():
    socket = FakeSocket([build_frame(MSG_ERROR, b"nope", error_code=45000001)])
    provider = provider_with(socket)
    with pytest.raises(VoiceProviderError):
        async for _ in provider.tts(aiter_of("嗨。"), VoiceRef("volcengine", "v")):
            pass
    assert socket.closed is True, "出错也要关连接"


async def test_volcengine_asr_requires_endpoint():
    provider = provider_with(FakeSocket([]))
    with pytest.raises(VoiceUnavailable):
        async for _ in provider.asr(aiter_of(b"a")):
            pass


async def test_volcengine_asr_parses_final_transcript():
    socket = FakeSocket(
        [
            json_frame({"result": [{"text": "你"}], "confidence": 0.4}, flags=FLAG_POSITIVE_SEQUENCE, sequence=1),
            json_frame({"result": [{"text": "你好"}], "confidence": 0.9, "is_final": True}),
        ]
    )
    provider = provider_with(socket, asr_endpoint="wss://example.invalid/asr")
    results = [t async for t in provider.asr(aiter_of(b"audio"))]
    assert [(r.text, r.is_final) for r in results] == [("你", False), ("你好", True)]
    assert socket.sent == [b"audio"]
    assert socket.closed is True


# ---- 端口一致性 ----

def test_fake_and_volcengine_satisfy_port_protocol():
    assert isinstance(FakeVoiceProvider(), VoiceProvider)
    provider = provider_with(FakeSocket([]))
    assert isinstance(provider, VoiceProvider)


async def aiter_of(*items):
    for item in items:
        yield item


# ---- 装配 ----

def test_build_gateway_uses_explicit_providers():
    gw = build_gateway({"fake": FakeVoiceProvider()}, secondary=None)
    assert gw.registered == ["fake"]


def test_build_gateway_fails_loudly_without_config(monkeypatch):
    for name in ("VOLC_TTS_APP_ID", "VOLC_TTS_ACCESS_TOKEN", "VOLC_TTS_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(VoiceUnavailable):
        build_gateway()


def test_build_gateway_from_env(monkeypatch):
    monkeypatch.setenv("VOLC_TTS_APP_ID", "app")
    monkeypatch.setenv("VOLC_TTS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VOLC_TTS_ENDPOINT", "wss://example.invalid/tts")
    monkeypatch.setenv("COMPANION_VOICE_SECONDARY", "  ")
    gw = build_gateway()
    assert gw.registered == ["volcengine"]
    # 空白值按未配置处理，不能变成一个空字符串供应商名
    assert gw._secondary is None
