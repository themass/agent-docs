"""后台任务进程入口（O §1、P §3.1）。独立进程，不在 API 进程里起循环。

用法：python -m companion.worker_jobs    （需要 COMPANION_MYSQL_URL）
当前注册的任务见 app/jobs/handlers.py；其余 kind 入队后会被置 dead，不会静默丢弃。
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket

from companion.adapters.store.mysql.jobs import MysqlJobStore
from companion.app.jobs.handlers import audit_trim, confirmation_expire
from companion.app.jobs.worker import JobWorker


async def main() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from companion.adapters.store.mysql.repositories import MysqlConfirmationStore, MysqlToolCallStore

    url = os.environ["COMPANION_MYSQL_URL"]
    engine = create_async_engine(url, pool_pre_ping=True)
    confirmations = MysqlConfirmationStore(engine)
    audit = MysqlToolCallStore(engine)
    handlers = {
        "confirmation.expire": confirmation_expire(confirmations),
        "audit.trim": audit_trim(audit),
    }
    owner = f"{socket.gethostname()}:{os.getpid()}"
    worker = JobWorker(store=MysqlJobStore(engine), handlers=handlers, owner=owner)
    logging.basicConfig(level=os.environ.get("COMPANION_LOG_LEVEL", "INFO"))
    try:
        await worker.run_forever()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
