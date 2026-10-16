"""DeerFlow MCP tool interceptors for JC business gates."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from jc.db.session import AsyncSessionLocal
from jc.models.enums import ReviewerStatus
from jc.stores.resume_store import ResumeStore

logger = logging.getLogger(__name__)


def _tool_basename(name: str) -> str:
    if name.startswith("jc_jc_"):
        return name.removeprefix("jc_")
    return name


async def _latest_draft_passed(profile_id: str, elevation_level: str = "elevated") -> bool:
    async with AsyncSessionLocal() as db:
        store = ResumeStore(db)
        draft = await store.get_latest_draft(profile_id, elevation_level=elevation_level)
        if draft is None:
            return False
        status = draft.reviewer_status
        if isinstance(status, ReviewerStatus):
            return status == ReviewerStatus.PASSED
        return str(status).lower() == ReviewerStatus.PASSED.value


def build_apply_pipeline_review_interceptor() -> Any:
    """Block apply_pipeline export until resume_review has passed on latest draft."""

    async def interceptor(request: Any, handler: Any) -> Any:
        name = _tool_basename(str(getattr(request, "name", "") or ""))
        if name != "jc_apply_pipeline":
            return await handler(request)

        profile_id = os.environ.get("JC_MCP_PROFILE_ID")
        if not profile_id:
            return await handler(request)

        args = getattr(request, "args", None) or {}
        elevation_level = str(args.get("elevation_level") or "elevated")
        create_application = args.get("create_application", True)
        export_format = str(args.get("export_format") or "pdf")

        if export_format and create_application is not False:
            try:
                passed = await _latest_draft_passed(profile_id, elevation_level=elevation_level)
            except Exception:
                logger.exception("apply_pipeline review gate check failed")
                passed = False
            if not passed:
                payload = {
                    "status": "blocked",
                    "code": "review_required",
                    "message": (
                        "Export blocked: call jc_resume_review on the latest draft "
                        "and ensure status is passed before jc_apply_pipeline."
                    ),
                }
                return json.dumps(payload, ensure_ascii=False)

        return await handler(request)

    return interceptor
