"""Auth and context API schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    email_verified: bool


class UserContext(UserPublic):
    display_name: str | None = None


class AuthContextResponse(BaseModel):
    actor: str
    user: UserContext | None = None
    capabilities: list[str]
    active_profile_id: str | None = None
    merge_conflict: dict | None = None


class AuthSuccessResponse(BaseModel):
    user: UserContext
    active_profile_id: str | None = None
    merge_conflict: MergeConflictResponse | None = None


class GuestSessionResponse(BaseModel):
    guest_session_id: str


class RegisterRequest(BaseModel):
    email: EmailStr = Field(description="注册邮箱")
    password: str = Field(min_length=8, max_length=128, description="密码，至少 8 位")
    display_name: str | None = Field(default=None, max_length=128, description="显示名称（可选）")


class LoginRequest(BaseModel):
    email: EmailStr = Field(description="登录邮箱")
    password: str = Field(description="密码")


class MergeConflictProfileSummary(BaseModel):
    id: str
    contact_name: str | None = None
    updated_at: str


class MergeConflictResponse(BaseModel):
    guest_profile: MergeConflictProfileSummary
    account_profile: MergeConflictProfileSummary


class ResolveMergeRequest(BaseModel):
    choice: str = Field(
        pattern="^(keep_guest|keep_account)$",
        description="`keep_guest` 保留访客档案；`keep_account` 保留账号原档案",
    )


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(description="注册邮箱")


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256, description="邮件中的重置 token")
    password: str = Field(min_length=8, max_length=128, description="新密码，至少 8 位")


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256, description="邮件中的验证 token")


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(description="当前密码")
    new_password: str = Field(min_length=8, max_length=128, description="新密码，至少 8 位")


class MessageResponse(BaseModel):
    message: str
