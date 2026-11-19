"""剧本房 RtcAdapter：Memory 记录顺序 / 等待超时；LiveKit 冒烟（mock，不连 SFU）。"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_rtc_module_keeps_livekit_imports_local():
    """livekit 只能出现在 rtc.py 内部，不能泄漏到其它 script_room 模块顶层。"""
    root = Path(__file__).resolve().parents[1] / "src" / "companion" / "devtools" / "script_room"
    rtc_path = root / "rtc.py"
    assert rtc_path.is_file(), "rtc.py must exist"

    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(n == "livekit" or n.startswith("livekit.") for n in names):
                assert path.name == "rtc.py", f"livekit import leaked into {path.name}"


@pytest.mark.asyncio
async def test_memory_records_publish_order():
    from companion.devtools.script_room.rtc import MemoryRtcAdapter

    rtc = MemoryRtcAdapter()
    await rtc.connect("wss://example", "tok")
    await rtc.publish_data("ctl", b"hello")
    await rtc.publish_pcm(b"\x00\x01", sample_rate=16000)
    await rtc.publish_data("cue", b"bye")

    assert rtc.published == [
        ("data", "ctl", b"hello"),
        ("pcm", b"\x00\x01", 16000),
        ("data", "cue", b"bye"),
    ]
    await rtc.close()


@pytest.mark.asyncio
async def test_memory_wait_timeout_without_remote():
    from companion.devtools.script_room.rtc import MemoryRtcAdapter

    rtc = MemoryRtcAdapter()
    await rtc.connect("wss://example", "tok")
    with pytest.raises(asyncio.TimeoutError):
        await rtc.wait_for_remote_participant(timeout=0.05)
    await rtc.close()


@pytest.mark.asyncio
async def test_memory_wait_succeeds_after_simulate_join():
    from companion.devtools.script_room.rtc import MemoryRtcAdapter

    rtc = MemoryRtcAdapter()
    await rtc.connect("wss://example", "tok")

    async def _join_soon():
        await asyncio.sleep(0.01)
        rtc.simulate_remote_join()

    asyncio.create_task(_join_soon())
    await rtc.wait_for_remote_participant(timeout=1.0)
    await rtc.close()


@pytest.mark.asyncio
async def test_livekit_adapter_smoke_mocked():
    """构造 / 方法存在 / 调用路径正确；不连真实 SFU。"""
    from companion.devtools.script_room.rtc import LiveKitRtcAdapter, RtcAdapter

    adapter = LiveKitRtcAdapter()
    assert isinstance(adapter, RtcAdapter)
    for name in ("connect", "publish_data", "publish_pcm", "wait_for_remote_participant", "close"):
        assert callable(getattr(adapter, name))

    fake_room = MagicMock()
    fake_room.connect = AsyncMock()
    fake_room.disconnect = AsyncMock()
    fake_lp = MagicMock()
    fake_lp.publish_data = AsyncMock()
    fake_lp.publish_track = AsyncMock(return_value=MagicMock())
    fake_room.local_participant = fake_lp
    fake_room.remote_participants = {}

    # Room.on is a decorator used as @room.on("participant_connected")
    def _on(event_name: str):
        def _decorator(fn):
            return fn

        return _decorator

    fake_room.on = _on

    fake_source = MagicMock()
    fake_source.capture_frame = AsyncMock()
    fake_track = MagicMock()

    with (
        patch("companion.devtools.script_room.rtc.rtc.Room", return_value=fake_room),
        patch("companion.devtools.script_room.rtc.rtc.AudioSource", return_value=fake_source),
        patch(
            "companion.devtools.script_room.rtc.rtc.LocalAudioTrack.create_audio_track",
            return_value=fake_track,
        ),
        patch("companion.devtools.script_room.rtc.rtc.AudioFrame") as FakeFrame,
        patch("companion.devtools.script_room.rtc.rtc.TrackPublishOptions", return_value=MagicMock()),
        patch("companion.devtools.script_room.rtc.rtc.TrackSource") as FakeSource,
    ):
        FakeSource.SOURCE_MICROPHONE = "mic"
        FakeFrame.return_value = MagicMock()

        await adapter.connect("wss://lk", "jwt")
        fake_room.connect.assert_awaited_once_with("wss://lk", "jwt")

        await adapter.publish_data("ctl", b"{}")
        fake_lp.publish_data.assert_awaited_once_with(b"{}", topic="ctl")

        await adapter.publish_pcm(b"\x00\x00", sample_rate=16000)
        fake_lp.publish_track.assert_awaited()
        fake_source.capture_frame.assert_awaited()

        await adapter.close()
        fake_room.disconnect.assert_awaited()


@pytest.mark.asyncio
async def test_memory_set_data_handler_receives_simulated_data():
    from companion.devtools.script_room.rtc import MemoryRtcAdapter

    rtc = MemoryRtcAdapter()
    seen: list[tuple] = []

    async def _handler(payload: bytes, topic: str, identity: str, kind: str) -> None:
        seen.append((payload, topic, identity, kind))

    rtc.set_data_handler(_handler)
    await rtc.connect("wss://example", "tok")
    await rtc.simulate_data(b"x", topic="cmp.ctl", publisher_identity="phone", publisher_kind="STANDARD")
    assert seen == [(b"x", "cmp.ctl", "phone", "STANDARD")]
    await rtc.close()


@pytest.mark.asyncio
async def test_memory_simulate_data_without_handler_is_noop():
    from companion.devtools.script_room.rtc import MemoryRtcAdapter

    rtc = MemoryRtcAdapter()
    await rtc.simulate_data(b"x", topic="cmp.ctl", publisher_identity="phone")


@pytest.mark.asyncio
async def test_livekit_adapter_data_received_reaches_handler():
    """真房 data_received（同步回调）→ 异步 handler，字段映射与 protocol_bridge.attach 一致。"""
    from types import SimpleNamespace

    from companion.devtools.script_room.rtc import LiveKitRtcAdapter

    adapter = LiveKitRtcAdapter()
    seen: list[tuple] = []

    async def _handler(payload: bytes, topic: str, identity: str, kind: str) -> None:
        seen.append((payload, topic, identity, kind))

    adapter.set_data_handler(_handler)

    callbacks: dict[str, object] = {}
    fake_room = MagicMock()
    fake_room.connect = AsyncMock()
    fake_room.disconnect = AsyncMock()
    fake_room.remote_participants = {}

    def _on(event_name: str, callback=None):
        if callback is not None:
            callbacks[event_name] = callback
            return callback

        def _decorator(fn):
            callbacks[event_name] = fn
            return fn

        return _decorator

    fake_room.on = _on

    with patch("companion.devtools.script_room.rtc.rtc.Room", return_value=fake_room):
        await adapter.connect("wss://lk", "jwt")

    assert "data_received" in callbacks
    packet = SimpleNamespace(
        data=b"hello-bytes",
        topic="cmp.ctl",
        participant=SimpleNamespace(identity="phone-1", kind=SimpleNamespace(name="STANDARD")),
    )
    callbacks["data_received"](packet)
    await asyncio.sleep(0.01)
    assert seen == [(b"hello-bytes", "cmp.ctl", "phone-1", "STANDARD")]
    await adapter.close()
