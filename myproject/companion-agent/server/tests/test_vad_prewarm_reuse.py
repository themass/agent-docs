"""VAD 模型必须进程级加载一次，不许每个房间在事件循环里重载。

生产证据（2026-11-22 stage-3，voice=main 625596a）：prewarm 修掉冷 import 后，
loop_monitor 改点名 `pathlib.py:1013 open`——**每个新 job 进程接房时 7–23s**
（9.4/10.1/14.7/22.9s 各一笔，task=job_user_entrypoint），位置恰在
`companion joined room` 之前：`build_voice_stack` 每房间调一次 `silero.VAD.load()`，
把 ONNX 模型同步读进内存，冻住整个事件循环。SDK 文档原话：
"This method is blocking… recommended to call this method inside your prewarm
mechanism"，推荐姿势 `proc.userdata["vad"] = silero.VAD.load()`。
"""

from __future__ import annotations

import pytest


def test_build_voice_stack_reuses_preloaded_vad(monkeypatch) -> None:
    """传了预加载 VAD 就绝不许再 load——这是"每房间一次 load"的直接回归。"""
    from companion.bootstrap import voice_stack as vs

    sentinel = object()

    def _boom(*a, **k):  # noqa: ANN003
        raise AssertionError("传入了预加载 VAD，却仍然调用了 silero.VAD.load()")

    monkeypatch.setattr("livekit.plugins.silero.VAD.load", _boom)
    # 绕过 provider 校验只需要走到 VAD 装配；用假的 tts/stt 构造器替换网络侧
    monkeypatch.setattr(vs, "build_tts", lambda cfg, *, voice_id=None: object())
    from companion.service.voice import volcengine_livekit as vl

    monkeypatch.setattr(vl.NewConsoleSTT, "__init__", lambda self, *a, **k: None)

    from livekit.agents import vad as lk_vad

    monkeypatch.setattr(lk_vad, "VAD", type(sentinel))  # isinstance 哨兵放行

    tts, stt, vad = vs.build_voice_stack(
        vs.VoiceStackConfig(enabled=True, provider="volcengine", voice_id="v"), vad=sentinel)
    assert vad is sentinel


def test_build_voice_stack_without_vad_still_loads(monkeypatch) -> None:
    """dev/测试模式没有 userdata：不传 vad 时仍要自己 load（行为回退，不是死路径）。"""
    from companion.bootstrap import voice_stack as vs

    sentinel = object()
    monkeypatch.setattr("livekit.plugins.silero.VAD.load", lambda *a, **k: sentinel)
    monkeypatch.setattr(vs, "build_tts", lambda cfg, *, voice_id=None: object())
    from companion.service.voice import volcengine_livekit as vl

    monkeypatch.setattr(vl.NewConsoleSTT, "__init__", lambda self, *a, **k: None)
    from livekit.agents import vad as lk_vad

    monkeypatch.setattr(lk_vad, "VAD", type(sentinel))

    _tts, _stt, vad = vs.build_voice_stack(
        vs.VoiceStackConfig(enabled=True, provider="volcengine", voice_id="v"))
    assert vad is sentinel


def test_prewarm_stores_vad_in_userdata(monkeypatch) -> None:
    """prewarm 必须把模型放进 job_proc.userdata["vad"]，入口才有得取。"""
    from companion.api.livekit import prewarm as mod

    sentinel = object()
    calls = []

    # 进程级缓存清干净：全量套里别的用例可能已经 load 过，缓存会让本用例
    # 拿到旧模型而不是哨兵（这正是"每进程一次"的另一面）。
    monkeypatch.setattr(mod, "_VAD", None)

    class _FakeVAD:
        @classmethod
        def load(cls, **kw):
            calls.append(kw)
            return sentinel

    import livekit.plugins.silero as silero

    monkeypatch.setattr(silero, "VAD", _FakeVAD)

    class _Proc:
        userdata: dict = {}

    proc = _Proc()
    mod.prewarm(proc)

    assert calls, "prewarm 没有加载 VAD 模型"
    assert proc.userdata.get("vad") is sentinel


def test_build_session_options_forwards_preloaded_vad() -> None:
    """入口层不许把 userdata 里热好的模型丢在半路。"""
    from companion.api.livekit.entrypoint import build_session_options

    seen: dict = {}

    def _factory(**kw):
        seen.update(kw)
        return object(), object(), object()

    sentinel = object()
    build_session_options(mode="voice", voice_factory=_factory, voice_id="v", vad=sentinel)
    assert seen.get("vad") is sentinel


def test_build_session_options_omits_vad_when_absent() -> None:
    """没有 userdata（dev 模式）时不许传 vad=None 进不认识它的旧 factory。"""
    from companion.api.livekit.entrypoint import build_session_options

    seen: dict = {}

    def _factory(**kw):
        seen.update(kw)
        return object(), object(), object()

    build_session_options(mode="voice", voice_factory=_factory, voice_id="v")
    assert "vad" not in seen


def test_preloaded_vad_reads_proc_userdata() -> None:
    """入口必须从 ctx.proc.userdata 里取 prewarm 热好的模型——这是链条的最后一棒。

    少了这一棒，prewarm 与 build_session_options 两头都对，中间照样每房间 load。
    """
    from types import SimpleNamespace

    from companion.api.livekit.entrypoint import _preloaded_vad

    sentinel = object()
    ctx = SimpleNamespace(proc=SimpleNamespace(userdata={"vad": sentinel}))
    assert _preloaded_vad(ctx) is sentinel


def test_preloaded_vad_tolerates_missing_proc() -> None:
    """dev 模式与测试替身没有 proc/userdata：取不到就 None，不许炸。"""
    from types import SimpleNamespace

    from companion.api.livekit.entrypoint import _preloaded_vad

    assert _preloaded_vad(SimpleNamespace()) is None
    assert _preloaded_vad(SimpleNamespace(proc=SimpleNamespace(userdata={}))) is None
