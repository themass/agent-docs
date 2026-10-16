"""Async database session."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from jc.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    # Verify pooled connections before reuse and retire them before a remote MySQL idle timeout.
    pool_pre_ping=True,
    pool_recycle=settings.jc_db_pool_recycle_seconds,
    pool_timeout=settings.jc_db_pool_timeout_seconds,
    connect_args={"connect_timeout": settings.jc_db_connect_timeout_seconds},
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield one request session without letting a broken cleanup reset the HTTP connection."""
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        try:
            await session.close()
        except SQLAlchemyError:
            # A remote MySQL connection can disappear while a slow LLM operation is running.
            # Preserve the endpoint error/response instead of replacing it with a cleanup traceback.
            logger.warning("Discarding broken MySQL session during request cleanup", exc_info=True)
            try:
                await session.invalidate()
            except SQLAlchemyError:
                logger.warning("Unable to invalidate broken MySQL session", exc_info=True)


async def release_db_connection(session: AsyncSession) -> None:
    """End the current read-only transaction before a slow model call.

    Resume generation, resume review and JD parsing each run for minutes. Holding the
    pooled MySQL connection across that window lets a remote server time the socket out,
    which surfaces as a reset API connection instead of a usable response.

    This is a connection-lifetime concern, not an atomicity one: nothing is written
    before the call, so a rollback only discards the read snapshot. Callers must
    re-load any ORM object they still need afterwards -- the identity map survives but
    the rows behind it are no longer attached to a live transaction.
    """
    await session.rollback()
