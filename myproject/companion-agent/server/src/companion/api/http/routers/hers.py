"""her 目录：客户端「她长什么样」选择页的数据来源。

persona/her 分层第一刀的服务端接口（docs/design/2026-11-28-persona-her-split-architecture.md §3）。
镜像 characters 路由的鉴权、分页与裁剪风格；两个历史教训在这里固化：

1. **response_model 必须显式声明每一个要出去的字段。** 同一个缺口发生过两次
   （voice_ref、renderer），内部测试全绿而 HTTP JSON 里没有那个键。所以这里
   每个响应类都把字段列全，并由 tests/test_hers_http.py 打真路由钉住。
2. **只给够渲染的字段。** 模型包的细节（effects 的锚点参数、touch_zones 几何）
   在详情里给——列表只给卡片要画的东西（缩略图、renderer 徽标、特效计数）。

现在库没播种时列表就是空的——与 characters 不同，her 没有文件兜底链：呈现实体
从第一刀起就以库为事实源，播种脚本 tools/seed_her_packs.py 把角色卡里的
model_ref 转成 her 包 + 默认绑定。

本文件不放 ``from __future__ import annotations``：路由里的 ``Annotated[str, Depends(...)]``
用了 build_router 内的局部名，推迟求值会让 FastAPI 到模块全局找它们——找不到时
``user_id`` 会退化成 query 参数（422），deps.py 的注释钉过同一个坑。
"""

from dataclasses import dataclass, field
from typing import Any

from companion.service.roles.hers import HerPackRecord, SqlHerPackStore


class HerNotFound(LookupError):
    """her 不存在。"""


@dataclass(frozen=True, slots=True)
class HerSummary:
    """列表项。够画一张卡片，不含呈现细节。"""

    id: str
    name: str
    tagline: str
    # 渲染这个 her 用哪种数字人引擎（simple|live2d|vrm|rive|…）。空串 = 包没声明，
    # 客户端退回默认引擎。renderer 长在包上，不长在角色上——这是分层的判别点。
    renderer: str
    status: str
    pack_version: int
    thumbnail: str
    effect_count: int
    sticker_count: int
    voice_ref: dict[str, str] | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "tagline": self.tagline,
            "renderer": self.renderer,
            "status": self.status,
            "pack_version": self.pack_version,
            "thumbnail": self.thumbnail,
            "effect_count": self.effect_count,
            "sticker_count": self.sticker_count,
            "voice_ref": dict(self.voice_ref) if self.voice_ref else None,
        }


@dataclass(frozen=True, slots=True)
class HerDetail:
    """详情。多给模型引用与目录（特效/贴纸/触摸区），端上按契约校验安装。"""

    summary: HerSummary
    source: str
    model_ref: dict[str, Any] = field(default_factory=dict)
    effects: list[Any] = field(default_factory=list)
    stickers: list[Any] = field(default_factory=list)
    touch_zones: list[Any] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            **self.summary.to_json(),
            "source": self.source,
            "model_ref": dict(self.model_ref),
            "effects": list(self.effects),
            "stickers": list(self.stickers),
            "touch_zones": list(self.touch_zones),
        }


def summarize(rec: HerPackRecord) -> HerSummary:
    return HerSummary(
        id=rec.her_id,
        name=rec.name,
        tagline=rec.tagline,
        renderer=rec.renderer,
        status=rec.status,
        pack_version=rec.pack_version,
        thumbnail=rec.thumbnail,
        effect_count=len(rec.effects),
        sticker_count=len(rec.stickers),
        voice_ref=rec.voice_ref,
    )


class HerCatalog:
    """her 目录。读一次、缓存一次（进程级），口径同 CharacterCatalog。

    her 包的改动走播种/发布（部署或 Hermes 产线），列表页每请求重查整目录没有意义；
    热更新路径调 ``invalidate()``。
    """

    def __init__(self, store: SqlHerPackStore) -> None:
        self._store = store
        self._cache: dict[str, HerPackRecord] | None = None

    async def _load_all(self) -> dict[str, HerPackRecord]:
        if self._cache is None:
            self._cache = {rec.her_id: rec for rec in await self._store.list_records()}
        return self._cache

    async def list(self, *, limit: int = 20, offset: int = 0) -> tuple[list[HerSummary], int]:
        records = await self._load_all()
        ids = sorted(records)
        window = ids[offset: offset + limit]
        return [summarize(records[hid]) for hid in window], len(ids)

    async def get(self, her_id: str) -> HerDetail:
        rec = (await self._load_all()).get(her_id)
        if rec is None:
            raise HerNotFound(her_id)
        return HerDetail(
            summary=summarize(rec),
            source=rec.source,
            model_ref=rec.model_ref,
            effects=rec.effects,
            stickers=rec.stickers,
            touch_zones=[z for z in (rec.payload.get("touch_zones") or []) if isinstance(z, (dict, list))],
        )

    def invalidate(self) -> None:
        """丢缓存。播种后与测试用。"""
        self._cache = None


def build_router(catalog: HerCatalog, current_user):
    """挂到 app 上。fastapi 在这里才导入（与 characters 路由同形）。

    鉴权与角色目录一致：统一要求身份，不搞「这个接口能不能公开」的逐个判断。
    """
    from typing import Annotated

    from fastapi import APIRouter, Depends, HTTPException, Query
    from pydantic import BaseModel

    from companion.api.http.support import DEFAULT_LIMIT, clamp_window

    class HerSummaryResponse(BaseModel):
        id: str
        name: str
        tagline: str
        renderer: str
        status: str
        pack_version: int
        thumbnail: str
        effect_count: int
        sticker_count: int
        # response_model 会滤掉未声明的字段——这里漏一个，客户端就永远看不见一个。
        # （voice_ref、renderer 各栽过一次，见 tests/test_hers_http.py 文件头。）
        voice_ref: dict[str, str] | None = None

    class HerListResponse(BaseModel):
        items: list[HerSummaryResponse]
        total: int
        limit: int
        offset: int

    class HerDetailResponse(HerSummaryResponse):
        source: str
        model_ref: dict[str, Any]
        effects: list[Any]
        stickers: list[Any]
        touch_zones: list[Any]

    router = APIRouter(prefix="/v1", tags=["companion"])

    @router.get("/hers", response_model=HerListResponse)
    async def list_hers(
        user_id: Annotated[str, Depends(current_user)],
        limit: int = Query(DEFAULT_LIMIT),
        offset: int = Query(0),
    ) -> HerListResponse:
        bounded_limit, bounded_offset = clamp_window(limit, offset)
        items, total = await catalog.list(limit=bounded_limit, offset=bounded_offset)
        return HerListResponse(
            items=[HerSummaryResponse(**item.to_json()) for item in items],
            total=total,
            limit=bounded_limit,
            offset=bounded_offset,
        )

    @router.get("/hers/{her_id}", response_model=HerDetailResponse)
    async def get_her(
        her_id: str,
        user_id: Annotated[str, Depends(current_user)],
    ) -> HerDetailResponse:
        try:
            detail = await catalog.get(her_id)
        except HerNotFound as exc:
            raise HTTPException(status_code=404, detail="her not found") from exc
        return HerDetailResponse(**detail.to_json())

    return router
