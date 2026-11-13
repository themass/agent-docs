"""每个记忆后端都必须通过规范的一致性检查（docs/chat-agent-memory-spec.md §9.1）。"""

import asyncio
import os

import pytest

from tests.memory_conformance import check_port


def test_in_memory_backend_conforms():
    from companion.agent.memory.fake import InMemoryMemoryPort

    asyncio.run(check_port(InMemoryMemoryPort()))


def test_hub_scoped_client_over_in_memory_conforms():
    from companion.agent.memory.fake import InMemoryMemoryPort
    from memory_hub import AppConfig, MemoryHub

    hub = MemoryHub.from_config([AppConfig("companion")], lambda cfg: InMemoryMemoryPort())
    asyncio.run(check_port(hub.for_app("companion")))


DB_URL = os.environ.get("COMPANION_TEST_DATABASE_URL") or os.environ.get("COMPANION_TEST_MYSQL_URL", "")


@pytest.mark.skipif(not DB_URL, reason="needs COMPANION_TEST_DATABASE_URL (or COMPANION_TEST_MYSQL_URL)")
def test_sql_backend_conforms(memory_schema):
    from sqlalchemy.ext.asyncio import create_async_engine

    from companion.agent.memory.sql import SqlMemoryPort

    async def go():
        engine = create_async_engine(DB_URL, pool_pre_ping=True)
        try:
            await check_port(SqlMemoryPort(engine))
        finally:
            await engine.dispose()

    asyncio.run(go())
