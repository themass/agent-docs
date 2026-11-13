"""形象发布的存储协议。形象包本身在对象存储里，这里只存元数据与上下线状态。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

DRAFT, ONLINE, OFFLINE = "draft", "online", "offline"


@dataclass(frozen=True)
class AvatarRelease:
    id: int
    avatar_key: str
    version: int
    name: str
    role_id: str                 # 空串 = 所有角色
    status: str
    manifest: dict[str, Any]
    object_key: str
    size_bytes: int
    sha256: str
    min_app_version: int
    published_at: datetime | None
    created_at: datetime


class AvatarReleaseStore(Protocol):
    async def create(self, *, avatar_key: str, name: str, role_id: str, manifest: dict[str, Any],
                     object_key_for: Any, size_bytes: int, sha256: str, min_app_version: int) -> AvatarRelease:
        """版本号由存储分配（同一 avatar_key 下自增）；``object_key_for(version)`` 给出该版本的对象 key。"""
        ...

    async def get(self, *, release_id: int) -> AvatarRelease | None: ...

    async def list_all(self, *, avatar_key: str | None = None, limit: int = 100) -> list[AvatarRelease]: ...

    async def set_status(self, *, release_id: int, from_statuses: tuple[str, ...], to_status: str) -> bool:
        """条件更新：当前状态在 ``from_statuses`` 里才改。上线时写 published_at。"""
        ...

    async def list_online(self, *, role_id: str) -> list[AvatarRelease]:
        """上线中的形象：绑定该角色的，加上不绑定角色的（role_id 为空）。"""
        ...
