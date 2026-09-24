"""OpenAPI / Swagger metadata for JobCome API docs."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

OPENAPI_TAGS: list[dict[str, str]] = [
    {
        "name": "auth",
        "description": "注册、登录、登出与当前会话上下文（Cookie 鉴权）。",
    },
    {
        "name": "guest",
        "description": "访客会话；上传简历前通常由 `/auth/context` 自动创建。",
    },
    {
        "name": "profiles",
        "description": "简历上传、档案编辑、拔高预览与导出。",
    },
    {
        "name": "agent",
        "description": "DeerFlow Agent 会话与 SSE 消息流。",
    },
    {
        "name": "coach",
        "description": "面试题库、真题归档与模拟面。",
    },
    {
        "name": "jobs",
        "description": "JD 解析与人岗匹配打分。",
    },
]

API_DESCRIPTION = """
JobCome 后端 API（MVP）。

## 鉴权

- 使用 **HttpOnly Cookie**，浏览器请求需带 `credentials: include`。
- Cookie 名称：
  - `jc_session` — 登录用户
  - `jc_guest` — 访客会话
- 在 Swagger UI 中调试：先调用 `GET /auth/context` 或 `POST /auth/login`，浏览器会保存 Set-Cookie，后续请求自动携带。

## 典型流程

1. `GET /auth/context` — 获取访客能力与会话
2. `POST /profiles/upload` — 上传简历（multipart）
3. `PATCH /profiles/{id}` — 核对/修改档案 JSON
4. `GET /profiles/{id}/elevate/preview` — 拔高 HTML 预览
5. `POST /auth/register` 或 `POST /auth/login` — 登录后获得 `export` 能力
6. `POST /profiles/{id}/export` — 导出 PDF / DOCX
"""


def build_openapi_schema(app: FastAPI) -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=API_DESCRIPTION,
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})
    schema["components"]["securitySchemes"]["jc_session"] = {
        "type": "apiKey",
        "in": "cookie",
        "name": "jc_session",
        "description": "登录用户会话 Cookie（`POST /auth/login` 或 `POST /auth/register` 后下发）",
    }
    schema["components"]["securitySchemes"]["jc_guest"] = {
        "type": "apiKey",
        "in": "cookie",
        "name": "jc_guest",
        "description": "访客会话 Cookie（`GET /auth/context` 或上传简历时下发）",
    }
    app.openapi_schema = schema
    return app.openapi_schema


def attach_openapi(app: FastAPI) -> None:
    app.openapi = lambda: build_openapi_schema(app)  # type: ignore[method-assign]
