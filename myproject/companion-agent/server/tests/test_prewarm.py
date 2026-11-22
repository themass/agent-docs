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
    """
    from companion.api.livekit.prewarm import PREWARM_IMPORTS

    for blamed in ("companion.agent.skills.library", "yaml", "companion.bootstrap.database",
                   "anyio._backends._asyncio"):
        assert blamed in PREWARM_IMPORTS, blamed


def test_prewarm_imports_them_without_calling_anything(tmp_path, monkeypatch):
    """prewarm 只许 import：不许建连接、读远端配置（副作用会被 forkserver 复制）。"""
    from companion.api.livekit import prewarm as mod

    calls: list[str] = []
    monkeypatch.setattr(mod, "PREWARM_IMPORTS", ("json", "base64"))
    real_import = __import__

    def spy(name, *a, **k):
        calls.append(name)
        return real_import(name, *a, **k)

    monkeypatch.setattr("builtins.__import__", spy)
    mod.prewarm()
    assert calls == ["json", "base64"]
