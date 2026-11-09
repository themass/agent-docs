"""每个记忆后端都必须通过规范的一致性检查（docs/chat-agent-memory-spec.md §9.1）。"""

import asyncio
import os

import pytest

from tests.memory_conformance import check_port


def test_in_memory_backend_conforms():
    from companion.adapters.memory.fake import InMemoryMemoryPort

    asyncio.run(check_port(InMemoryMemoryPort()))


def test_hub_scoped_client_over_in_memory_conforms():
    from companion.adapters.memory.fake import InMemoryMemoryPort
    from memory_hub import AppConfig, MemoryHub

    hub = MemoryHub.from_config([AppConfig("companion")], lambda cfg: InMemoryMemoryPort())
    asyncio.run(check_port(hub.for_app("companion")))


@pytest.mark.skipif(not os.environ.get("COMPANION_TEST_MYSQL_URL"), reason="needs COMPANION_TEST_MYSQL_URL")
def test_mysql_backend_conforms(memory_schema):
    from sqlalchemy.ext.asyncio import create_async_engine

    from companion.adapters.store.mysql.memory import MysqlMemoryPort

    async def go():
        engine = create_async_engine(os.environ["COMPANION_TEST_MYSQL_URL"], pool_pre_ping=True)
        try:
            await check_port(MysqlMemoryPort(engine))
        finally:
            await engine.dispose()

    asyncio.run(go())
