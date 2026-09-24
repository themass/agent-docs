"""Profile ↔ JD fit scoring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jobcome.config import settings
from jobcome.llm.router import get_llm_router
from jobcome.models.enums import FitRecommendation
from jobcome.schemas.job import FitScoreResponse, JDParseResult
from jobcome.schemas.profile_payload import ProfilePayload

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "ingest" / "fit_score.md"
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
        if not settings.job_come_llm_enabled:
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
        response = await router.acompletion(
            "flash",
            messages=[
                {"role": "system", "content": self._system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"profile": profile.model_dump(mode="json"), "jd": jd.model_dump(mode="json")},
                        ensure_ascii=False,
                    )[:50_000],
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        data = json.loads(router.content_from_response(response))
        return fit_response_from_llm(data)
