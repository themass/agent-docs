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

from dataclasses import dataclass, field, replace
from typing import Any

# HerCatalog 类体内有个叫 list() 的方法——它会把内建 list 遮住，之后任何注解再写
# list[...] 就是在给方法对象下标（TypeError，收集期就炸）。注解一律用这个别名。
_List = list

from companion.service.roles.hers import HerPackRecord, SqlHerPackStore

#: 签名 URL 的有效期。口径同形象发布链（service/avatar/catalog.py SIGNED_URL_TTL）：
#: 下载是一次动作，不是长期凭据——1 小时够下一包，过期再取。
SIGNED_URL_TTL = 3600


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
    # 卡片图。库里存的是对象 key（payload.thumbnail_key），读时现签——签名 URL 是
    # bearer secret，不落库（同 avatars 线 SIGNED_URL_TTL 口径）。没配对象存储 = 空串。
    thumbnail_url: str = ""
    url_expires_in: int = 0

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
            "thumbnail_url": self.thumbnail_url,
            "url_expires_in": self.url_expires_in,
        }


@dataclass(frozen=True, slots=True)
class HerDetail:
    """详情。多给模型引用与目录（特效/贴纸/触摸区），端上按契约校验安装。

    URL 口径（docs/her-tos-delivery-design-20261128.md §3）：库里存的是**对象 key**
    （payload.object_key / thumbnail_key / portrait_key / 目录项 key），读时现签
    （``url_expires_in`` 同步给出）；签名 URL 是 bearer secret，永不落库。
    没配对象存储 → URL 全空串，端上按「暂不可下载」处理，不是错误。
    persona 半经 ``ca_character_her`` 绑定 join 角色卡——「她长什么样」的页面
    同时回答「她是谁」；her 可以没绑定（纯注册未上架），那时 persona=null。
    """

    summary: HerSummary
    source: str
    model_ref: dict[str, Any] = field(default_factory=dict)
    effects: list[Any] = field(default_factory=list)
    stickers: list[Any] = field(default_factory=list)
    touch_zones: list[Any] = field(default_factory=list)
    portrait_url: str = ""
    persona: dict[str, Any] | None = None
    url_expires_in: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            **self.summary.to_json(),
            "source": self.source,
            "model_ref": dict(self.model_ref),
            "effects": list(self.effects),
            "stickers": list(self.stickers),
            "touch_zones": list(self.touch_zones),
            "portrait_url": self.portrait_url,
            "persona": dict(self.persona) if self.persona else None,
            "url_expires_in": self.url_expires_in,
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

    ``objects``（对象存储）与 ``characters``（persona 读取链）都是可选依赖：
    - 没配对象存储 → URL 字段一律空串（服务照常起，端上显示「暂不可下载」）；
      签名是本地加密运算，不联网，列表页 N 次签名没有成本问题（avatars 线同款）。
    - 没有 persona 链 → persona=null；绑定存在但角色卡读不出来同样 null，不 404。
    库里存的是**对象 key**（发布工具写入），URL 只在这里现签——签名 URL 是
    bearer secret，永不落库。
    """

    def __init__(self, store: SqlHerPackStore, *, objects: Any = None,
                 characters: Any = None) -> None:
        self._store = store
        self._objects = objects
        self._characters = characters
        self._cache: dict[str, HerPackRecord] | None = None

    async def _sign(self, key: str) -> tuple[str, int]:
        if not key or self._objects is None:
            return "", 0
        try:
            url = await self._objects.signed_url(key=key, ttl_seconds=SIGNED_URL_TTL)
        except KeyError:
            # 库里有 key、桶里没有对象（半写/误删）：URL 给空，别让一个坏 key 掀掉整页。
            return "", 0
        return url, SIGNED_URL_TTL

    async def _load_all(self) -> dict[str, HerPackRecord]:
        if self._cache is None:
            self._cache = {rec.her_id: rec for rec in await self._store.list_records()}
        return self._cache

    async def list(self, *, limit: int = 20, offset: int = 0) -> tuple[list[HerSummary], int]:
        records = await self._load_all()
        # 上架闸：C 端列表只给 published。draft-first 裁决（注册≠上架）在这里生效——
        # 发布工具登记的 draft、下架的 retired 都不进目录，否则 draft 闸只是装饰。
        # 详情仍可按 id 直达（验收/QA 的深链），列表与详情不同权是刻意的。
        ids = sorted(hid for hid, rec in records.items() if rec.status == "published")
        window = ids[offset: offset + limit]
        out: list[HerSummary] = []
        for hid in window:
            summary = summarize(records[hid])
            url, ttl = await self._sign(str(records[hid].payload.get("thumbnail_key") or ""))
            out.append(replace(summary, thumbnail_url=url, url_expires_in=ttl))
        return out, len(ids)

    async def _persona(self, her_id: str) -> dict[str, Any] | None:
        role_id = await self._store.role_for_her(her_id)
        if role_id is None or self._characters is None:
            return None
        try:
            card = await self._characters.load(role_id)
        except FileNotFoundError:
            # 绑定存在但角色卡读不出来（没播种/坏卡）：persona 给 null，不连坐详情。
            return None
        return {"role_id": role_id, "name": getattr(card, "name", "") or role_id,
                "description": getattr(card, "description", "") or "",
                "personality": getattr(card, "personality", "") or ""}

    async def _sign_catalog(self, items: _List[Any]) -> _List[Any]:
        """目录项（特效/贴纸）现签 URL。缺 key 的项保持原样——策略目录也允许纯 id 项。"""
        out: list[Any] = []
        for item in items:
            if isinstance(item, dict) and item.get("key"):
                url, ttl = await self._sign(str(item["key"]))
                item = {**item, "url": url, "url_expires_in": ttl}
            out.append(item)
        return out

    async def get(self, her_id: str) -> HerDetail:
        rec = (await self._load_all()).get(her_id)
        if rec is None:
            raise HerNotFound(her_id)
        model_ref = rec.model_ref
        url, ttl = await self._sign(str(rec.payload.get("object_key") or ""))
        if url:
            model_ref = {**model_ref, "download_url": url, "url_expires_in": ttl,
                         "size_bytes": rec.payload.get("size_bytes")}
        thumbnail_url, _ = await self._sign(str(rec.payload.get("thumbnail_key") or ""))
        portrait_url, _ = await self._sign(str(rec.payload.get("portrait_key") or ""))
        return HerDetail(
            summary=replace(summarize(rec), thumbnail_url=thumbnail_url, url_expires_in=ttl),
            source=rec.source,
            model_ref=model_ref,
            effects=await self._sign_catalog(rec.effects),
            stickers=await self._sign_catalog(rec.stickers),
            touch_zones=[z for z in (rec.payload.get("touch_zones") or []) if isinstance(z, (dict, list))],
            portrait_url=portrait_url,
            persona=await self._persona(her_id),
            url_expires_in=ttl,
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
        thumbnail_url: str = ""
        url_expires_in: int = 0

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
        portrait_url: str = ""
        persona: dict[str, Any] | None = None

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
