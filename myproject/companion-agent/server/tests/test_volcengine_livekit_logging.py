"""NewConsoleSTT 的连接可观测性：开流/连上/断/错，每样必须在 voice.log 里有一行。

事故依据（2026-11-21 测量轮 R3，room QOd1c_5g，job pid 223060）：音频到达服务端、
VAD 正常翻转，`inbound user_transcript` 恒零，而整个 pid 的日志里 **STT 段落一个
字都没有**——插件失败路径的日志全在 `livekit.plugins.volcengine` 命名空间，且插件
对"连接建立后不再吐字"这种静默死法根本没有日志点。下次复现时，日志必须能回答
"ASR websocket 到底连上没有、什么时候断的、断的时候有没有异常"。

日志走 `companion.service.voice.volcengine_livekit` 命名空间：和
inbound_audio_probe 同一棵已验证能进 voice.log 的树（R3 里 `name:
companion.api.livekit.inbound_audio_probe` 的行都在）。

http_session 显式注入：插件在无 job context 时拒绝自建 session（测试里正是这种
场景），生产装配本来就走 http_session 参数或惰性自建，注入不影响线上路径。
"""

from __future__ import annotations

import logging

import aiohttp
import pytest

from companion.service.voice import volcengine_livekit as vl

_LOGGER = "companion.service.voice.volcengine_livekit"


class _FakeWS:
    async def close(self) -> None:
        pass


@pytest.fixture
async def stream():
    session = aiohttp.ClientSession()
    try:
        stt = vl.NewConsoleSTT(api_key="test-key", http_session=session)
        yield stt.stream()
    finally:
        await session.close()


def test_stream_returns_the_logging_subclass(stream) -> None:
    """装配层拿到的必须是我们的子类，否则日志点全部落空。"""
    assert isinstance(stream, vl._LoggingSpeechStream)


async def test_ws_open_logs_elapsed(stream, monkeypatch, caplog) -> None:
    async def fake_connect(self):  # noqa: ANN001 - 替身签名与被替换方法一致
        return _FakeWS()

    monkeypatch.setattr(vl._PluginSpeechStream, "_connect_ws", fake_connect)
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        ws = await stream._connect_ws()

    assert isinstance(ws, _FakeWS)
    assert any("volc asr ws open" in r.getMessage() for r in caplog.records)


async def test_ws_connect_failure_logs_and_reraises(stream, monkeypatch, caplog) -> None:
    """连不上必须留痕再原样抛出——吞掉异常正是 R3 那种零日志死法的来源。"""

    async def boom(self):  # noqa: ANN001
        raise OSError("ws refused")

    monkeypatch.setattr(vl._PluginSpeechStream, "_connect_ws", boom)
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        with pytest.raises(OSError):
            await stream._connect_ws()

    assert any("volc asr ws failed" in r.getMessage() for r in caplog.records)


async def test_run_logs_start_and_end(stream, monkeypatch, caplog) -> None:
    async def nothing(self):  # noqa: ANN001
        return

    monkeypatch.setattr(vl._PluginSpeechStream, "_run", nothing)
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        await stream._run()

    msgs = [r.getMessage() for r in caplog.records]
    assert any("volc asr stream start" in m for m in msgs)
    assert any("volc asr stream end" in m for m in msgs)


async def test_run_logs_exception_and_reraises(stream, monkeypatch, caplog) -> None:
    async def boom(self):  # noqa: ANN001
        raise RuntimeError("stream died")

    monkeypatch.setattr(vl._PluginSpeechStream, "_run", boom)
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        with pytest.raises(RuntimeError):
            await stream._run()

    assert any("volc asr stream failed" in r.getMessage() for r in caplog.records)
