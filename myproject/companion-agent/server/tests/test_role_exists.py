"""RoleProfileResolver.exists：建会话时的角色存在性判据。

判据必须与 resolve() 同源——这条测试钉的就是「resolve 能成功的，exists 必须说在；
resolve 会抛 RoleNotFound 的，exists 必须说不在」，两边不能各长一套。
"""

import pytest

from companion.service.roles.resolver import RoleNotFound, RoleProfileResolver


class Catalog:
    def __init__(self, ids):
        self._ids = set(ids)

    def get(self, role_id):
        return object() if role_id in self._ids else None


class Cards:
    def __init__(self, ids):
        self._ids = set(ids)

    def load(self, character_id):
        if character_id not in self._ids:
            raise FileNotFoundError(f"character not found: {character_id}")
        return {"meta": {"name": character_id}}


class UserRoles:
    def __init__(self, owned):
        self._owned = set(owned)

    async def get_owned(self, *, owner_id, public_id):
        return object() if public_id in self._owned and str(owner_id) == "1001" else None


def _resolver(**kw):
    kw.setdefault("catalog", Catalog(["linche"]))
    kw.setdefault("characters", Cards(["card_a"]))
    kw.setdefault("user_roles", UserRoles(["u_mine"]))
    return RoleProfileResolver(**kw)


@pytest.mark.parametrize("role_id,expected", [
    ("linche", True),        # 目录角色
    ("card_a", True),        # 角色卡
    ("u_mine", True),        # 当前用户的自建角色
    ("__default__", False),  # 线上事故里那个占位符
    ("u_someone_elses", False),  # 别人的自建角色（按 owner 隔离）
])
async def test_exists_agrees_with_what_resolve_can_do(role_id, expected):
    r = _resolver()
    assert await r.exists(role_id=role_id, owner_id=1001) is expected
    # 反向：exists 说在的，resolve 必须走到查角色之后的环节（哪怕替身喂的卡形不完整，
    # 抛别的错也算「角色找到了」）；exists 说不在的，resolve 必须正好抛 RoleNotFound。
    try:
        await r.resolve(role_id=role_id, owner_id=1001)
        not_found = False
    except RoleNotFound:
        not_found = True
    except Exception:
        not_found = False
    assert not_found is (not expected)


async def test_user_role_visibility_follows_owner():
    """同一个 u_ id，主人查得到、别人查不到——不能因为 exists 把隔离放掉。"""
    r = _resolver()
    assert await r.exists(role_id="u_mine", owner_id=1001) is True
    assert await r.exists(role_id="u_mine", owner_id=2002) is False


async def test_no_character_source_still_answers_catalog_and_user_roles():
    """离线装配没有角色卡来源：目录与自建仍能判，卡片角色判为不在（与 resolve 一致）。"""
    r = RoleProfileResolver(catalog=Catalog(["linche"]), user_roles=UserRoles(["u_mine"]), characters=None)
    assert await r.exists(role_id="linche", owner_id=1001) is True
    assert await r.exists(role_id="card_a", owner_id=1001) is False
