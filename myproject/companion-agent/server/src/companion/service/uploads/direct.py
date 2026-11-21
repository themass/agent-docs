"""客户端直传（ADR-011 同款时序）：sign → 客户端 PUT 直进桶 → 发消息时绑定校验。

字节不再穿过应用服务器。服务端只签发「单 key、只能写、10 分钟」的 PUT 凭证，
并在消息真正引用这个 key 时做归属校验 + HEAD 复核——**归属校验，不是内容校验**：

- key 必须是我们签给这个 owner 的（查签发记录）；
- 必须在有效期内、没被别人绑过；
- HEAD 一次：对象真的存在、实际字节数不超场景上限（presigned PUT 约束不了
  Content-Length，超大只能在绑定时拒收，这是 ADR-011 §7.3 的既定取舍）。

绑定成功后直接写进既有的 ``ca_upload``（size 用 HEAD 的实际值），
回合水合（``turn_runner._load_images`` 按 upload_id 走 ``get_owned`` + ``read_bytes``）
对直传完全无感——这是复用的全部意义：模型看图的链路一行不用改。
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from companion.db.port import UploadRecord
from companion.agent.util.ids import new_ulid

UPLOAD_TTL = timedelta(minutes=10)
SCENE_CHAT_IMAGE = "chat-image"
SCENE_CHAT_VIDEO = "chat-video"
# 场景与 Content-Type 成对放开：chat-image 拿不到视频凭证，反之亦然——否则视频能绕过
# 自己的上限从 2 MiB 的图片场景挤进来。视频只收 MP4（Android 系统相机与分享的标准容器；
# 用户拍出的 mov 由客户端选片时拒收或转封装，是客户端的事，这里不养第二套容器白名单）。
SCENE_CONTENT_TYPES: dict[str, dict[str, str]] = {
    SCENE_CHAT_IMAGE: {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"},
    SCENE_CHAT_VIDEO: {"video/mp4": "mp4"},
}
# 直传聊天图上限 2 MiB（ADR-011 §4）：客户端 ImageCompressor 的目标是 800 KiB，这是安全边际。
# 与中转通道的 8 MiB 不同是有意的——中转有 normalize_image 兜底，直传没有服务端重编码。
MAX_BYTES_CHAT_IMAGE = 2 * 1024 * 1024
# 直传聊天视频上限 25 MiB（P2-13 拍板：不转码直传，约 1080p 30~60 秒）。
# **与客户端上限同值写死**：presigned PUT 约束不了字节数，绑定时的 HEAD 复核是唯一闸门，
# 两边不同值就会出现「客户端放行、发消息时 413」的幽灵失败。
MAX_BYTES_CHAT_VIDEO = 25 * 1024 * 1024

_KEY_SEGMENT = re.compile(r"^[a-z0-9-]{1,32}$")


class DirectRejected(ValueError):
    """签发/绑定阶段的拒绝。路由层按 code 翻译成 4xx。"""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _env_prefix(key_prefix: str) -> str:
    """ca_upload 的 key 前缀（生产 ``companion/``、qa ``companion-qa/``）在这里就是环境段。

    job-come 的 key 形如 ``jc/<env>/uploads/...``；我们没有 jc，前缀纪律照搬：
    ``<env>/uploads/<owner>/<scene>/<yyyy>/<mm>/<dd>/<id>.<ext>``。qa 与 prod 共用一个桶，
    环境段必须原样保留——合并成一个段会让两个环境的对象互相踩。
    """
    env = key_prefix.strip("/").split("/", 1)[0]
    return env if _KEY_SEGMENT.fullmatch(env) else "dev"


class DirectUploadService:
    def __init__(self, *, objects: Any, records, limits: dict[str, int] | None = None,
                 clock=lambda: datetime.now(UTC), key_prefix: str = "") -> None:
        self._objects = objects
        self._records = records  # SqlUploadStore：create / get_owned
        self._limits = limits or {SCENE_CHAT_IMAGE: MAX_BYTES_CHAT_IMAGE, SCENE_CHAT_VIDEO: MAX_BYTES_CHAT_VIDEO}
        self._clock = clock
        self._env = _env_prefix(key_prefix)

    # ---------------------------------------------------------------- 签发

    async def sign(self, *, owner_id: int, scene: str, content_type: str, size_bytes: int) -> dict:
        limit = self._limits.get(scene)
        if limit is None:
            raise DirectRejected("SCENE_NOT_ALLOWED")
        # 白名单按场景查：类型表与上限表同源，改场景不会漏改另一张表
        types = SCENE_CONTENT_TYPES.get(scene, {})
        if content_type not in types:
            raise DirectRejected("CONTENT_TYPE_NOT_ALLOWED")
        if not (0 < size_bytes <= limit):
            raise DirectRejected("SIZE_NOT_ALLOWED")
        now = self._clock()
        key_id = new_ulid()
        ext = types[content_type]
        key = (f"{self._env}/uploads/{owner_id}/{scene}/{now:%Y/%m/%d}/{key_id}.{ext}")
        url = await self._objects.presigned_put(key=key, content_type=content_type,
                                                ttl_seconds=int(UPLOAD_TTL.total_seconds()))
        expires_at = now + UPLOAD_TTL
        # 预登记：key 即 upload_id（ULID，26 位，ca_upload.id 原样放得下）。
        # size=0 表示还没绑定；绑定时的 UPDATE 会写入 HEAD 的实际值。
        await self._records.create(UploadRecord(
            id=key_id, owner_id=owner_id, object_key=key, mime=content_type,
            size=0, width=0, height=0, referenced=False, created_at=now))
        return {
            "upload_id": key_id,
            "object_key": key,
            "upload": {
                "method": "PUT",
                "url": url,
                "headers": {"Content-Type": content_type},
                "expires_at": expires_at.isoformat(),
            },
            "limits": {"max_size_bytes": limit, "put_ttl_seconds": int(UPLOAD_TTL.total_seconds())},
        }

    # ---------------------------------------------------------------- 绑定

    async def bind(self, *, owner_id: int, upload_id: str) -> None:
        """消息引用前调用；不过就抛 DirectRejected，路由翻译成 4xx。

        两类行共用 ca_upload，按 key 形状分流：
        - **中转行**（``<prefix>uploads/<owner>/<id>.jpg``）：字节早已入库、size 已填真值，
          没有绑定这一步——直接返回。
        - **直传行**：未过期、未绑定、HEAD 存在且不超限才放行（job-come ADR-011 §6-C 同口径）。
          成功把 size 从预登记的 0 更新为 HEAD 实际值（=已消费）；已消费再绑是 409
          （key 不复用是 §7.2 写死的契约）。
        """
        record = await self._records.get_owned(owner_id=owner_id, upload_id=upload_id)
        if record is None:
            # 不存在、不是你的、或者格式不对：一律同一句话，不区分（防枚举）
            raise DirectRejected("KEY_NOT_FOUND")
        scene = self._scene_of(record.object_key)
        if not scene:
            return  # 中转通道的行：不属于直传的状态机
        if record.size > 0:
            raise DirectRejected("KEY_ALREADY_BOUND")
        if self._clock() > record.created_at + UPLOAD_TTL:
            raise DirectRejected("KEY_EXPIRED")
        actual = await self._objects.head_size(key=record.object_key)
        if actual is None:
            raise DirectRejected("KEY_NOT_PUT")
        if actual > self._limits.get(scene, MAX_BYTES_CHAT_IMAGE):
            raise DirectRejected("SIZE_NOT_ALLOWED")
        await self._records.mark_bound(upload_id=upload_id, actual_size=actual)

    def _scene_of(self, object_key: str) -> str:
        # <env>/uploads/<owner>/<scene>/<yyyy>/<mm>/<dd>/<id>.<ext>
        parts = object_key.split("/")
        return parts[3] if len(parts) >= 8 and parts[:2] == [self._env, "uploads"] else ""
