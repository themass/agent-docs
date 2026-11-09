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

from companion.ports.roles import CharacterSourcePort
from companion.domain.roles.card import CharacterCard, CharacterFormatError

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

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "tagline": self.tagline,
            "tags": list(self.tags),
            "voice_available": self.voice_available,
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
    )


class CharacterCatalog:
    """角色目录。读盘一次、缓存一次。

    角色卡随包发布、进程生命周期内不变；不缓存的话刷一次列表页就会把同一批
    文件读几十遍。改卡需要重启进程，这与「卡是发布资产」的定位一致。
    """

    def __init__(self, source: CharacterSourcePort) -> None:
        self._source = source
        self._cache: dict[str, CharacterCard] | None = None

    def _load_all(self) -> dict[str, CharacterCard]:
        if self._cache is not None:
            return self._cache
        loaded: dict[str, CharacterCard] = {}
        for character_id in character_ids(self._source.root):
            # 一张坏卡不该让整个选角色页空白：跳过它，其余照常展示。
            try:
                loaded[character_id] = self._source.load(character_id)
            except (CharacterFormatError, json.JSONDecodeError, OSError):
                continue
        self._cache = loaded
        return loaded

    def list(
        self, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[CharacterSummary], int]:
        """一页摘要 + 总数。总数让客户端知道还有没有下一页。"""
        cards = self._load_all()
        ids = sorted(cards)
        window = ids[offset : offset + limit]
        return [summarize(cid, cards[cid]) for cid in window], len(ids)

    def get(self, character_id: str) -> CharacterDetail:
        card = self._load_all().get(character_id)
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

    router = APIRouter(prefix="/companion", tags=["companion"])

    @router.get("/characters", response_model=CharacterListResponse)
    async def list_characters(
        user_id: Annotated[str, Depends(current_user)],
        limit: int = Query(DEFAULT_LIMIT),
        offset: int = Query(0),
    ) -> CharacterListResponse:
        bounded_limit, bounded_offset = clamp_window(limit, offset)
        items, total = catalog.list(limit=bounded_limit, offset=bounded_offset)
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
            detail = catalog.get(character_id)
        except CharacterNotFound as exc:
            raise HTTPException(status_code=404, detail="character not found") from exc
        return CharacterDetailResponse(**detail.to_json())

    return router
