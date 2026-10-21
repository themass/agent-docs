"""Preview-specific configuration for the shared request progress stream."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from jc.services.operation_progress import report, stream_operation  # report remains a public import

logger = logging.getLogger(__name__)
STAGES = (
    ("read", "读取最新档案与写作选项"),
    ("generate", "生成内容并保留已确认文字"),
    ("save", "保存预览稿"),
    ("render", "渲染预览"),
    ("audit", "检查内容覆盖与篇幅"),
)


def stream_preview(service: Any, profile_id: str, *, timeout_seconds: float = 240,
                   heartbeat_seconds: float = 10, **kwargs: Any) -> AsyncIterator[bytes]:
    async def rollback() -> None:
        await service._db.rollback()

    return stream_operation(lambda: service.preview(profile_id, **kwargs), profile_id,
                            rollback_db=rollback, operation="preview", label="预览生成", log=logger,
                            timeout_seconds=timeout_seconds, heartbeat_seconds=heartbeat_seconds)
