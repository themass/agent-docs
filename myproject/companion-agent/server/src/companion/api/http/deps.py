"""调用方身份解析。

服务端只信凭据，不信请求体：真实部署里 ``Authorization`` 是平台签发的
JWT / session token，由 ``CredentialVerifier`` 的实现验签后给出 user_id。

``AllowAllVerifier`` 只为本地跑通链路存在——它把 Bearer 里的字符串直接当 user_id。
**生产必须替换**（``create_app(verifier=...)``），否则任何人改个头就能变成别人。
"""

from typing import Annotated, Protocol


from companion.ports.auth import AuthUnavailable, CredentialVerifier, IdentityError, parse_bearer


class AllowAllVerifier:
    """开发用，不验签。生产替换掉它。"""

    def __init__(self, default_user_id: str = "dev-user") -> None:
        self._default_user_id = default_user_id

    async def verify(self, authorization: str | None) -> str:
        return parse_bearer(authorization) or self._default_user_id


def build_current_user(verifier: CredentialVerifier):
    """把 verifier 包成 FastAPI 依赖。

    fastapi 在这里才导入，本模块在没装 fastapi 的环境（测试 venv）仍可导入。
    本文件不放 ``from __future__ import annotations``：``Header()`` 是局部名，
    推迟求值会让 FastAPI 去模块全局找它而报 NameError。
    """
    from fastapi import Header, HTTPException

    async def current_user(
        authorization: Annotated[str | None, Header()] = None,
    ) -> str:
        try:
            return await verifier.verify(authorization)
        except IdentityError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthUnavailable as exc:
            raise HTTPException(status_code=503, detail="auth temporarily unavailable") from exc

    return current_user
