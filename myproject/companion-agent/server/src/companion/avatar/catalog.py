"""形象发布：后台上传、上线、下线；客户端按角色拉取已上线的最新版本。

流程：上传 zip → 校验（domain/avatar/package.py）→ 存对象存储 → 记一条 draft → 运营上线。
下线后客户端下次同步就看不到；已经下载的本地副本由客户端自己决定是否保留。
同一个 avatar_key 同时只会有一个在线版本：上线新版本时，旧的在线版本自动下线。
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from companion.avatar.package import InvalidPackage, parse_package, valid_avatar_key
from companion.avatar.port import DRAFT, OFFLINE, ONLINE, AvatarRelease, AvatarReleaseStore
from companion.ports.objects import ObjectStore

log = logging.getLogger("companion.avatar")

SIGNED_URL_TTL = 3600


class ReleaseNotFound(LookupError):
    pass


class ReleaseStateError(RuntimeError):
    """当前状态不允许这个操作（例如把已下线的版本直接上线）。"""


class AvatarCatalog:
    def __init__(self, *, store: AvatarReleaseStore, objects: ObjectStore, key_prefix: str = "") -> None:
        self._store = store
        self._objects = objects
        self._prefix = key_prefix

    def _object_key(self, avatar_key: str, version: int) -> str:
        return f"{self._prefix}avatars/{avatar_key}/v{version}.zip"

    async def upload(self, *, avatar_key: str, role_id: str, data: bytes, min_app_version: int = 0) -> AvatarRelease:
        """校验并保存为草稿。包不合法抛 InvalidPackage。"""
        if not valid_avatar_key(avatar_key):
            raise InvalidPackage("avatar_key 只能用小写字母、数字、- 和 _，最长 64 位")
        package = parse_package(data)
        digest = hashlib.sha256(data).hexdigest()
        stored: list[str] = []

        def object_key_for(version: int) -> str:
            key = self._object_key(avatar_key, version)
            stored.append(key)
            return key

        # 先登记（拿到版本号 → 对象 key），再传对象；传失败就把草稿标成下线，不留「有记录没文件」的在线版本。
        release = await self._store.create(
            avatar_key=avatar_key, name=str(package.manifest["name"]), role_id=role_id,
            manifest=package.manifest, object_key_for=object_key_for, size_bytes=len(data), sha256=digest,
            min_app_version=min_app_version)
        try:
            await self._objects.put(key=release.object_key, data=data, content_type="application/zip")
        except Exception:
            await self._store.set_status(release_id=release.id, from_statuses=(DRAFT,), to_status=OFFLINE)
            raise
        return release

    async def list_releases(self, *, avatar_key: str | None = None) -> list[AvatarRelease]:
        return await self._store.list_all(avatar_key=avatar_key)

    async def publish(self, release_id: int) -> AvatarRelease:
        release = await self._store.get(release_id=release_id)
        if release is None:
            raise ReleaseNotFound(release_id)
        if release.status == ONLINE:
            return release
        if release.status not in (DRAFT, OFFLINE):
            raise ReleaseStateError(release.status)
        if not await self._store.set_status(release_id=release_id, from_statuses=(DRAFT, OFFLINE), to_status=ONLINE):
            raise ReleaseStateError("changed concurrently")
        # 同一个 avatar_key 只留一个在线版本
        for other in await self._store.list_all(avatar_key=release.avatar_key):
            if other.id != release_id and other.status == ONLINE:
                await self._store.set_status(release_id=other.id, from_statuses=(ONLINE,), to_status=OFFLINE)
        published = await self._store.get(release_id=release_id)
        assert published is not None
        return published

    async def offline(self, release_id: int) -> AvatarRelease:
        release = await self._store.get(release_id=release_id)
        if release is None:
            raise ReleaseNotFound(release_id)
        if release.status != OFFLINE:
            await self._store.set_status(release_id=release_id, from_statuses=(DRAFT, ONLINE), to_status=OFFLINE)
        offline = await self._store.get(release_id=release_id)
        assert offline is not None
        return offline

    async def for_client(self, *, role_id: str, app_version: int = 0) -> list[dict[str, Any]]:
        """客户端可见的形象：该角色（含不绑定角色的）已上线、且客户端版本够用的最新版本，带短期下载地址。"""
        latest: dict[str, AvatarRelease] = {}
        for release in await self._store.list_online(role_id=role_id):
            if release.min_app_version > app_version:
                continue
            current = latest.get(release.avatar_key)
            if current is None or release.version > current.version:
                latest[release.avatar_key] = release
        out: list[dict[str, Any]] = []
        for release in latest.values():
            url = await self._objects.signed_url(key=release.object_key, ttl_seconds=SIGNED_URL_TTL)
            out.append({"avatar_key": release.avatar_key, "version": release.version, "name": release.name,
                        "role_id": release.role_id or None, "size_bytes": release.size_bytes,
                        "sha256": release.sha256, "manifest": release.manifest, "download_url": url,
                        "url_expires_in": SIGNED_URL_TTL})
        out.sort(key=lambda item: (item["role_id"] is None, item["avatar_key"]))   # 绑定了该角色的排在前面
        return out
