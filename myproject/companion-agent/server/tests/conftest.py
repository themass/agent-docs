"""测试共享夹具。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def memory_schema():
    """确保 ca_memory_item 存在。alembic upgrade head 幂等，且不 downgrade，避免影响其他模块的 ca_ 表。"""
    url = (os.environ.get("COMPANION_TEST_DATABASE_URL") or os.environ.get("COMPANION_TEST_MYSQL_URL", ""))
    if not url:
        pytest.skip("needs COMPANION_TEST_DATABASE_URL (or COMPANION_TEST_MYSQL_URL)")
    env = {**os.environ, "COMPANION_MYSQL_URL": url, "COMPANION_DATABASE_URL": url, "PYTHONPATH": str(ROOT / "src")}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                   cwd=ROOT, env=env, check=True, capture_output=True)


@pytest.fixture
async def sqlite_engine():
    """内存 SQLite 上建好全部 ca_* 表。不依赖外部数据库，所以这类测试在任何机器上都会真正执行。

    只验证 SQL 逻辑与读写往返；Postgres 专有的行为（锁、timestamptz、JSONB 运算）仍要靠
    COMPANION_TEST_DATABASE_URL 的那批测试。
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    import companion.memory.sql  # noqa: F401 —— 注册 ca_memory_item
    import companion.store.schema as schema

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(schema.metadata.create_all)
    yield engine
    await engine.dispose()
