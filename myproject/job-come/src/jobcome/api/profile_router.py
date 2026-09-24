"""Profile routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Path, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from agentkit.web.auth import Actor, UserActor
from jobcome.api.cookies import set_guest_cookie
from jobcome.api.deps import (
    get_actor,
    get_auth_service,
    get_profile_service,
    get_resume_service,
    require_capability,
    require_user,
)
from jobcome.exceptions import ForbiddenError, NotFoundError
from jobcome.models.enums import ElevationLevel
from jobcome.schemas.profile import (
    ProfileConfirmResponse,
    ProfileListResponse,
    ProfileResponse,
    ProfileUpdateRequest,
)
from jobcome.schemas.resume import (
    ElevatePreviewResponse,
    ExportJobResponse,
    ExportRequest,
    LocalizeRequest,
    ResumeDraftResponse,
)
from jobcome.services.auth_service import AuthService
from jobcome.services.profile_ingest_service import IngestValidationError
from jobcome.services.profile_service import ProfileService
from jobcome.services.resume_service import ResumeService

router = APIRouter(prefix="/profiles", tags=["profiles"])


async def get_actor_with_guest(
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
    actor: Actor = Depends(get_actor),
) -> Actor:
    if actor.kind == "guest" and actor.guest_session_id == "gst_anonymous":
        guest_id, _created = await auth.ensure_guest_session(None)
        set_guest_cookie(response, guest_id)
        from agentkit.web.auth import GuestActor

        return GuestActor(guest_session_id=guest_id)
    return actor


@router.get(
    "",
    response_model=ProfileListResponse,
    summary="列出我的档案",
)
async def list_profiles(
    actor: UserActor = Depends(require_user),
    profiles: ProfileService = Depends(get_profile_service),
) -> ProfileListResponse:
    data = await profiles.list_profiles(actor=actor)
    return ProfileListResponse(**data)


@router.post(
    "",
    response_model=ProfileResponse,
    summary="新建空白档案",
)
async def create_profile(
    actor: UserActor = Depends(require_user),
    profiles: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    return await profiles.create_profile(actor=actor)


@router.post(
    "/upload",
    response_model=ProfileResponse,
    summary="上传简历",
    description="支持 PDF / Word / 图片。解析后创建档案草稿，原文件存入 TOS。",
)
async def upload_profile(
    file: Annotated[
        UploadFile,
        File(description="简历文件（.pdf / .doc / .docx / .png / .jpg / .webp）"),
    ],
    background_tasks: BackgroundTasks,
    actor: Actor = Depends(get_actor_with_guest),
    profiles: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    raw = await file.read()
    result = await profiles.upload(
        actor=actor,
        file_name=file.filename or "resume.pdf",
        content_type=file.content_type,
        raw_bytes=raw,
    )
    from jobcome.tasks import prepare_resume_tracks

    background_tasks.add_task(prepare_resume_tracks, result.id, "conservative")
    return result


@router.get(
    "/{profile_id}",
    response_model=ProfileResponse,
    summary="获取档案详情",
    description="返回档案 JSON payload、版本号与解析来源信息。",
)
async def get_profile(
    profile_id: Annotated[str, Path(description="档案 ID，形如 prof_xxx")],
    actor: Actor = Depends(get_actor),
    profiles: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    return await profiles.get(profile_id, actor=actor)


@router.patch(
    "/{profile_id}",
    response_model=ProfileResponse,
    summary="更新档案草稿",
    description="提交完整 `payload`；可选 `expected_version` 做乐观锁。",
)
async def update_profile(
    profile_id: Annotated[str, Path(description="档案 ID")],
    body: ProfileUpdateRequest,
    actor: Actor = Depends(get_actor),
    profiles: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    return await profiles.update(profile_id, actor=actor, body=body)


@router.post(
    "/{profile_id}/confirm",
    response_model=ProfileConfirmResponse,
    summary="确认档案",
    description="用户核对无误后锁定档案版本，供后续拔高/导出使用。",
)
async def confirm_profile(
    profile_id: Annotated[str, Path(description="档案 ID")],
    background_tasks: BackgroundTasks,
    actor: Actor = Depends(get_actor),
    profiles: ProfileService = Depends(get_profile_service),
) -> ProfileConfirmResponse:
    result = await profiles.confirm(profile_id, actor=actor)
    from jobcome.tasks import prepare_resume_tracks

    background_tasks.add_task(prepare_resume_tracks, result.id, "elevated")
    return result


@router.post(
    "/{profile_id}/reopen",
    response_model=ProfileResponse,
    summary="退回修改",
    description="将已确认档案退回草稿状态，以便继续编辑核对。",
)
async def reopen_profile(
    profile_id: Annotated[str, Path(description="档案 ID")],
    actor: Actor = Depends(get_actor),
    profiles: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    return await profiles.reopen(profile_id, actor=actor)


@router.post(
    "/{profile_id}/activate",
    response_model=ProfileResponse,
    summary="切换当前活跃档案",
)
async def activate_profile(
    profile_id: Annotated[str, Path(description="档案 ID")],
    actor: UserActor = Depends(require_user),
    profiles: ProfileService = Depends(get_profile_service),
) -> ProfileResponse:
    return await profiles.activate_profile(profile_id, actor=actor)


@router.get(
    "/{profile_id}/export/review",
    summary="导出前 reviewer 预检",
)
async def export_review(
    profile_id: Annotated[str, Path(description="档案 ID")],
    elevation_level: Annotated[
        ElevationLevel,
        Query(description="优化档位"),
    ] = ElevationLevel.ELEVATED,
    locale: Annotated[str, Query(description="zh-CN | en-US | zh-en")] = "zh-CN",
    draft_id: Annotated[str | None, Query(description="指定已有优化稿；空则按 locale 回退最新稿")] = None,
    actor: UserActor = Depends(require_user),
    resumes: ResumeService = Depends(get_resume_service),
) -> dict:
    return await resumes.review_for_export(
        profile_id,
        actor=actor,
        elevation_level=elevation_level.value,
        locale=locale,
        draft_id=draft_id,
    )


@router.post(
    "/{profile_id}/elevate",
    response_model=ResumeDraftResponse,
    summary="生成拔高草稿",
    description="根据档案生成简历拔高草稿并持久化。",
)
async def elevate_profile(
    profile_id: Annotated[str, Path(description="档案 ID")],
    elevation_level: Annotated[
        ElevationLevel,
        Query(description="拔高档位：conservative（保守）| standard（标准）| elevated（拔高）"),
    ] = ElevationLevel.ELEVATED,
    locale: Annotated[str, Query(description="zh-CN | en-US | zh-en")] = "zh-CN",
    job_id: Annotated[str | None, Query(description="按该岗位关键词拔高")] = None,
    actor: Actor = Depends(require_capability("elevate_preview")),
    resumes: ResumeService = Depends(get_resume_service),
) -> ResumeDraftResponse:
    return await resumes.elevate(
        profile_id,
        actor=actor,
        elevation_level=elevation_level.value,
        locale=locale,
        job_id=job_id,
    )


@router.get(
    "/{profile_id}/elevate/preview",
    response_model=ElevatePreviewResponse,
    summary="拔高 HTML 预览",
    description="返回拔高后的 HTML 与 draft 元数据，供前端 iframe 展示。",
)
async def elevate_preview(
    profile_id: Annotated[str, Path(description="档案 ID")],
    elevation_level: Annotated[
        ElevationLevel,
        Query(description="拔高档位：conservative | standard | elevated"),
    ] = ElevationLevel.ELEVATED,
    locale: Annotated[str, Query(description="zh-CN | en-US | zh-en")] = "zh-CN",
    job_id: Annotated[str | None, Query(description="按该岗位关键词拔高")] = None,
    actor: Actor = Depends(require_capability("elevate_preview")),
    resumes: ResumeService = Depends(get_resume_service),
) -> ElevatePreviewResponse:
    return await resumes.preview(
        profile_id,
        actor=actor,
        elevation_level=elevation_level.value,
        locale=locale,
        job_id=job_id,
    )


@router.get(
    "/{profile_id}/resume-tracks",
    summary="中/英/双语稿状态",
)
async def list_resume_tracks(
    profile_id: Annotated[str, Path(description="档案 ID")],
    elevation_level: Annotated[
        ElevationLevel,
        Query(description="优化档位"),
    ] = ElevationLevel.ELEVATED,
    actor: Actor = Depends(require_capability("elevate_preview")),
    resumes: ResumeService = Depends(get_resume_service),
) -> dict:
    return await resumes.list_tracks(
        profile_id, actor=actor, elevation_level=elevation_level.value
    )


@router.post(
    "/{profile_id}/localize",
    summary="重译展示层并生成中英稿",
)
async def localize_profile(
    profile_id: Annotated[str, Path(description="档案 ID")],
    body: LocalizeRequest = Body(default_factory=LocalizeRequest),
    actor: Actor = Depends(get_actor),
    resumes: ResumeService = Depends(get_resume_service),
) -> dict:
    return await resumes.localize(
        profile_id, actor=actor, source_locale=body.source_locale
    )


@router.post(
    "/{profile_id}/export",
    response_model=ExportJobResponse,
    summary="导出简历",
    description="需登录。生成 PDF 或 DOCX，上传 TOS 后返回下载链接。",
)
async def export_profile(
    profile_id: Annotated[str, Path(description="档案 ID")],
    body: ExportRequest,
    actor: UserActor = Depends(require_user),
    resumes: ResumeService = Depends(get_resume_service),
) -> ExportJobResponse:
    return await resumes.export(profile_id, actor=actor, body=body)


@router.get(
    "/exports/{export_id}",
    response_model=ExportJobResponse,
    summary="查询导出任务",
    description="根据导出任务 ID 获取状态与下载 URL。",
)
async def get_export_job(
    export_id: Annotated[str, Path(description="导出任务 ID，形如 expj_xxx")],
    actor: UserActor = Depends(require_user),
    resumes: ResumeService = Depends(get_resume_service),
) -> ExportJobResponse:
    return await resumes.get_export(export_id, actor=actor)


def register_profile_exception_handlers(app) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(_request: Request, exc: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(IngestValidationError)
    async def ingest_validation_handler(
        _request: Request,
        exc: IngestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"code": "invalid_upload", "message": str(exc)},
        )
