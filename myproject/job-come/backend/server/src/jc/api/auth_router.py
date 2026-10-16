"""Authentication routes."""

from __future__ import annotations

from agentkit.web.auth import UserActor
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from jc.api.cookies import (
    GUEST_COOKIE,
    SESSION_COOKIE,
    clear_guest_cookie,
    clear_session_cookie,
    set_guest_cookie,
    set_session_cookie,
)
from jc.api.deps import get_auth_service, require_user
from jc.exceptions import AppError, AuthError, ConflictError
from jc.schemas.auth import (
    AccountResponse,
    AuthContextResponse,
    AuthSuccessResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    ResolveMergeRequest,
    UpdateAccountRequest,
    VerifyEmailCodeRequest,
    VerifyEmailRequest,
)
from jc.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/context",
    response_model=AuthContextResponse,
    summary="获取当前会话上下文",
    description=(
        "返回访客或登录用户的能力列表、活跃档案 ID。"
        "无 Cookie 时自动创建访客会话并 Set-Cookie。"
    ),
)
async def auth_context(
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
) -> AuthContextResponse:
    session_id = request.cookies.get(SESSION_COOKIE)
    guest_id = request.cookies.get(GUEST_COOKIE)
    actor = None

    if session_id:
        try:
            actor = await auth.resolve_actor(session_id=session_id, guest_session_id=guest_id)
        except AuthError:
            clear_session_cookie(response)

    if actor is None:
        if not guest_id:
            guest_id = await auth.open_guest_session()
            set_guest_cookie(response, guest_id)
        actor = await auth.resolve_actor(session_id=None, guest_session_id=guest_id)

    return await auth.build_context(actor=actor)


@router.post(
    "/register",
    response_model=AuthSuccessResponse,
    summary="注册账号",
    description="创建用户并登录。若请求带访客 Cookie，自动认领访客档案到该账号。",
)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
) -> AuthSuccessResponse:
    guest_id = request.cookies.get(GUEST_COOKIE)
    session_issue, claim = await auth.register(body, guest_session_id=guest_id)
    set_session_cookie(response, session_issue.session_id)
    if claim.merge_conflict is None:
        clear_guest_cookie(response)
    return auth.to_success_response(session_issue, claim)


@router.post(
    "/login",
    response_model=AuthSuccessResponse,
    summary="登录",
    description="邮箱密码登录；可合并当前访客档案。",
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
) -> AuthSuccessResponse:
    guest_id = request.cookies.get(GUEST_COOKIE)
    session_issue, claim = await auth.login(
        body.email,
        body.password,
        guest_session_id=guest_id,
    )
    set_session_cookie(response, session_issue.session_id)
    if claim.merge_conflict is None:
        clear_guest_cookie(response)
    return auth.to_success_response(session_issue, claim)


@router.post("/logout", status_code=204, summary="登出", description="清除登录会话 Cookie。")
async def logout(
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
) -> Response:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        await auth.logout(session_id)
    clear_session_cookie(response)
    return Response(status_code=204)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="忘记密码",
    description="向注册邮箱发送重置链接。无论邮箱是否存在，均返回相同提示，防止枚举。",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    auth: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await auth.request_password_reset(body.email)
    return MessageResponse(message="若该邮箱已注册，我们已发送重置密码邮件，请查收。")


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="重置密码",
    description="使用邮件链接中的 token 设置新密码。",
)
async def reset_password(
    body: ResetPasswordRequest,
    auth: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await auth.reset_password(body.token, body.password)
    return MessageResponse(message="密码已重置，请使用新密码登录。")


@router.get(
    "/account",
    response_model=AccountResponse,
    summary="获取账户设置",
    description="需登录；返回当前账户的资料和个人配置。",
)
async def get_account(
    actor: UserActor = Depends(require_user),
    auth: AuthService = Depends(get_auth_service),
) -> AccountResponse:
    return await auth.get_account(actor.user_id)


@router.patch(
    "/account",
    response_model=AccountResponse,
    summary="更新账户设置",
    description="需登录；仅更新显示名称、界面语言和默认表达力度。邮箱变更不属于 V1。",
)
async def update_account(
    body: UpdateAccountRequest,
    actor: UserActor = Depends(require_user),
    auth: AuthService = Depends(get_auth_service),
) -> AccountResponse:
    return await auth.update_account(actor.user_id, body)


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="验证邮箱",
    description="使用注册确认邮件中的 token 完成邮箱验证。",
)
async def verify_email(
    body: VerifyEmailRequest,
    auth: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await auth.verify_email(body.token)
    return MessageResponse(message="邮箱已验证。")


@router.post(
    "/verify-email-code",
    response_model=MessageResponse,
    summary="使用验证码验证邮箱",
    description="需登录；输入验证邮件中的 4 位数字验证码完成验证。",
)
async def verify_email_code(
    body: VerifyEmailCodeRequest,
    actor: UserActor = Depends(require_user),
    auth: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await auth.verify_email_code(actor.user_id, body.code)
    return MessageResponse(message="邮箱已验证。")


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="重发验证邮件",
    description="需登录；向当前用户邮箱重新发送验证链接和 4 位验证码。",
)
async def resend_verification(
    actor: UserActor = Depends(require_user),
    auth: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await auth.send_email_verification(actor.user_id)
    return MessageResponse(message="验证邮件已发送，请查收。")


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="修改密码",
    description="需登录；验证当前密码后设置新密码。",
)
async def change_password(
    body: ChangePasswordRequest,
    actor: UserActor = Depends(require_user),
    auth: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await auth.change_password(actor.user_id, body.current_password, body.new_password)
    return MessageResponse(message="密码已修改。")


@router.post(
    "/resolve-merge",
    response_model=AuthSuccessResponse,
    summary="解决访客/账号档案冲突",
    description="登录或注册时若双方各有档案，需选择保留访客或账号版本。",
)
async def resolve_merge(
    body: ResolveMergeRequest,
    request: Request,
    response: Response,
    actor: UserActor = Depends(require_user),
    auth: AuthService = Depends(get_auth_service),
) -> AuthSuccessResponse:
    guest_id = request.cookies.get(GUEST_COOKIE)
    claim = await auth.resolve_merge(actor.user_id, body, guest_session_id=guest_id)
    clear_guest_cookie(response)
    user = await auth._users.get_by_id(actor.user_id)
    if user is None:
        raise AuthError("User not found", code="session_invalid")
    return AuthSuccessResponse(
        user=AuthService._to_user_context(user),
        active_profile_id=claim.active_profile_id,
        merge_conflict=None,
    )


def register_exception_handlers(app) -> None:
    @app.exception_handler(AuthError)
    async def auth_error_handler(_request: Request, exc: AuthError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(ConflictError)
    async def conflict_error_handler(_request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"code": exc.code, "message": exc.message})
