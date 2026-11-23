"""stage-6 热修：checkpointer 须在事件循环里建，不能进 asyncio.to_thread。"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from companion.bootstrap.platform import _checkpointer, build_platform
from companion.config import Settings


@pytest.mark.asyncio
async def test_build_platform_with_injected_checkpoint_bundle_off_thread():
    """模拟 worker._platform：主循环里 _checkpointer，to_thread 里 build_platform 注入。"""
    pool = MagicMock()
    saver = MagicMock(name="AsyncPostgresSaver")
    bundle = (pool, saver)

    settings = Settings(
        _env_file=None,
        companion_mysql_url="postgresql+psycopg://u:p@127.0.0.1:5432/db",
        companion_redis_url="redis://127.0.0.1:6379/0",
        companion_checkpoint_url="postgresql://u:p@127.0.0.1:5432/db",
        companion_qa_enabled=False,
    )
    fake_brain = MagicMock()

    def _build() -> object:
        return build_platform(
            settings,
            brain=fake_brain,
            checkpoint_bundle=bundle,
            profile="voice",
        )

    platform = await asyncio.to_thread(_build)
    assert platform is not None


def test_injected_bundle_skips_fresh_checkpointer_in_build_platform(monkeypatch):
    monkeypatch.setattr(
        "companion.bootstrap.platform._checkpointer",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not build checkpointer in thread")),
    )
    settings = Settings(
        _env_file=None,
        companion_mysql_url="postgresql+psycopg://u:p@127.0.0.1:5432/db",
        companion_redis_url="redis://127.0.0.1:6379/0",
        companion_checkpoint_url="postgresql://u:p@127.0.0.1:5432/db",
        companion_qa_enabled=False,
    )
    fake_brain = MagicMock()
    bundle = (MagicMock(), MagicMock())
    platform = build_platform(
        settings,
        brain=fake_brain,
        checkpoint_bundle=bundle,
        profile="voice",
    )
    assert platform is not None

