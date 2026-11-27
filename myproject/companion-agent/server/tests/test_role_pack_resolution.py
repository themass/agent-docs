"""角色封装落库后的解析优先级（提示词真正读的那一段）。

顺序是刻意的：**库里的系统包 → 文件兜底 → 用户自己的角色卡覆盖**。
用户卡（ca_role_card）盖在系统封装之上，所以「她是谁」在服务端库里，
而「这个用户想微调的部分」仍在用户自己的行里——两者不会互相顶掉。
"""

import pytest

from companion.agent.roles.card import CharacterCard
from companion.service.roles.resolver import RoleNotFound, RoleProfileResolver


class Catalog:
    def get(self, _role_id):
        return None


class UserRoles:
    async def get_owned(self, *, owner_id, public_id):
        return None


def _card(name: str, description: str = "系统封装的人设") -> CharacterCard:
    card = CharacterCard(id="linche", name=name, description=description,
                         personality="直接、务实", tagline="成长教练")
    card.voice_ref = {"provider": "volcengine", "voice_id": "pack_voice"}
    return card


class Source:
    """异步角色卡来源替身：命中给卡，未命中抛 FileNotFoundError（与真源同口径）。"""

    def __init__(self, cards: dict[str, CharacterCard]):
        self._cards = cards
        self.asked: list[str] = []

    async def load(self, character_id: str) -> CharacterCard:
        self.asked.append(character_id)
        if character_id not in self._cards:
            raise FileNotFoundError(character_id)
        return self._cards[character_id]


class Overlays:
    """ca_role_card 生效链的替身（真实现是 CardService.effective）。"""

    def __init__(self, by_owner: dict[tuple[int, str], dict]):
        self._by_owner = by_owner
        self.asked: list[tuple[int, str]] = []

    async def effective(self, *, owner_id: int, role_id: str):
        self.asked.append((owner_id, role_id))
        fields = self._by_owner.get((owner_id, role_id))
        if fields is None:
            return None
        return type("Eff", (), {"role_id": role_id, "version": 3, "fields": fields})()


def _resolver(source: Source, overlays: Overlays | None = None) -> RoleProfileResolver:
    return RoleProfileResolver(catalog=Catalog(), user_roles=UserRoles(),
                               characters=source, card_overlays=overlays)


# ---- 系统封装来自库 -----------------------------------------------------------

async def test_persona_fields_come_from_the_packed_card():
    r = _resolver(Source({"linche": _card("林澈")}))
    profile = await r.resolve(role_id="linche", owner_id=1001)
    assert profile.name == "林澈"
    assert profile.description == "系统封装的人设"
    assert profile.personality == "直接、务实"
    assert profile.source == "companion"


async def test_unknown_role_is_still_role_not_found():
    r = _resolver(Source({}))
    with pytest.raises(RoleNotFound):
        await r.resolve(role_id="ghost", owner_id=1001)


async def test_exists_uses_the_same_source_as_resolve():
    src = Source({"linche": _card("林澈")})
    r = _resolver(src)
    assert await r.exists(role_id="linche", owner_id=1001) is True
    assert await r.exists(role_id="ghost", owner_id=1001) is False
    assert src.asked == ["linche", "ghost"]


# ---- 用户卡覆盖盖在封装之上 ---------------------------------------------------

async def test_user_card_overlay_replaces_persona_fields_last():
    """用户改过 description：模型看到的 description 是用户那份，没改的仍是封装那份。"""
    overlays = Overlays({(1001, "linche"): {"description": "用户微调过的人设"}})
    r = _resolver(Source({"linche": _card("林澈")}), overlays)
    profile = await r.resolve(role_id="linche", owner_id=1001)
    assert profile.description == "用户微调过的人设"
    assert profile.personality == "直接、务实"      # 没覆盖的字段不动
    assert profile.name == "林澈"


async def test_overlay_is_per_owner():
    overlays = Overlays({(1001, "linche"): {"description": "只属于 1001 的微调"}})
    r = _resolver(Source({"linche": _card("林澈")}), overlays)
    other = await r.resolve(role_id="linche", owner_id=2002)
    assert other.description == "系统封装的人设"


async def test_cleared_field_falls_back_to_the_pack_value():
    """覆盖链里的 null = 清除该字段，不是把 persona 置空——清除后回到封装值。"""
    overlays = Overlays({(1001, "linche"): {"name": None}})
    r = _resolver(Source({"linche": _card("林澈")}), overlays)
    assert (await r.resolve(role_id="linche", owner_id=1001)).name == "林澈"


async def test_no_overlays_means_no_extra_lookups_when_service_absent():
    r = _resolver(Source({"linche": _card("林澈")}))
    profile = await r.resolve(role_id="linche", owner_id=1001)
    assert profile.description == "系统封装的人设"


async def test_overlay_without_a_packed_card_is_still_role_not_found():
    """用户卡是覆盖层，不是角色本体：库和文件都没有这个角色就仍然解析失败。"""
    overlays = Overlays({(1001, "ghost"): {"description": "无本体"}})
    r = _resolver(Source({}), overlays)
    with pytest.raises(RoleNotFound):
        await r.resolve(role_id="ghost", owner_id=1001)
