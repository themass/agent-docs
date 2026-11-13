"""阿里云 TTS 适配器：签名、参数、token 缓存、错误识别。全部离线，不碰网络。"""

import json
from collections.abc import AsyncIterator

import pytest

from companion.service.voice.aliyun import (
    AliyunConfig,
    AliyunProvider,
    AliyunProtocolError,
    canonical_query,
    create_token_params,
    is_error_body,
    parse_token_response,
    rpc_signature,
    signed_token_params,
    tts_query,
)
from companion.service.voice.port import VoiceProviderError, VoiceRef, VoiceUnavailable


def config(**kw) -> AliyunConfig:
    base = dict(app_id="appkey-1", access_key_id="AK", access_key_secret="SK")
    base.update(kw)
    return AliyunConfig(**base)


class FakeHttp:
    """按顺序返回预设响应，并记下每次请求。"""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[tuple[str, dict, dict]] = []

    async def post(self, url, *, data=None, headers=None):
        self.calls.append((url, dict(data or {}), dict(headers or {})))
        if not self._responses:
            raise AssertionError("unexpected extra request")
        return self._responses.pop(0)

    async def post_form(self, url, *, data=None):
        return await self.post(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})


async def stream(*parts: str) -> AsyncIterator[str]:
    for part in parts:
        yield part


# ---- 纯函数 ----

def test_canonical_query_is_order_independent():
    params = {"B": "2", "A": "1", "C": "a b"}
    assert canonical_query(params) == canonical_query(dict(reversed(list(params.items()))))
    assert canonical_query(params) == "A=1&B=2&C=a%20b"


def test_signature_depends_on_secret_and_params():
    params = create_token_params(access_key_id="AK", now=0)
    sig = rpc_signature(method="POST", params=params, access_key_secret="SK")
    assert len(sig) == 28 and sig.endswith("=")
    assert rpc_signature(method="POST", params=params, access_key_secret="other") != sig
    changed = dict(params, RegionId="cn-beijing")
    assert rpc_signature(method="POST", params=changed, access_key_secret="SK") != sig


def test_signed_token_params_carry_a_signature():
    params = signed_token_params(access_key_id="AK", access_key_secret="SK", now=0)
    assert params["Action"] == "CreateToken" and params["Signature"]
    assert params["Timestamp"] == "1970-01-01T00:00:00Z"


def test_parse_token_response_validates_shape():
    assert parse_token_response({"Token": {"Id": "t1", "ExpireTime": 1700000000}}) == ("t1", 1700000000)
    for bad in ({"Token": {}}, {"Token": {"Id": "", "ExpireTime": 1}}, {"Token": {"Id": "x"}}, {}):
        with pytest.raises(AliyunProtocolError):
            parse_token_response(bad)


def test_tts_query_defaults():
    q = tts_query(appkey="a", token="t", text="你好")
    assert (q["format"], q["sample_rate"], q["text_type"], q["uid"]) == ("wav", "16000", "plain", "a")
    assert tts_query(appkey="a", token="t", text="<speak/>", text_type="ssml")["text_type"] == "ssml"


def test_error_body_only_matches_json():
    assert is_error_body(b'{"message":"invalid token"}') == "invalid token"
    assert is_error_body(b'{"Message":"x"}') == "x"
    assert is_error_body(b"RIFF....") is None      # wav
    assert is_error_body(b"ID3....") is None       # mp3
    assert is_error_body(b"{not json") is None


def test_missing_credentials_say_which_ones():
    with pytest.raises(VoiceUnavailable) as exc:
        AliyunConfig.from_env({"ALI_TTS_APP_ID": "a"})
    assert "ALI_TTS_ACCESS_KEY" in str(exc.value)


# ---- 供应商 ----

def token_response(token="tok", expires=2_000_000_000) -> tuple[int, bytes]:
    return 200, json.dumps({"Token": {"Id": token, "ExpireTime": expires}}).encode()


async def test_tts_fetches_a_token_once_and_synthesises_each_sentence():
    http = FakeHttp([token_response(), (200, b"RIFF-wav-1"), (200, b"RIFF-wav-2")])
    provider = AliyunProvider(config=config(), client=http)
    ref = VoiceRef(provider="aliyun", voice_id="xiaoyun")

    chunks = [c async for c in provider.tts(stream("第一句。", "  ", "第二句。"), ref)]

    assert [c.data for c in chunks] == [b"RIFF-wav-1", b"RIFF-wav-2"]   # 空白句被跳过
    assert http.calls[0][0].startswith("https://nls-meta")
    assert http.calls[0][1]["Action"] == "CreateToken"
    assert http.calls[1][1]["token"] == "tok" and http.calls[1][1]["text"] == "第一句。"
    assert all(c.format == "wav" and c.sample_rate == 16000 for c in chunks)


async def test_a_valid_token_is_reused():
    http = FakeHttp([token_response(), (200, b"a"), (200, b"b")])
    provider = AliyunProvider(config=config(), client=http)
    ref = VoiceRef(provider="aliyun", voice_id="xiaoyun")
    [c async for c in provider.tts(stream("一"), ref)]
    [c async for c in provider.tts(stream("二"), ref)]
    assert len(http.calls) == 3        # 一次换 token + 两次合成


async def test_an_expired_token_is_refreshed():
    http = FakeHttp([token_response(expires=1000), (200, b"x"), token_response(token="tok2"), (200, b"y")])
    provider = AliyunProvider(config=config(), client=http)
    ref = VoiceRef(provider="aliyun", voice_id="xiaoyun")
    [c async for c in provider.tts(stream("一"), ref)]
    [c async for c in provider.tts(stream("二"), ref)]
    assert http.calls[2][1]["Action"] == "CreateToken"          # 过期后重新换了一次
    assert http.calls[3][1]["token"] == "tok2"


async def test_a_json_error_body_becomes_a_provider_error():
    http = FakeHttp([token_response(), (200, b'{"message":"invalid appkey"}')])
    provider = AliyunProvider(config=config(), client=http)
    with pytest.raises(VoiceProviderError) as exc:
        [c async for c in provider.tts(stream("你好"), VoiceRef(provider="aliyun", voice_id="v"))]
    assert "invalid appkey" in str(exc.value) and exc.value.provider == "aliyun"


async def test_token_failure_is_reported_as_provider_error():
    http = FakeHttp([(403, b"denied")])
    provider = AliyunProvider(config=config(), client=http)
    with pytest.raises(VoiceProviderError):
        [c async for c in provider.tts(stream("你好"), VoiceRef(provider="aliyun", voice_id="v"))]


async def test_asr_is_explicitly_unsupported():
    provider = AliyunProvider(config=config(), client=FakeHttp([]))
    with pytest.raises(VoiceUnavailable):
        provider.asr(stream("x"))  # type: ignore[arg-type]
