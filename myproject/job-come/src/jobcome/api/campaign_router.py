"""Campaign progress routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from agentkit.web.auth import Actor
from jobcome.api.deps import get_actor, get_campaign_service
from jobcome.schemas.job import CampaignStatsResponse
from jobcome.services.campaign_service import CampaignService

router = APIRouter(prefix="/campaign", tags=["campaign"])


@router.get(
    "/profiles/{profile_id}",
    response_model=CampaignStatsResponse,
    summary="战役进度与 fit 校准",
)
async def campaign_stats(
    profile_id: Annotated[str, Path(description="档案 ID")],
    actor: Actor = Depends(get_actor),
    campaign: CampaignService = Depends(get_campaign_service),
) -> CampaignStatsResponse:
    return await campaign.get_stats(profile_id, actor=actor)


@router.post(
    "/profiles/{profile_id}/jobs/{job_id}/tag",
    response_model=CampaignStatsResponse,
    summary="标记练手/目标岗位",
)
async def tag_job(
    profile_id: Annotated[str, Path(description="档案 ID")],
    job_id: Annotated[str, Path(description="岗位 ID")],
    tag: str = Query(description="warmup | target"),
    actor: Actor = Depends(get_actor),
    campaign: CampaignService = Depends(get_campaign_service),
) -> CampaignStatsResponse:
    return await campaign.tag_job(profile_id, job_id, actor=actor, tag=tag)
