"""系统角色目录（D §5、T7）：解析校验、语言回退、用户角色的归属与接口。"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.roles.catalog_files import load_system_catalog
from companion.api.http.deps import AllowAllVerifier, build_current_user
from companion.api.http.routers.roles import build_router
from companion.roles.service import RoleForbidden, RoleService
from companion.roles.catalog import CatalogError, negotiate_locale, parse_catalog
from companion.paths import ROLES_CATALOG_DIR

ROOT = ROLES_CATALOG_DIR


def minimal(**role_overrides):
    role = dict(id="academic-x", division="academic", name="X", prompt="p", description="d", vibe="v")
    role.update(role_overrides)
    return {"divisions": [{"id": "academic", "label": "Academic"}], "roles": [role]}


def test_shipped_catalog_has_all_283_roles_and_loads():
    index = load_system_catalog(ROOT, reserved_ids={"linche", "sudai"})
    assert len(index.roles) == 283
    assert index.get("academic-anthropologist") is not None


@pytest.mark.parametrize("bad", [
    dict(id="u_hack"),
    dict(id="Bad Id"),
    dict(id="linche"),
    dict(division="nope"),
    dict(prompt=""),
])
def test_invalid_catalog_entries_are_rejected(bad):
    with pytest.raises(CatalogError):
        parse_catalog(minimal(**bad), None, reserved_ids={"linche"})


def test_duplicate_role_id_is_rejected():
    source = minimal()
    source["roles"].append(dict(source["roles"][0]))
    with pytest.raises(CatalogError):
        parse_catalog(source, None)


def test_overlay_for_unknown_role_is_rejected():
    with pytest.raises(CatalogError):
        parse_catalog(minimal(), {"roles": {"ghost": {"name": "g"}}})


def test_locale_negotiation_prefers_explicit_then_accept_language_then_default():
    assert negotiate_locale("en", "zh-CN") == "en"
    assert negotiate_locale(None, "ar-SA,en;q=0.8") == "ar"
    assert negotiate_locale(None, "fr, en;q=0.5") == "en"
    assert negotiate_locale(None, None) == "zh-CN"


def test_arabic_display_is_english_placeholder_marked_machine_translated():
    index = load_system_catalog(ROOT, reserved_ids={"linche", "sudai"})
    shown = index.display(index.get("academic-anthropologist"), "ar")
    assert shown.machine_translated is True
    assert shown.dir == "rtl"


class RoleStore:
    def __init__(self):
        self.rows = {}

    async def create(self, *, owner_id, public_id, name, tagline, description, prompt, locale):
        r = SimpleNamespace(public_id=public_id, owner_id=owner_id, name=name, tagline=tagline,
                            description=description, prompt=prompt, locale=locale, deleted=False)
        self.rows[public_id] = r
        return r

    async def get_owned(self, *, owner_id, public_id):
        r = self.rows.get(public_id)
        return r if r and r.owner_id == owner_id and not r.deleted else None

    async def list_owned(self, *, owner_id, limit, offset):
        return [r for r in self.rows.values() if r.owner_id == owner_id and not r.deleted][offset:offset + limit]

    async def update(self, *, owner_id, public_id, **fields):
        r = await self.get_owned(owner_id=owner_id, public_id=public_id)
        if r is None:
            return False
        for k, v in fields.items():
            setattr(r, k, v)
        return True

    async def soft_delete(self, *, owner_id, public_id):
        r = await self.get_owned(owner_id=owner_id, public_id=public_id)
        if r is None:
            return False
        r.deleted = True
        return True


@pytest.fixture
def client():
    index = load_system_catalog(ROOT, reserved_ids={"linche", "sudai"})
    app = FastAPI()
    app.include_router(build_router(RoleService(index, RoleStore()), build_current_user(AllowAllVerifier())))
    return TestClient(app)


ME = {"Authorization": "Bearer 7"}
BOB = {"Authorization": "Bearer 8"}


def test_user_roles_are_private_and_system_roles_are_read_only(client):
    created = client.post("/v1/roles", json={"name": "我的助手", "prompt": "你是导师"}, headers=ME)
    assert created.status_code == 201
    rid = created.json()["id"]
    assert rid.startswith("u_")
    assert client.get(f"/v1/roles/{rid}", headers=BOB).status_code == 404
    assert client.put(f"/v1/roles/{rid}", json={"name": "新"}, headers=BOB).status_code == 404
    assert client.put(f"/v1/roles/{rid}", json={"name": "新"}, headers=ME).json()["name"] == "新"
    assert client.put("/v1/roles/academic-anthropologist", json={"name": "x"}, headers=ME).status_code == 403
    assert client.delete("/v1/roles/academic-anthropologist", headers=ME).status_code == 403
    assert client.delete(f"/v1/roles/{rid}", headers=ME).status_code == 204
    assert client.delete(f"/v1/roles/{rid}", headers=ME).status_code == 404


def test_role_prompt_length_is_capped(client):
    assert client.post("/v1/roles", json={"name": "x", "prompt": "p" * 5000}, headers=ME).status_code == 422


def test_role_list_is_paged_and_searchable(client):
    page = client.get("/v1/roles", params={"limit": 2}, headers=ME).json()
    assert page["total"] >= 283 and len(page["items"]) == 2
    hits = client.get("/v1/roles", params={"q": "anthropologist", "limit": 5}, headers=ME).json()
    assert hits["total"] == 1
