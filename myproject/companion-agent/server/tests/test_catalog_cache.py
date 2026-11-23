"""stage-6：系统角色目录在 job 进程预热一次，接房不再在事件循环里扫 283 个 md。"""

from unittest.mock import MagicMock

import pytest

from companion.agent.roles.catalog import RoleIndex
from companion.bootstrap import catalog_cache
from companion.config import Settings


def _fake_catalog() -> RoleIndex:
    return RoleIndex(divisions=[], roles=[])


@pytest.fixture(autouse=True)
def _clear_catalog_cache():
    catalog_cache.clear_system_catalog_cache_for_tests()
    yield
    catalog_cache.clear_system_catalog_cache_for_tests()


def test_warm_system_catalog_runs_loader_once(monkeypatch):
    calls: list[int] = []

    def fake_load(*_a, **_k):
        calls.append(1)
        return _fake_catalog()

    monkeypatch.setattr(catalog_cache, "load_system_catalog", fake_load)
    first = catalog_cache.warm_system_catalog()
    second = catalog_cache.warm_system_catalog()
    assert first is second
    assert calls == [1]


def test_build_platform_uses_injected_catalog_without_reload(monkeypatch):
    from companion.bootstrap.platform import build_platform

    monkeypatch.setattr(
        "companion.bootstrap.platform.load_system_catalog",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should not reload catalog")),
    )
    settings = Settings(
        _env_file=None,
        companion_mysql_url="postgresql+psycopg://u:p@127.0.0.1:5432/db",
        companion_redis_url="redis://127.0.0.1:6379/0",
        companion_qa_enabled=False,
    )
    fake_brain = MagicMock()
    platform = build_platform(
        settings,
        brain=fake_brain,
        catalog=_fake_catalog(),
        profile="voice",
    )
    assert platform.roles is not None
