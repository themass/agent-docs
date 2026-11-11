"""把角色 id 解析成提示词用的 RoleProfile（三个来源，见 domain/roles/profile.py）。

- ``u_`` 前缀：用户自建角色（存储里只有一段提示词）；
- 目录角色：系统目录（283 个）；
- 其余：陪伴角色卡（SillyTavern V2/V3，可能带世界书与 skill）。

解析每回合都做，不缓存：角色卡和 skill 都可能被改动，缓存会让改动表现成「改了没生效」。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from companion.domain.roles.profile import RoleProfile, from_card, from_system_role, from_user_prompt
from companion.ports.roles import CharacterSourcePort
from companion.ports.skills import SkillCatalog
from companion.ports.store import RoleStore

log = logging.getLogger("companion.roles")

USER_ROLE_PREFIX = "u_"


class RoleNotFound(LookupError):
    pass


class RoleProfileResolver:
    def __init__(self, *, catalog: Any, user_roles: RoleStore, characters: CharacterSourcePort | None = None,
                 skills: SkillCatalog | None = None,
                 skill_id_of: Callable[[Any], str | None] | None = None) -> None:
        self._catalog = catalog              # RoleIndex：get(role_id) -> SystemRole | None
        self._user_roles = user_roles
        self._characters = characters
        self._skills = skills
        self._skill_id_of = skill_id_of

    async def resolve(self, *, role_id: str, owner_id: int, locale: str = "zh-CN") -> RoleProfile:
        if role_id.startswith(USER_ROLE_PREFIX):
            record = await self._user_roles.get_owned(owner_id=owner_id, public_id=role_id)
            if record is None:
                raise RoleNotFound(role_id)
            return from_user_prompt(role_id=role_id, name=record.name, prompt=record.prompt)

        system = self._catalog.get(role_id) if self._catalog is not None else None
        if system is not None:
            return from_system_role(system, locale=locale)

        if self._characters is None:
            raise RoleNotFound(role_id)
        try:
            card = self._characters.load(role_id)
        except FileNotFoundError as exc:
            raise RoleNotFound(role_id) from exc
        profile = from_card(card)
        method = self._method_for(card)
        if method:
            from dataclasses import replace

            profile = replace(profile, method=method)
        return profile

    def _method_for(self, card: Any) -> str:
        if self._skills is None or self._skill_id_of is None:
            return ""
        skill_id = self._skill_id_of(card)
        if not skill_id:
            return ""
        try:
            return self._skills.compose([skill_id])
        except Exception:  # noqa: BLE001 —— skill 缺失不该让对话开不起来
            log.warning("skill compose failed", extra={"skill": skill_id})
            return ""
