"""二次元头像生成的端点契约（对端 = Android ``AvatarGenRemote``）。

钉死四件事，全部对着端侧 ``mapStatus`` 的分类跑：

1. 200 的字段形状（``avatar_upload_id`` / ``style`` / ``provider``）与预览复用
   ``GET /v1/uploads/{id}``（Android 不新造读图路径）；
2. 错误分类：401→NOT_LOGGED_IN、422→BAD_IMAGE（源图不存在 / 非本人 / style 非法）、
   429→QUOTA、502→provider 失败（原始错误不外泄）；
3. 每日配额按**尝试**计数（失败也计）；
4. 源图 TTL：到点 sweep 连对象带行删；没到点不动；**上限 24h 夹死**。

测试全程用 fake provider——真实模型未接线（见 ``providers.real_provider``）。
"""

from __future__ import annotations

import asyncio
import io
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from companion.api.http.deps import build_current_user
from companion.api.http.routers.avatar_gen import build_router as build_avatar_gen_router
from companion.api.http.routers.uploads import build_router as build_uploads_router
from companion.db.port import UploadRecord
from companion.service.auth.port import IdentityError
from companion.service.avatar_gen.port import ExpiredSource
from companion.service.avatar_gen.providers import FakeStyleProvider
from companion.service.avatar_gen.service import DEFAULT_DAILY_QUOTA, MAX_SOURCE_TTL, AvatarGenService
from companion.service.uploads.images import normalize_image
from companion.service.uploads.memory_storage import InMemoryObjectStore
from companion.service.uploads.service import UploadService

NOW = datetime(2026, 11, 25, 10, 0)
HEADERS = {"Authorization": "Bearer login-token"}
HEADERS_2 = {"Authorization": "Bearer second-token"}

#: 用户 id → token：owner id 是 BIGINT（与 Java 的 long 对齐），测试里也用数字。
_TOKENS = {"Bearer login-token": "1001", "Bearer second-token": "1002"}


class Auth:
    async def verify(self, authorization):
        user = _TOKENS.get(authorization or "")
        if user is None:
            raise IdentityError("login required")
        return user


class Records:
    """ca_upload 的内存替身（语义对齐 SqlUploadStore 的四个方法）。"""

    def __init__(self) -> None:
        self.rows: dict[str, UploadRecord] = {}

    async def create(self, record: UploadRecord) -> None:
        self.rows[record.id] = record

    async def get_owned(self, *, owner_id: int, upload_id: str) -> UploadRecord | None:
        row = self.rows.get(upload_id)
        return row if row and row.owner_id == owner_id else None

    async def mark_bound(self, *, upload_id: str, actual_size: int) -> None:
        pass

    async def delete_owned(self, *, owner_id: int, upload_id: str) -> None:
        row = self.rows.get(upload_id)
        if row and row.owner_id == owner_id:
            self.rows.pop(upload_id)


class Attempts:
    """AvatarGenAttemptStore 的内存替身（SQL 版另有 test_avatar_gen_sql.py 钉语义）。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self._next = 1

    async def add_attempt(self, *, owner_id: int, source_upload_id: str, source_key: str, style: str,
                          created_at: datetime, expires_at: datetime) -> int:
        row = {"id": self._next, "owner_id": owner_id, "source_upload_id": source_upload_id,
               "source_key": source_key, "result_upload_id": None, "style": style,
               "created_at": created_at, "expires_at": expires_at}
        self._next += 1
        self.rows.append(row)
        return row["id"]

    async def count_recent(self, *, owner_id: int, since: datetime) -> int:
        return sum(1 for r in self.rows if r["owner_id"] == owner_id and r["created_at"] >= since)

    async def attach_result(self, *, attempt_id: int, result_upload_id: str) -> None:
        for r in self.rows:
            if r["id"] == attempt_id:
                r["result_upload_id"] = result_upload_id

    async def result_owned(self, *, owner_id: int, upload_id: str) -> bool:
        return any(r["owner_id"] == owner_id and r["result_upload_id"] == upload_id for r in self.rows)

    async def due_sources(self, *, now: datetime, limit: int) -> list[ExpiredSource]:
        seen: set[str] = set()
        out: list[ExpiredSource] = []
        for r in self.rows:
            if r["expires_at"] is None or r["expires_at"] > now or r["source_upload_id"] in seen:
                continue
            seen.add(r["source_upload_id"])
            out.append(ExpiredSource(upload_id=r["source_upload_id"], owner_id=r["owner_id"],
                                     object_key=r["source_key"]))
            if len(out) >= limit:
                break
        return out

    async def mark_source_purged(self, *, source_upload_id: str) -> None:
        for r in self.rows:
            if r["source_upload_id"] == source_upload_id:
                r["expires_at"] = None


class Avatars:
    def __init__(self) -> None:
        self.ptrs: dict[int, str] = {}

    async def get(self, *, owner_id: int) -> str | None:
        return self.ptrs.get(owner_id)

    async def set(self, *, owner_id: int, upload_id: str) -> None:
        self.ptrs[owner_id] = upload_id

    async def delete(self, *, owner_id: int) -> None:
        self.ptrs.pop(owner_id, None)


class BrokenProvider:
    name = "broken"

    async def generate(self, *, image: bytes, style: str) -> bytes:
        raise RuntimeError("gateway https://secret-inference.internal:8443 exploded")


class Harness:
    """服务 + 两个 router 装到一个 app 上（预览复用 uploads 路由，必须一起挂）。"""

    def __init__(self, *, daily_quota: int = DEFAULT_DAILY_QUOTA, ttl_hours: int = 20,
                 provider=None, objects=None) -> None:
        self.now = NOW
        self.objects = objects or InMemoryObjectStore()
        self.records = Records()
        self.uploads = UploadService(objects=self.objects, records=self.records, normalize=normalize_image,
                                     clock=lambda: self.now.replace(tzinfo=UTC))
        self.attempts = Attempts()
        self.avatars = Avatars()
        self.provider = provider or FakeStyleProvider()
        self.service = AvatarGenService(uploads=self.uploads, attempts=self.attempts, avatars=self.avatars,
                                        provider=self.provider, daily_quota=daily_quota,
                                        source_ttl=timedelta(hours=ttl_hours), clock=lambda: self.now)
        app = FastAPI()
        app.include_router(build_uploads_router(self.uploads, build_current_user(Auth())))
        app.include_router(build_avatar_gen_router(self.service, build_current_user(Auth())))
        self.client = TestClient(app)

    def upload(self, headers: dict = HEADERS) -> str:
        resp = self.client.post("/v1/uploads", content=_png(), headers=headers)
        assert resp.status_code == 201, resp.text
        return resp.json()["upload_id"]

    def generate(self, source_id: str, style: str = "anime", headers: dict = HEADERS):
        return self.client.post("/v1/avatars/generate", headers=headers,
                                json={"source_upload_id": source_id, "style": style})

    def apply(self, avatar_id: str, headers: dict = HEADERS):
        return self.client.post("/v1/avatars/apply", headers=headers, json={"avatar_upload_id": avatar_id})

    def sweep(self) -> dict:
        return asyncio.run(self.service.sweep())

    def object_count(self) -> int:
        return len(self.objects._blobs)  # noqa: SLF001 —— 测试直接看桶，最硬


def _png(size: tuple[int, int] = (640, 480)) -> bytes:
    img = Image.new("RGB", size, (200, 50, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------- 成功链路


def test_generate_returns_contract_shape_and_preview_reuses_uploads():
    h = Harness()
    source = h.upload()
    resp = h.generate(source)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"avatar_upload_id", "style", "provider"}
    assert body["style"] == "anime" and body["provider"] == "fake"
    assert body["avatar_upload_id"] and body["avatar_upload_id"] != source
    # 预览走既有 GET /v1/uploads/{id}（Android 不为头像新开读图路径）
    preview = h.client.get(f"/v1/uploads/{body['avatar_upload_id']}", headers=HEADERS)
    assert preview.status_code == 200 and "url" in preview.json()
    # 生成图与源图是同一条 uploads 存储：两条 ca_upload 行、两个对象
    assert set(h.records.rows) == {source, body["avatar_upload_id"]}


def test_fake_provider_is_deterministic_and_changes_the_image():
    src = _png()
    out1 = asyncio.run(FakeStyleProvider().generate(image=src, style="anime"))
    out2 = asyncio.run(FakeStyleProvider().generate(image=src, style="anime"))
    assert out1 == out2 and out1 != src
    with Image.open(io.BytesIO(out1)) as img:
        assert img.format == "JPEG"


def test_apply_sets_pointer_and_deletes_previous_result():
    h = Harness()
    first = h.generate(h.upload()).json()["avatar_upload_id"]
    assert h.apply(first).status_code == 200
    assert h.avatars.ptrs[1001] == first

    second = h.generate(h.upload()).json()["avatar_upload_id"]
    resp = h.apply(second)
    assert resp.status_code == 200 and resp.json() == {"ok": True}
    assert h.avatars.ptrs[1001] == second
    # 「直到再次更换前保留」：被换掉的那张当场删（行与对象都没了）
    assert first not in h.records.rows
    assert second in h.records.rows


# ------------------------------------------------------------------- 鉴权


def test_missing_or_bad_token_is_401():
    h = Harness()
    assert h.client.post("/v1/avatars/generate", json={"source_upload_id": "x", "style": "anime"}).status_code == 401
    assert h.generate("x", headers={"Authorization": "Bearer nope"}).status_code == 401


# ----------------------------------------------------------------- 422 类


def test_source_missing_or_foreign_or_bad_style_all_422():
    h = Harness()
    own = h.upload()
    foreign = h.upload(headers=HEADERS_2)

    for body in ({"source_upload_id": "01NOPE000000000000000000", "style": "anime"},  # 不存在
                 {"source_upload_id": foreign, "style": "anime"},                      # 不是本人的
                 {"source_upload_id": own, "style": "realistic"},                      # style 未放开
                 {"source_upload_id": "", "style": "anime"}):                          # 缺字段
        resp = h.client.post("/v1/avatars/generate", headers=HEADERS, json=body)
        assert resp.status_code == 422, (body, resp.text)
        # 端侧 mapStatus：422 → BAD_IMAGE，只靠 code 分类，message 不外泄
        assert resp.json()["detail"]["code"] in ("source_not_found", "style_not_allowed")
    assert h.attempts.rows == []  # 进不了生成的请求不占配额


def test_apply_rejects_source_and_foreign_results():
    h = Harness()
    source = h.upload()
    mine = h.generate(source).json()["avatar_upload_id"]

    assert h.apply(source).status_code == 422      # 源图不能直接当头像（会被 TTL 删）
    assert h.apply("01NOPE000000000000000000").status_code == 422
    assert h.apply(mine, headers=HEADERS_2).status_code == 422


# ------------------------------------------------------------------ 配额


def test_daily_quota_returns_429_and_counts_failed_attempts():
    h = Harness(daily_quota=2, provider=BrokenProvider())
    source = h.upload()
    for _ in range(2):
        resp = h.generate(source)
        assert resp.status_code == 502, resp.text
        assert "secret" not in resp.text  # provider 原始错误不外泄
    resp = h.generate(source)
    assert resp.status_code == 429
    assert resp.json()["detail"]["code"].startswith("quota")  # 端侧 code 前缀口径

    # 窗口滚动：一天之后配额恢复
    h.now = NOW + timedelta(hours=24, minutes=1)
    assert h.generate(source).status_code == 502  # 又是 provider 坏，但不再是配额


def test_quota_is_per_user():
    h = Harness(daily_quota=1)
    mine = h.generate(h.upload()).json()["avatar_upload_id"]
    assert h.generate(h.upload()).status_code == 429
    theirs = h.generate(h.upload(headers=HEADERS_2), headers=HEADERS_2)
    assert theirs.status_code == 200 and theirs.json()["avatar_upload_id"] != mine
    assert h.apply(mine).status_code == 200


# ------------------------------------------------------------- TTL 清理


def test_sweep_deletes_expired_source_only():
    h = Harness(ttl_hours=20)
    source = h.upload()
    result = h.generate(source).json()["avatar_upload_id"]
    keys_before = set(h.objects._blobs)  # noqa: SLF001

    h.now = NOW + timedelta(hours=19)
    assert h.sweep()["expired_sources"] == 0          # 还没到 TTL
    assert source in h.records.rows

    h.now = NOW + timedelta(hours=21)
    assert h.sweep()["expired_sources"] == 1
    assert source not in h.records.rows               # ca_upload 行删了
    assert keys_before - set(h.objects._blobs) != set()  # 对象也删了
    assert result in h.records.rows                   # 生成结果不受清理影响
    # 账本行留着（配额窗口与 apply 认领都要它），expires_at 置空不再重复扫
    assert h.attempts.rows and all(r["expires_at"] is None for r in h.attempts.rows)
    assert h.apply(result).status_code == 200
    assert h.sweep()["expired_sources"] == 0          # 幂等


def test_source_ttl_is_capped_at_24h_even_if_configured_longer():
    """隐私口径（端侧文案同句）：源图存活**不超过 24h**。配置调长也必须夹住。"""
    assert MAX_SOURCE_TTL == timedelta(hours=24)
    h = Harness(ttl_hours=72)
    source = h.upload()
    h.generate(source)

    h.now = NOW + timedelta(hours=23)
    assert h.sweep()["expired_sources"] == 0
    h.now = NOW + timedelta(hours=24)
    assert h.sweep()["expired_sources"] == 1
    assert source not in h.records.rows


def test_sweep_survives_object_delete_failure_and_retries():
    class FlakyStore(InMemoryObjectStore):
        def __init__(self):
            super().__init__()
            self.fail_next = True

        async def delete(self, *, key: str) -> None:
            if self.fail_next:
                self.fail_next = False
                raise RuntimeError("tos 503")
            await super().delete(key=key)

    store = FlakyStore()
    h = Harness(ttl_hours=20, objects=store)
    source = h.upload()
    h.generate(source)
    h.now = NOW + timedelta(hours=21)

    assert h.sweep()["expired_sources"] == 0     # 对象删失败：行留着，等下一轮
    assert source in h.records.rows
    assert h.sweep()["expired_sources"] == 1     # 下一轮成功
    assert source not in h.records.rows
