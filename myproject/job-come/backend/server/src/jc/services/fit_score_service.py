"""Profile ↔ JD fit scoring."""

from __future__ import annotations

import json
import logging
from typing import Any

from jc.config import settings
from jc.domain.fit_evidence import verify_requirement_evidence
from jc.domain.profile_context import material_profile
from jc.exceptions import AppError
from jc.llm.call_context import llm_context
from jc.llm.router import get_llm_router
from jc.models.enums import FitRecommendation
from jc.paths import prompt_file
from jc.schemas.job import FitScoreResponse, JDParseResult
from jc.schemas.profile_payload import ProfilePayload

logger = logging.getLogger(__name__)

_PROMPT_PATH = prompt_file("ingest", "fit_score.md")
_DIM_KEYS = ("match", "target", "comp", "culture", "red_flags")
_LEGIT = {"high", "caution", "suspicious"}


def fit_response_from_llm(data: dict[str, Any], *, job_id: str | None = None) -> FitScoreResponse:
    rec = data.get("recommendation", "caution")
    if rec not in {FitRecommendation.GO, FitRecommendation.CAUTION, FitRecommendation.NO}:
        rec = FitRecommendation.CAUTION
    raw_dims = data.get("dimensions") or {}
    dimensions: dict[str, int] = {}
    if isinstance(raw_dims, dict):
        for key in _DIM_KEYS:
            if key in raw_dims:
                try:
                    dimensions[key] = max(0, min(100, int(raw_dims[key])))
                except (TypeError, ValueError):
                    continue
    legit = data.get("legitimacy")
    if legit not in _LEGIT:
        legit = None
    hints = [str(h).strip() for h in (data.get("elevate_hints") or []) if str(h).strip()]
    return FitScoreResponse(
        job_id=job_id,
        score=int(data.get("score", 50)),
        recommendation=rec,
        gaps=[str(g) for g in (data.get("gaps") or [])],
        blockers=[str(b) for b in (data.get("blockers") or [])],
        summary=data.get("summary"),
        elevate_hints=hints,
        dimensions=dimensions,
        legitimacy=legit,
    )


class FitScoreService:
    def __init__(self) -> None:
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def score(
        self,
        *,
        profile: ProfilePayload,
        jd: JDParseResult,
    ) -> FitScoreResponse:
        if not settings.jc_llm_enabled:
            return FitScoreResponse(
                job_id=None,
                score=60,
                recommendation="caution",
                gaps=["LLM 未启用，请人工核对匹配度"],
                blockers=[],
                summary="开启 LLM 后可得到完整匹配报告；仍可按该岗位优化简历。",
                elevate_hints=["对照职位关键词改写已有经历要点，不编造新公司或业绩数字"],
            )

        router = get_llm_router()

        def validate(response: Any) -> FitScoreResponse:
            data = json.loads(router.content_from_response(response))
            result = fit_response_from_llm(data)
            return result.model_copy(
                update={
                    "requirement_evidence": verify_requirement_evidence(
                        data.get("requirement_evidence") or [],
                        profile,
                        jd,
                    )
                }
            )

        request_data = json.dumps(
            {"profile": material_profile(profile), "jd": jd.model_dump(mode="json")},
            ensure_ascii=False,
        )
        logger.info(
            "profile_context task=fit_score input_chars=%d budget_chars=100000", len(request_data)
        )
        if len(request_data) > 100_000:
            # Never silently remove evidence or submit an invalid, sliced JSON document.
            raise AppError(
                "岗位匹配材料超过处理上限；请缩小职位描述或整理重复材料后重试。",
                code="fit_input_too_large",
            )
        # Validated inside the call so a 200 carrying unparseable JSON fails
        # over to the next endpoint instead of becoming a 500.
        return await router.acompletion(
            "flash",
            log_context=llm_context("fit_score"),
            messages=[
                {"role": "system", "content": self._system_prompt},
                {
                    "role": "user",
                    "content": request_data,
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            response_validator=validate,
        )
