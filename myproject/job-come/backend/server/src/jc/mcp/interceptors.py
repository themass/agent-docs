"""Compatibility entry point for existing DeerFlow extension configurations.

Review is advisory for HTTP and MCP alike (TECH-API export review contract).
The old interceptor inspected the latest draft before the pipeline created its
job-bound draft, and incorrectly coupled review to application registration.
Keep the factory importable for deployed configs, but leave ownership, artifact
validation and persistence to the business services that hold the actual draft.
"""

from __future__ import annotations

from typing import Any


def build_apply_pipeline_review_interceptor() -> Any:
    """Do not reintroduce a model-review blocker ahead of the export service."""

    async def interceptor(request: Any, handler: Any) -> Any:
        return await handler(request)

    return interceptor
