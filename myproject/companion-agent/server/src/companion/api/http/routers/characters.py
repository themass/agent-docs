"""角色目录：客户端选角色页的数据来源。

角色卡会进系统提示词，属于服务端资产。对外只给「够渲染」的字段：人格、例子对话、
creator_notes 既不必要，也容易被拿去套壳别人的角色。所以这里做的是读盘 + 裁剪，
不引入新的存储。

读取失败一律当角色不存在，不区分「文件坏了」和「没有这个角色」——对调用方是
同一件事，而区分开来只会泄漏服务端有没有某个文件。
"""


import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from companion.service.roles.port import CharacterSourcePort
from companion.service.roles.packs import renderer_of
from companion.agent.roles.card import CharacterCard, CharacterFormatError

_CARD_SUFFIX = ".v2.json"


class CharacterNotFound(LookupError):
    """角色不存在。"""


@dataclass(frozen=True, slots=True)
class CharacterSummary:
    """列表项。够画一张卡片，不含人设正文。"""

    id: str
    name: str
    tagline: str
    tags: list[str] = field(default_factory=list)
    # 有音色才可以语音聊。接真实火山音色时只需改角色卡里的 voice_id。
    voice_available: bool = True
    # 这个角色说话用谁的声音。客户端拿它显示音色名（「贴心女友」）或调试时对账。
    # 只给 provider 与 voice_id，不给 params：那里面可能有账号侧的调参。
    voice_ref: dict[str, str] | None = None
    # 这个角色的形象由哪种数字人引擎渲染（simple|live2d|vrm|…）。空串 = 卡没声明，
    # 客户端退回默认引擎。有了它，「目录返回引擎类型 → 自动选引擎」不再靠实验菜单手选。
    renderer: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "tagline": self.tagline,
            "tags": list(self.tags),
            "voice_available": self.voice_available,
            "voice_ref": dict(self.voice_ref) if self.voice_ref else None,
            "renderer": self.renderer,
        }


@dataclass(frozen=True, slots=True)
class CharacterDetail:
    """详情。多给开场白与出场方式，客户端进聊天页第一屏要用。"""

    summary: CharacterSummary
    description: str
    personality: str
    scenario: str
    first_mes: str
    alternate_greetings: list[str] = field(default_factory=list)
    skill: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            **self.summary.to_json(),
            "description": self.description,
            "personality": self.personality,
            "scenario": self.scenario,
            "first_mes": self.first_mes,
            "alternate_greetings": list(self.alternate_greetings),
            "skill": self.skill,
        }


def character_ids(root: Path) -> list[str]:
    """扫出所有角色 id，按文件名排序。

    顺序固定是因为客户端会缓存列表；依赖目录读取顺序会让「角色在第一位」
    这种安排在一部分设备上失效。
    """
    if not root.is_dir():
        return []
    return [
        path.name[: -len(_CARD_SUFFIX)]
        for path in sorted(root.iterdir())
        if path.is_file() and path.name.endswith(_CARD_SUFFIX)
    ]


def voice_is_available(card: CharacterCard) -> bool:
    return bool(str((card.voice_ref or {}).get("voice_id") or "").strip())


def public_voice_ref(card: CharacterCard) -> dict[str, str] | None:
    """对外只给 provider 与 voice_id。

    ``voice_ref.params`` 是账号侧的调参（语速、情感强度之类），客户端不需要，
    公开出去只是把服务端的供应商配置摊开。没有音色就返回 ``None``——
    客户端据此退回「用默认音色」的那条显示，而不是猜一个名字。
    """
    ref = card.voice_ref or {}
    voice_id = str(ref.get("voice_id") or "").strip()
    if not voice_id:
        return None
    return {"provider": str(ref.get("provider") or "volcengine").strip(),
            "voice_id": voice_id}


def skill_id(card: CharacterCard) -> str:
    vvv = card.extensions.get("vvv")
    if not isinstance(vvv, dict):
        return ""
    skill = vvv.get("skill")
    return skill if isinstance(skill, str) else ""


def summarize(character_id: str, card: CharacterCard) -> CharacterSummary:
    return CharacterSummary(
        id=card.id or character_id,
        name=card.name or character_id,
        tagline=card.tagline,
        tags=list(card.tags),
        voice_available=voice_is_available(card),
        voice_ref=public_voice_ref(card),
        renderer=renderer_of(card),
    )


class CharacterCatalog:
    """角色目录。读一次、缓存一次（进程级）。

    来源现在是链（库优先、文件兜底，见 service/roles/packs.py）。缓存沿用进程级：
    列表页每请求重查整目录没有意义，而封装的改动走部署——播种后进程重启即生效，
    热更新路径调 ``invalidate()``。
    """

    def __init__(self, source: CharacterSourcePort) -> None:
        self._source = source
        self._cache: dict[str, CharacterCard] | None = None

    async def _load_all(self) -> dict[str, CharacterCard]:
        if self._cache is not None:
            return self._cache
        loader = getattr(self._source, "cards", None)
        if loader is not None:
            loaded = await loader()
        else:
            # 来源没有整目录接口时逐个读；一张坏卡不该让整个选角色页空白。
            loaded = {}
            for character_id in character_ids(self._source.root):
                try:
                    loaded[character_id] = await self._source.load(character_id)
                except (CharacterFormatError, json.JSONDecodeError, OSError, FileNotFoundError):
                    continue
        self._cache = loaded
        return loaded

    async def list(
        self, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[CharacterSummary], int]:
        """一页摘要 + 总数。总数让客户端知道还有没有下一页。"""
        cards = await self._load_all()
        ids = sorted(cards)
        window = ids[offset : offset + limit]
        return [summarize(cid, cards[cid]) for cid in window], len(ids)

    async def get(self, character_id: str) -> CharacterDetail:
        card = (await self._load_all()).get(character_id)
        if card is None:
            raise CharacterNotFound(character_id)
        return CharacterDetail(
            summary=summarize(character_id, card),
            description=card.description,
            personality=card.personality,
            scenario=card.scenario,
            first_mes=card.first_mes,
            alternate_greetings=list(card.alternate_greetings),
            skill=skill_id(card),
        )

    def invalidate(self) -> None:
        """丢缓存。测试与热更新角色卡用。"""
        self._cache = None


def build_router(catalog: CharacterCatalog, current_user):
    """挂到 app 上。fastapi 在这里才导入。

    两个接口都要求身份：角色卡本身不是隐私，但统一的鉴权面更简单——不要求
    身份就得逐个判断「这个接口能不能公开」，迟早会漏一个。
    """
    from typing import Annotated

    from fastapi import APIRouter, Depends, HTTPException, Query
    from pydantic import BaseModel

    from companion.api.http.support import DEFAULT_LIMIT, clamp_window

    class CharacterSummaryResponse(BaseModel):
        id: str
        name: str
        tagline: str
        tags: list[str]
        voice_available: bool
        # 客户端据此显示音色名。没有音色的角色给 null。
        voice_ref: dict[str, str] | None = None
        # 数字人引擎判别（simple|live2d|vrm|…），空串 = 卡没声明。
        # response_model 会滤掉未声明的字段——这里漏了，客户端就永远看不见它。
        renderer: str = ""

    class CharacterListResponse(BaseModel):
        items: list[CharacterSummaryResponse]
        total: int
        limit: int
        offset: int

    class CharacterDetailResponse(CharacterSummaryResponse):
        description: str
        personality: str
        scenario: str
        first_mes: str
        alternate_greetings: list[str]
        skill: str

    router = APIRouter(prefix="/v1", tags=["companion"])

    @router.get("/characters", response_model=CharacterListResponse)
    async def list_characters(
        user_id: Annotated[str, Depends(current_user)],
        limit: int = Query(DEFAULT_LIMIT),
        offset: int = Query(0),
    ) -> CharacterListResponse:
        bounded_limit, bounded_offset = clamp_window(limit, offset)
        items, total = await catalog.list(limit=bounded_limit, offset=bounded_offset)
        return CharacterListResponse(
            items=[CharacterSummaryResponse(**item.to_json()) for item in items],
            total=total,
            limit=bounded_limit,
            offset=bounded_offset,
        )

    @router.get("/characters/{character_id}", response_model=CharacterDetailResponse)
    async def get_character(
        character_id: str,
        user_id: Annotated[str, Depends(current_user)],
    ) -> CharacterDetailResponse:
        try:
            detail = await catalog.get(character_id)
        except CharacterNotFound as exc:
            raise HTTPException(status_code=404, detail="character not found") from exc
        return CharacterDetailResponse(**detail.to_json())

    return router
