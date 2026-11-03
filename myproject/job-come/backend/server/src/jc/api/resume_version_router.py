"""Resume versions: list the drafts a user has, view one, delete one."""

from __future__ import annotations

from typing import Annotated

from agentkit.web.auth import UserActor
from fastapi import APIRouter, Depends, Path, Response
from fastapi.responses import HTMLResponse

from jc.api.deps import get_db, get_profile_service
from jc.api.deps import require_user
from jc.schemas.resume_version import ResumeVersionListResponse
from jc.services.profile_service import ProfileService
from jc.services.resume_version_service import ResumeVersionService

router = APIRouter(prefix="/resume-versions", tags=["resume-versions"])


def _service(db=Depends(get_db), profiles: ProfileService = Depends(get_profile_service)) -> ResumeVersionService:
    return ResumeVersionService(db, profiles)


@router.get("", response_model=ResumeVersionListResponse, summary="我的简历版本（按档案分组）")
async def list_versions(
    actor: UserActor = Depends(require_user),
    versions: ResumeVersionService = Depends(_service),
) -> ResumeVersionListResponse:
    return ResumeVersionListResponse(**await versions.list_grouped(actor=actor))


@router.get(
    "/{draft_id}/html",
    response_class=HTMLResponse,
    summary="查看某个版本的简历（按保存的内容渲染，不调用模型）",
)
async def view_version(
    draft_id: Annotated[str, Path(description="版本 ID，形如 rdft_xxx")],
    actor: UserActor = Depends(require_user),
    versions: ResumeVersionService = Depends(_service),
) -> HTMLResponse:
    html = await versions.render_html(draft_id, actor=actor)
    # The content is the user's own, but the response is still sandboxed: it must not run
    # script or reach the app's origin if anything in the text were ever to slip through.
    return HTMLResponse(html, headers={"Content-Security-Policy": "sandbox"})


@router.delete(
    "/{draft_id}",
    status_code=204,
    summary="删除一个版本，连同它导出的文件",
)
async def delete_version(
    draft_id: Annotated[str, Path(description="版本 ID，形如 rdft_xxx")],
    actor: UserActor = Depends(require_user),
    versions: ResumeVersionService = Depends(_service),
) -> Response:
    await versions.delete(draft_id, actor=actor)
    return Response(status_code=204)
