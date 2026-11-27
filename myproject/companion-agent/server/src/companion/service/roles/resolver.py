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

from companion.agent.prompt.role_profile import RoleProfile, from_card, from_system_role, from_user_prompt
from companion.service.roles.port import CharacterSourcePort
from companion.agent.skills.port import SkillCatalog
from companion.db.port import RoleStore

log = logging.getLogger("companion.roles")

USER_ROLE_PREFIX = "u_"

# 用户卡能覆盖到 RoleProfile 上的字段——与 service/card/model.py 的 persona 白名单里
# 确实存在于角色层的那几项对齐（voice/boundaries 不在这条链上：音色由 voice_ref 走，
# 边界由输出层走，见各自模块）。
_OVERLAY_FIELDS = frozenset({"name", "description", "personality", "scenario"})


class RoleNotFound(LookupError):
    pass


class RoleProfileResolver:
    def __init__(self, *, catalog: Any, user_roles: RoleStore, characters: CharacterSourcePort | None = None,
                 skills: SkillCatalog | None = None,
                 skill_id_of: Callable[[Any], str | None] | None = None,
                 skill_ids_of: Callable[[Any], list[str]] | None = None,
                 card_overlays: Any = None) -> None:
        self._catalog = catalog              # RoleIndex：get(role_id) -> SystemRole | None
        self._user_roles = user_roles
        self._characters = characters
        self._skills = skills
        # ca_role_card 的生效链（CardService）。角色封装在库里（系统包），用户的微调盖在它
        # 之上：只有陪伴卡走这一步，目录角色与用户自建角色本来就没有「封装」可覆盖。
        self._card_overlays = card_overlays
        # 新接口优先；只给老的单值函数时包成列表，行为与之前一致。
        if skill_ids_of is not None:
            self._skill_ids_of = skill_ids_of
        elif skill_id_of is not None:
            self._skill_ids_of = lambda card: [s] if (s := skill_id_of(card)) else []
        else:
            self._skill_ids_of = None

    async def exists(self, *, role_id: str, owner_id: int) -> bool:
        """这个角色能不能被解析——判据与 resolve 逐条对齐，不另起一套。

        建会话时用：未知 role_id 当场拒绝，而不是存下去后每回合 RoleNotFound。
        （线上曾有旧客户端把占位符 __default__ 当角色 id 发进来，会话建成功了，
        之后每条消息的回合都整轮失败。）
        """
        if role_id.startswith(USER_ROLE_PREFIX):
            return await self._user_roles.get_owned(owner_id=owner_id, public_id=role_id) is not None
        if self._catalog is not None and self._catalog.get(role_id) is not None:
            return True
        if self._characters is None:
            return False
        try:
            await self._characters.load(role_id)
            return True
        except FileNotFoundError:
            return False

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
            card = await self._characters.load(role_id)
        except FileNotFoundError as exc:
            raise RoleNotFound(role_id) from exc
        profile = from_card(card)
        profile = await self._apply_card_overlay(profile, role_id=role_id, owner_id=owner_id)
        method, skills = self._method_for(card)
        if method:
            from dataclasses import replace

            profile = replace(profile, method=method, skills=tuple(skills))
        return profile

    async def _apply_card_overlay(self, profile: RoleProfile, *, role_id: str, owner_id: int) -> RoleProfile:
        """把用户卡（ca_role_card 生效链）盖在系统封装之上。

        只覆盖 persona 白名单里「这个人是谁」的几项；链里的 ``None`` 是「清除该字段」，
        落到角色层就是回到封装值——persona 不能因为用户清了一个字段就变成空段。
        """
        if self._card_overlays is None:
            return profile
        try:
            effective = await self._card_overlays.effective(owner_id=owner_id, role_id=role_id)
        except Exception:  # noqa: BLE001 —— 覆盖链读不到不该让对话开不起来，封装本身够用
            log.warning("card overlay lookup failed", extra={"role_id": role_id})
            return profile
        if effective is None or not effective.fields:
            return profile
        from dataclasses import replace

        changes = {field: value for field, value in effective.fields.items()
                   if field in _OVERLAY_FIELDS and value}
        return replace(profile, **changes) if changes else profile

    def _method_for(self, card: Any) -> tuple[str, list[str]]:
        """返回 (方法层文本, 实际用到的 skill id)。"""
        if self._skills is None or self._skill_ids_of is None:
            return "", []
        skill_ids = self._skill_ids_of(card)
        try:
            # 空列表也 compose：常驻 skill（陪伴底线）对每张陪伴卡都生效
            text = self._skills.compose(skill_ids)
        except Exception:  # noqa: BLE001 —— skill 缺失不该让对话开不起来
            log.warning("skill compose failed", extra={"skills": skill_ids})
            return "", []
        selected = getattr(self._skills, "selected_ids", None)
        return text, (list(selected(skill_ids)) if selected else list(skill_ids))
