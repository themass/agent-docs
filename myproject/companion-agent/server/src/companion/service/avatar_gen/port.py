"""二次元头像生成的端口与纯规则（契约见 Android ``docs/design/2026-11-24-anime-avatar-mvp.md`` §3）。

端侧只认一个稳定契约（``AvatarGenRemote``）：``POST /v1/avatars/generate`` 同步返回
``avatar_upload_id``。生成侧用哪个模型、要不要换供应商，全部关在服务端这一层——所以
provider 是一个协议，不是散在路由里的配置名。

这里只放**协议与错误**：路由与装配从 ``providers`` 取实现，测试注入自己的假实现。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

#: 放开的风格。**白名单而不是自由文本**：style 直接决定检查点与提示词，未审核的取值
#: 等于把提示词注入的面开给客户端。加一个风格 = 过一遍许可审查再进这张表。
ALLOWED_STYLES = frozenset({"anime"})


class AvatarGenError(Exception):
    """生成/应用被拒。路由层按 ``status`` + ``code`` 翻译成 ``/v1`` 的错误形状
    ``{"detail": {"code": ...}}``——端侧 ``mapStatus`` 只认 status 与 code，
    **绝不把 message 原文透给用户**（photosolve 的 decode 纪律）。

    两个必须与端侧对齐的分类（端侧 ``AvatarGenRemote.mapStatus``）：

    - 422（``BAD_IMAGE``）：源图不存在、不属于该用户、style 非法——都归这一类，
      不区分（防枚举，同直传的 ``KEY_NOT_FOUND`` 口径）；
    - 429（``QUOTA``）：每日生成配额用尽。
    """

    def __init__(self, code: str, *, status: int) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


class AnimeStyleProvider(Protocol):
    """给定源图字节 + 风格，返回结果图字节。

    同步语义（MVP）：一次调用内出图，端侧 readTimeout 已放宽到 120s。
    以后改异步任务（job id + 轮询）只换实现与端侧那一个类，契约不动。

    实现若出图失败，抛任何异常即可——服务层统一收敛成
    ``AvatarGenError("provider_failed", status=502)``，不外泄原始错误。
    """

    name: str

    async def generate(self, *, image: bytes, style: str) -> bytes: ...


@dataclass(frozen=True)
class ExpiredSource:
    """一条到期的源图（sweep 的处理单元）。多个尝试共用同一源图时只出现一次。"""

    upload_id: str
    owner_id: int
    object_key: str


class AvatarGenAttemptStore(Protocol):
    """``ca_avatar_gen_attempt`` 的存取（表注释见 db/schema.py）。

    一行 = 一次生成尝试，只存元数据（图像字节在私有桶、行在 ca_upload）。它同时
    承担两件事：配额窗口（按 owner + created_at 计数）与源图 TTL 账本（expires_at
    到点由 sweep 连对象删）。因此**每次进入生成的尝试都留行，包括 provider 失败的**——
    否则连续失败可以无限重试打穿配额。（style 非法 / 源图不可用的请求不落行：
    它们根本没进入生成，不该占配额。）
    """

    async def add_attempt(self, *, owner_id: int, source_upload_id: str, source_key: str,
                          style: str, created_at: datetime, expires_at: datetime) -> int:
        """记一次尝试，返回行 id（成功时把结果回填到这一行，不靠「最近一行」找它）。"""
        ...

    async def count_recent(self, *, owner_id: int, since: datetime) -> int: ...

    async def attach_result(self, *, attempt_id: int, result_upload_id: str) -> None: ...

    async def result_owned(self, *, owner_id: int, upload_id: str) -> bool:
        """该上传是不是这个用户某次尝试的生成结果（apply 只接受生成结果）。"""
        ...

    async def due_sources(self, *, now: datetime, limit: int) -> list[ExpiredSource]: ...

    async def mark_source_purged(self, *, source_upload_id: str) -> None:
        """源图对象与 ca_upload 行已删：置空 expires_at。行留着——配额窗口按
        created_at 计数、apply 靠 result_upload_id 认领「这是我生成的结果」，都要它。"""
        ...


class UserAvatarStore(Protocol):
    """当前头像指针（``ca_user_avatar``，每用户一行）。服务端是真相：端侧只在
    apply 成功后才写本地副本（「失败不覆盖旧头像」红线的服务端半边）。"""

    async def get(self, *, owner_id: int) -> str | None: ...

    async def set(self, *, owner_id: int, upload_id: str) -> None: ...

    async def delete(self, *, owner_id: int) -> None: ...
