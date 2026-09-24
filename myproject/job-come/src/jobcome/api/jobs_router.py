"""Job description parse and fit score routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from agentkit.common.trace import get_trace_id
from agentkit.web.auth import Actor, UserActor
from jobcome.api.deps import (
    get_actor,
    get_application_service,
    get_apply_pipeline_service,
    get_job_service,
    require_user,
)
from jobcome.schemas.job import (
    ApplicationResponse,
    ApplyPipelineRequest,
    ApplyPipelineResponse,
    FitScoreRequest,
    FitScoreResponse,
    JobParseRequest,
    JobResponse,
    ParseFromUrlRequest,
)
from jobcome.services.application_service import ApplicationService
from jobcome.services.apply_pipeline_service import ApplyPipelineService
from jobcome.services.jd_fetch_service import JdFetchService
from jobcome.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "/profiles/{profile_id}/parse",
    response_model=JobResponse,
    summary="解析 JD",
    description="粘贴岗位描述，结构化并可选入库。",
)
async def parse_job_description(
    profile_id: Annotated[str, Path(description="档案 ID")],
    body: JobParseRequest,
    actor: Actor = Depends(get_actor),
    jobs: JobService = Depends(get_job_service),
) -> JobResponse:
    return await jobs.parse_jd(profile_id, actor=actor, body=body)


@router.post(
    "/profiles/{profile_id}/parse-url",
    response_model=JobResponse,
    summary="从招聘链接解析 JD",
    description="抓取公开页面正文后走 JD 解析（Scout-lite，无浏览器）。",
)
async def parse_job_from_url(
    profile_id: Annotated[str, Path(description="档案 ID")],
    body: ParseFromUrlRequest,
    actor: Actor = Depends(get_actor),
    jobs: JobService = Depends(get_job_service),
) -> JobResponse:
    text = await JdFetchService().fetch_text(body.url)
    return await jobs.parse_jd(
        profile_id,
        actor=actor,
        body=JobParseRequest(raw_text=text, source_url=body.url, save=body.save),
    )


@router.post(
    "/profiles/{profile_id}/fit",
    response_model=FitScoreResponse,
    summary="人岗匹配打分",
)
async def score_job_fit(
    profile_id: Annotated[str, Path(description="档案 ID")],
    body: FitScoreRequest,
    actor: Actor = Depends(get_actor),
    jobs: JobService = Depends(get_job_service),
) -> FitScoreResponse:
    return await jobs.fit_score(profile_id, actor=actor, body=body)


@router.post(
    "/profiles/{profile_id}/apply-pipeline",
    response_model=ApplyPipelineResponse,
    summary="定向申请流水线",
    description="fit → 按 JD 拔高 → 审稿 → 导出 → 投递归档（等价 ai-job-search /apply）。",
)
async def run_apply_pipeline(
    profile_id: Annotated[str, Path(description="档案 ID")],
    body: ApplyPipelineRequest,
    actor: UserActor = Depends(require_user),
    pipeline: ApplyPipelineService = Depends(get_apply_pipeline_service),
) -> ApplyPipelineResponse:
    return await pipeline.run(
        profile_id,
        actor=actor,
        body=body,
        trace_id=get_trace_id(),
    )


@router.get(
    "/profiles/{profile_id}/{job_id}/prep",
    summary="面试准备包",
    description="返回该岗位的 JD + fit + 档案摘要，供 coach-mock 使用。",
)
async def interview_prep_pack(
    profile_id: Annotated[str, Path(description="档案 ID")],
    job_id: Annotated[str, Path(description="岗位 ID")],
    actor: Actor = Depends(get_actor),
    pipeline: ApplyPipelineService = Depends(get_apply_pipeline_service),
) -> dict:
    return await pipeline.prep_context(profile_id, job_id, actor=actor)


@router.get(
    "/profiles/{profile_id}",
    response_model=list[JobResponse],
    summary="列出已保存岗位",
)
async def list_jobs(
    profile_id: Annotated[str, Path(description="档案 ID")],
    actor: Actor = Depends(get_actor),
    jobs: JobService = Depends(get_job_service),
) -> list[JobResponse]:
    return await jobs.list_jobs(profile_id, actor=actor)


@router.get(
    "/profiles/{profile_id}/applications",
    response_model=list[ApplicationResponse],
    summary="投递归档列表",
)
async def list_applications(
    profile_id: Annotated[str, Path(description="档案 ID")],
    actor: UserActor = Depends(require_user),
    apps: ApplicationService = Depends(get_application_service),
) -> list[ApplicationResponse]:
    return await apps.list_for_profile(profile_id, actor=actor)
