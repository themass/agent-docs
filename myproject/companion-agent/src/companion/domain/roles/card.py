"""SillyTavern 角色卡（V2 为主，兼容 V3 导入）。

内部主格式是 V2 的 ``data`` 块；V3 的额外字段不丢，落到 ``extensions["vvv"]``，
导出时原样带回（设计文档第 3 节）。

角色卡是**用户不可信输入**：这里只做结构解析，不执行、不解释其中的任何指令；
它最终会被拼进系统提示词，所以长度必须有上限（见 ``render_persona``）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SPEC_V2 = "chara_card_v2"
SPEC_V3 = "chara_card_v3"
SPEC_VERSION_V2 = "2.0"

# extensions 里专门放 V3 独有字段的键；导出 V3 时整块抬回 data 顶层。
VVV_KEY = "vvv"

# persona 段落总长上限。角色卡可以任意长，系统提示词不行。
PERSONA_MAX_CHARS = 4000

# data 块里由 CharacterCard 字段接收的键，其余都算「未知」进 extensions。
_CORE_KEYS = frozenset(
    {
        "id",
        "name",
        "tagline",
        "description",
        "personality",
        "scenario",
        "first_mes",
        "mes_example",
        "creator_notes",
        "tags",
        "voice_ref",
        "model_ref",
        "emotion_map",
        "memory_policy",
        "extensions",
        "system_prompt",
        "post_history_instructions",
        "alternate_greetings",
        "character_book",
        "creator",
        "character_version",
        "spec",
        "spec_version",
    }
)

# V3 相对 V2 新增的字段；读到就归档到 extensions["vvv"]，不参与 persona。
_V3_ONLY_KEYS = frozenset(
    {
        "nickname",
        "creator_notes_multilingual",
        "source",
        "group_only_greetings",
        "assets",
        "creation_date",
        "modification_date",
    }
)


class CharacterFormatError(ValueError):
    """角色卡结构不可用（缺 data 块、类型不对、版本取不到）。"""


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _spec_marks_v3(spec: str, data: dict[str, Any]) -> bool:
    lowered = spec.lower()
    if "v3" in lowered or "ccv3" in lowered:
        return True
    # 没有 spec 的裸 data（手工整理或其它工具产出）靠 V3 独有字段判断
    return any(key in data for key in _V3_ONLY_KEYS)


def _emotion_map_from_assets(assets: Any) -> dict[str, str]:
    """V3 的表情资源 -> emotion_map。键取资源名，取不到就用 type。"""
    result: dict[str, str] = {}
    if not isinstance(assets, list):
        return result
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        kind = _text(asset.get("type")).lower()
        if "emotion" not in kind:
            continue
        key = _text(asset.get("name")) or kind
        uri = _text(asset.get("uri"))
        if key and uri:
            result[key] = uri
    return result


@dataclass
class CharacterCard:
    """一个角色。所有字符串字段都按原样保留，不做模板替换。"""

    id: str = ""
    name: str = ""
    tagline: str = ""
    description: str = ""
    personality: str = ""
    scenario: str = ""
    first_mes: str = ""
    mes_example: str = ""
    creator_notes: str = ""
    tags: list[str] = field(default_factory=list)
    voice_ref: dict[str, Any] | None = None
    model_ref: str | None = None
    emotion_map: dict[str, str] = field(default_factory=dict)
    memory_policy: dict[str, Any] = field(default_factory=dict)
    # 读到的所有非核心键；V3 独有的在 extensions["vvv"]。
    extensions: dict[str, Any] = field(default_factory=dict)
    # 以下三项 V2 有、但不参与 persona 渲染；导出时原样带回。
    system_prompt: str = ""
    post_history_instructions: str = ""
    alternate_greetings: list[str] = field(default_factory=list)
    spec_version: str = SPEC_VERSION_V2

    @property
    def is_v3(self) -> bool:
        return VVV_KEY in self.extensions


def from_v2_json(payload: dict[str, Any]) -> CharacterCard:
    """解析 V2 卡；``spec``/字段表明是 V3 时按 V3 读 data 块。"""
    if not isinstance(payload, dict):
        raise CharacterFormatError("character card must be a mapping")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise CharacterFormatError("character card has no data block")

    spec = _text(payload.get("spec") or data.get("spec"))
    spec_version = _text(payload.get("spec_version") or data.get("spec_version"))
    v3 = _spec_marks_v3(spec, data)

    extensions: dict[str, Any] = _mapping(data.get("extensions"))
    vvv: dict[str, Any] = {}
    for key, value in data.items():
        if key in _CORE_KEYS:
            continue
        if key in _V3_ONLY_KEYS:
            vvv[key] = value
        else:
            extensions[key] = value

    emotion_map = {
        str(k): str(v) for k, v in _mapping(data.get("emotion_map")).items()
    }
    if v3:
        # V3 的 assets 是唯一的表情来源；显式 emotion_map 优先（内部格式可能已填好）
        for key, uri in _emotion_map_from_assets(data.get("assets")).items():
            emotion_map.setdefault(key, uri)
        if vvv:
            extensions[VVV_KEY] = vvv

    voice_ref = data.get("voice_ref")
    model_ref = data.get("model_ref")
    return CharacterCard(
        id=_text(data.get("id")),
        name=_text(data.get("name")),
        tagline=_text(data.get("tagline")),
        description=_text(data.get("description")),
        personality=_text(data.get("personality")),
        scenario=_text(data.get("scenario")),
        first_mes=_text(data.get("first_mes")),
        mes_example=_text(data.get("mes_example")),
        creator_notes=_text(data.get("creator_notes")),
        tags=_string_list(data.get("tags")),
        voice_ref=_mapping(voice_ref) or None,
        model_ref=_text(model_ref) or None,
        emotion_map=emotion_map,
        memory_policy=_mapping(data.get("memory_policy")),
        extensions=extensions,
        system_prompt=_text(data.get("system_prompt")),
        post_history_instructions=_text(data.get("post_history_instructions")),
        alternate_greetings=_string_list(data.get("alternate_greetings")),
        spec_version=spec_version or ("3.0" if v3 else SPEC_VERSION_V2),
    )


def to_v2_json(card: CharacterCard) -> dict[str, Any]:
    """导出 V2 卡。读到的东西全部写回，未知键归到 ``data.extensions``。

    V2 规范把 ``extensions`` 定义为放任意数据的地方，所以未知键统一落这里，
    而不是散在 data 顶层——SillyTavern 两端都读得懂，且不丢内容。
    V3 独有字段仍在 ``extensions["vvv"]``，留给 V3 导出器抬回顶层。
    """
    data: dict[str, Any] = {
        "name": card.name,
        "description": card.description,
        "personality": card.personality,
        "scenario": card.scenario,
        "first_mes": card.first_mes,
        "mes_example": card.mes_example,
        "creator_notes": card.creator_notes,
        "tags": list(card.tags),
        "extensions": dict(card.extensions),
    }
    if card.id:
        data["id"] = card.id
    if card.tagline:
        data["tagline"] = card.tagline
    if card.voice_ref:
        data["voice_ref"] = dict(card.voice_ref)
    if card.model_ref:
        data["model_ref"] = card.model_ref
    if card.emotion_map:
        data["emotion_map"] = dict(card.emotion_map)
    if card.memory_policy:
        data["memory_policy"] = dict(card.memory_policy)
    if card.system_prompt:
        data["system_prompt"] = card.system_prompt
    if card.post_history_instructions:
        data["post_history_instructions"] = card.post_history_instructions
    if card.alternate_greetings:
        data["alternate_greetings"] = list(card.alternate_greetings)
    return {"spec": SPEC_V2, "spec_version": card.spec_version, "data": data}


def _section(title: str, text: str) -> str:
    return f"### {title}\n{text.strip()}"


def _clip(text: str, budget: int) -> str:
    if budget <= 0:
        return ""
    if len(text) <= budget:
        return text
    return text[: max(budget - 1, 0)].rstrip() + "…"


def render_persona(card: CharacterCard, max_chars: int = PERSONA_MAX_CHARS) -> str:
    """渲染 persona 段。按 描述 → 性格 → 场景 的顺序，超长时按段截断。

    例子对话（``mes_example``）不进这里：它是「怎么说话」的示例，属于另一段
    提示词，混进人设会挤掉场景信息。
    """
    # 无名卡也得出句人话，空引号会让模型把它当成缺失字段去追问
    header = f"你正在扮演「{card.name or '这个角色'}」"
    if card.tagline:
        header = f"{header}：{card.tagline}"
    parts = [header + "。"]

    sections = [
        ("角色描述", card.description),
        ("性格", card.personality),
        ("场景", card.scenario),
    ]
    # 先留出标题与已用长度，剩余预算均摊给各段；宁可每段短一点，也不整段丢掉。
    remaining = max(max_chars - len("\n\n".join(parts)), 0)
    pending = [(title, text) for title, text in sections if text.strip()]
    for index, (title, text) in enumerate(pending):
        share = remaining // (len(pending) - index)
        clipped = _clip(text.strip(), share - len(title) - 8)
        if not clipped:
            continue
        block = _section(title, clipped)
        parts.append(block)
        remaining -= len(block) + 2

    result = "\n\n".join(parts)
    if len(result) > max_chars:
        result = _clip(result, max_chars)
    return result


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """把角色名转成可做目录名 / 文件名的 id；中文名会得到空串，由调用方兜底。"""
    return _SLUG_RE.sub("-", name.strip().lower()).strip("-")
