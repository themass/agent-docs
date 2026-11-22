"""prewarm 清单的守护测试。

prewarm 失败 = SDK 判进程启动失败并不断重试；清单里一个拼错的模块名就会让
**所有** job 起不来。所以每一项都必须真的可 import——这条在 CI 里跑，比上线后
看 voice.log 便宜得多。
"""

from __future__ import annotations

import importlib


def test_every_prewarm_module_is_importable():
    from companion.api.livekit.prewarm import PREWARM_IMPORTS

    missing = []
    for name in PREWARM_IMPORTS:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - 记录原因而不是中断收集
            missing.append(f"{name}: {exc!r}")
    assert not missing, "\n".join(missing)


def test_prewarm_covers_modules_the_loop_blamed_in_production():
    """2026-11-21/22 生产 voice.log 的 loop-blocked 点名清单。

    新进程接房后第一件事就在事件循环里同步吃冷 import：
    companion.agent.skills.library 12.0s、yaml/scanner 9.5s、
    companion.bootstrap.database 10.9s——同进程里的 recall 0.8s 预算必然超时
    （voice.log 里 facts error=timeout 只出现在新进程）。

    5f1742d 部署后（stage-2，2026-11-22）点名的换成了 psycopg：fork 子进程里
    `importing psycopg_binary.version` 10.4s、`importing psycopg` 19.9s——
    bootstrap.database 只声明了 to_psycopg_conninfo 的工具面，不触发驱动本体。
    """
    from companion.api.livekit.prewarm import PREWARM_IMPORTS

    for blamed in ("companion.agent.skills.library", "yaml", "companion.bootstrap.database",
                   "anyio._backends._asyncio", "psycopg", "psycopg.pq.misc"):
        assert blamed in PREWARM_IMPORTS, blamed


def test_prewarm_imports_them_without_calling_anything(tmp_path, monkeypatch):
    """prewarm 的 import 循环不许夹带别的 import；副作用只许是 VAD load。

    VAD 是有意为之的例外（stage-3 生产：每房间 silero.VAD.load() 冻事件循环
    7–23s，SDK 文档要求放进 prewarm）——单独用替身计数验证，见下一用例。
    """
    from companion.api.livekit import prewarm as mod

    calls: list[str] = []
    monkeypatch.setattr(mod, "PREWARM_IMPORTS", ("json", "base64"))
    monkeypatch.setattr(mod, "_load_vad", lambda: "stub-vad")
    real_import = __import__

    def spy(name, *a, **k):
        calls.append(name)
        return real_import(name, *a, **k)

    monkeypatch.setattr("builtins.__import__", spy)
    mod.prewarm()
    assert calls == ["json", "base64"]


def test_prewarm_loads_vad_once_per_process(monkeypatch):
    """VAD 进程级一次：prewarm 被 forkserver 与 job 进程各调一次，第二次查表。"""
    from companion.api.livekit import prewarm as mod

    monkeypatch.setattr(mod, "_VAD", None)
    loads: list[int] = []

    class _FakeVAD:
        @classmethod
        def load(cls, **kw):
            loads.append(1)
            return "sentinel-vad"

    import livekit.plugins.silero as silero

    orig = silero.VAD
    monkeypatch.setattr(silero, "VAD", _FakeVAD)
    try:
        assert mod._load_vad() == "sentinel-vad"
        assert mod._load_vad() == "sentinel-vad"
    finally:
        silero.VAD = orig
    assert len(loads) == 1
