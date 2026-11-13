"""角色服务（D §5.3）：系统目录与用户自建角色合并成一个列表，按权限过滤。

- 系统角色：所有人可见，只读。修改/删除返回 RoleForbidden（→ 403）。
- 自建角色：仅本人可见、可改、可删；别人的与不存在的一律 None（→ 404，不泄露存在性）。
- 自建角色 id 形如 u_<ULID>，永远不与系统 id 冲突（D §3.2）。
"""

from __future__ import annotations

from typing import Any

from companion.agent.util.ids import new_ulid
from companion.agent.roles.catalog import (
    MAX_PROMPT_CHARS,
    USER_ROLE_PREFIX,
    RTL_LOCALES,
    RoleIndex,
    SystemRole,
)
from companion.db.port import RoleRecord, RoleStore

MAX_USER_ROLES_LISTED = 1000
MAX_NAME_CHARS = 40
MAX_DESCRIPTION_CHARS = 280


class RoleForbidden(PermissionError):
    """对系统角色做修改或删除。"""


class RoleService:
    def __init__(self, index: RoleIndex, store: RoleStore) -> None:
        self._index = index
        self._store = store

    @property
    def index(self) -> RoleIndex:
        return self._index

    async def list_roles(self, *, owner_id: int, division: str | None, q: str | None, featured: bool,
                         mine: bool, locale: str, limit: int, offset: int) -> dict[str, Any]:
        system: list[dict[str, Any]] = []
        if not mine:
            system = [self._system_json(r, locale)
                      for r in self._index.search(division=division, q=q, featured=featured)]
        user: list[dict[str, Any]] = []
        if not division and not featured:
            rows = await self._store.list_owned(owner_id=owner_id, limit=MAX_USER_ROLES_LISTED, offset=0)
            user = [self._user_json(r, locale) for r in rows if _matches(q, r.name, r.description)]
        merged = system + user
        return {
            "items": merged[offset: offset + limit],
            "total": len(merged),
            "limit": limit,
            "offset": offset,
            "locale": locale,
            "dir": _dir(locale),
        }

    async def divisions(self, *, locale: str) -> list[dict[str, Any]]:
        return [
            {"id": d.id, "label": self._index.division_label(d, locale), "icon": d.icon, "color": d.color,
             "count": self._index.division_count(d.id), "locale": locale, "dir": _dir(locale)}
            for d in self._index.divisions
        ]

    async def get(self, *, owner_id: int, role_id: str, locale: str) -> dict[str, Any] | None:
        if role_id.startswith(USER_ROLE_PREFIX):
            record = await self._store.get_owned(owner_id=owner_id, public_id=role_id)
            return self._user_json(record, locale) if record else None
        role = self._index.get(role_id)
        return self._system_json(role, locale) if role else None

    async def create(self, *, owner_id: int, name: str, description: str, prompt: str,
                     locale: str) -> dict[str, Any]:
        _check_user_fields(name, description, prompt)
        public_id = USER_ROLE_PREFIX + new_ulid()
        record = await self._store.create(owner_id=owner_id, public_id=public_id, name=name,
                                          tagline="", description=description, prompt=prompt, locale=locale)
        return self._user_json(record, locale)

    async def update(self, *, owner_id: int, role_id: str, locale: str, **fields: Any) -> dict[str, Any] | None:
        if not role_id.startswith(USER_ROLE_PREFIX):
            if self._index.get(role_id) is not None:
                raise RoleForbidden("system roles are read-only")
            return None
        allowed = {k: v for k, v in fields.items() if v is not None}
        if "name" in allowed or "description" in allowed or "prompt" in allowed:
            _check_user_fields(allowed.get("name", "x"), allowed.get("description", ""),
                               allowed.get("prompt", "x"))
        if not await self._store.update(owner_id=owner_id, public_id=role_id, **allowed):
            return None
        record = await self._store.get_owned(owner_id=owner_id, public_id=role_id)
        return self._user_json(record, locale) if record else None

    async def delete(self, *, owner_id: int, role_id: str) -> bool:
        if not role_id.startswith(USER_ROLE_PREFIX):
            if self._index.get(role_id) is not None:
                raise RoleForbidden("system roles cannot be deleted")
            return False
        return await self._store.soft_delete(owner_id=owner_id, public_id=role_id)

    # ---- 序列化 ----

    def _system_json(self, role: SystemRole, locale: str) -> dict[str, Any]:
        shown = self._index.display(role, locale)
        return {"id": role.id, "kind": "system", "division": role.division, "name": shown.name,
                "description": shown.description, "vibe": shown.vibe, "emoji": role.emoji,
                "color": role.color, "featured": role.featured, "locale": shown.locale,
                "dir": shown.dir, "machine_translated": shown.machine_translated}

    def _user_json(self, record: RoleRecord, locale: str) -> dict[str, Any]:
        return {"id": record.public_id, "kind": "user", "division": None, "name": record.name,
                "description": record.description, "vibe": record.tagline, "emoji": "", "color": "",
                "featured": False, "locale": record.locale, "dir": _dir(record.locale),
                "machine_translated": False}


def _check_user_fields(name: str, description: str, prompt: str) -> None:
    if not name.strip() or len(name) > MAX_NAME_CHARS:
        raise ValueError(f"name must be 1..{MAX_NAME_CHARS} characters")
    if len(description) > MAX_DESCRIPTION_CHARS:
        raise ValueError(f"description must be at most {MAX_DESCRIPTION_CHARS} characters")
    if not prompt.strip() or len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError(f"prompt must be 1..{MAX_PROMPT_CHARS} characters")


def _matches(q: str | None, *fields: str) -> bool:
    if not q:
        return True
    needle = q.strip().lower()
    return any(needle in f.lower() for f in fields)


def _dir(locale: str) -> str:
    return "rtl" if locale in RTL_LOCALES else "ltr"
