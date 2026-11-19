"""提示词用的统一角色视图。

角色有三个来源（P §4）：目录角色（SystemRole）、陪伴角色卡（CharacterCard，SillyTavern V2/V3）、
用户自建角色（只有一段提示词）。提示词引擎只认 RoleProfile，来源之间的差异在这里抹平。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from companion.agent.lorebook import Lorebook, from_character_book
from companion.agent.lorebook.model import ROLES, DepthInjection
from companion.agent.roles.card import CharacterCard
from companion.agent.roles.catalog import SystemRole

#: 任务卡里「怎么做这份工作」的段落。全库 283 张卡只有这几个二级标题，
#: 所以按标题切是可靠的；``Identity`` 与人设有关，留在角色层，不算方法层。
_TASK_SECTIONS = ("Core mission", "Rules", "Capabilities")

#: 卡里不是标题、但同样属于「工作清单」的整段：``You remember:`` 后面跟一串要记住的
#: 业务字段。留在角色层会变成「我记得你的合同金额是…」这类第一人称台词。
_REMEMBER_BLOCK = re.compile(r"(?m)^You remember:[ \t]*$.*?(?=\n[ \t]*\n|\Z)", re.S)

_SECTION_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.M)


def split_card_prompt(text: str) -> tuple[str, str]:
    """把任务卡正文拆成 (角色层, 方法层)。

    角色层只保留卡的开头（第一段自述）与 ``## Identity``；Core mission / Rules /
    Capabilities 是「工作要求」，进方法层。没有这些标题的卡（4 张）整段当角色层，
    行为和以前一致——分流是为了解决问题，不是为了改变所有卡。
    """
    body = text.strip()
    if not body:
        return "", ""
    marks = list(_SECTION_RE.finditer(body))
    if not marks:
        return body, ""

    kept: list[str] = []
    moved: list[str] = []
    head = body[: marks[0].start()].strip()
    if head:
        kept.append(head)
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        chunk = body[mark.start():end].strip()
        title = mark.group(1).strip()
        (moved if title in _TASK_SECTIONS else kept).append(chunk)

    # You remember 段可能落在任何一块里，逐块摘出来，避免整体搬家时漏掉。
    def _strip_remember(chunks: list[str]) -> list[str]:
        out: list[str] = []
        for chunk in chunks:
            for found in _REMEMBER_BLOCK.findall(chunk):
                moved.append(found.strip())
            rest = _REMEMBER_BLOCK.sub("", chunk).strip()
            if rest:
                out.append(rest)
        return out

    kept = _strip_remember(kept)
    return "\n\n".join(kept), "\n\n".join(moved)


@dataclass(frozen=True)
class RoleProfile:
    role_id: str
    name: str
    description: str
    personality: str = ""
    scenario: str = ""
    system_override: str = ""      # 卡片 system_prompt；只补充角色指令，不覆盖平台安全规则
    post_history: str = ""         # 卡片 post_history_instructions；放在历史之后
    examples: str = ""             # 卡片 mes_example 原文（<START> 分块）
    lorebook: Lorebook | None = None
    depth_prompt: DepthInjection | None = None
    method: str = ""               # skill 的方法层常驻段（P §5），由解析方填入
    skills: tuple[str, ...] = ()   # method 实际由哪些 skill 合成（含常驻的），质检用
    source: str = "catalog"        # catalog | companion | user


def _depth_prompt(extensions: dict[str, Any]) -> DepthInjection | None:
    raw = extensions.get("depth_prompt")
    if not isinstance(raw, dict):
        return None
    text = str(raw.get("prompt") or "").strip()
    if not text:
        return None
    try:
        depth = max(0, int(raw.get("depth", 4)))
    except (TypeError, ValueError):
        depth = 4
    role = str(raw.get("role") or "system")
    return DepthInjection(depth=depth, role=role if role in ROLES else "system", text=text)


def from_card(card: CharacterCard) -> RoleProfile:
    return RoleProfile(
        role_id=card.id,
        name=card.name,
        description=card.description,
        personality=card.personality,
        scenario=card.scenario,
        system_override=card.system_prompt,
        post_history=card.post_history_instructions,
        examples=card.mes_example,
        lorebook=from_character_book(card.character_book),
        depth_prompt=_depth_prompt(card.extensions),
        source="companion",
    )


def from_system_role(role: SystemRole, *, locale: str = "zh-CN") -> RoleProfile:
    """目录角色：产品写的人设进角色层，第三方的任务卡正文进方法层。

    目录里 283 张卡来自任务型 agent 仓库，一张 3.5k 字、通篇是「你要做这几件事」。
    以前把整张卡塞进 ``description``，它就原样落进「# 你的角色」这一层——模型对一句
    「hello」唯一能拿来当话说的就是这份任务清单，于是逐条念 Core mission / Rules 当
    自我介绍（2026-11-18 线上复现）。卡是上游内容、改不过来，所以在这里分流：

    - 角色层：``description`` + ``vibe``（产品自己写的、中文本地化 100% 覆盖）；
    - 方法层：卡里的 Core mission / Rules / Capabilities，标题为「工作方式」，
      离用户消息更远，且输出层已经说了「只有用户明确要分析、才展开」。
    """
    zh = locale.startswith("zh")
    name = role.name_zh if zh and role.name_zh else role.name
    summary = (role.description_zh if zh and role.description_zh else role.description).strip()
    vibe = (role.vibe_zh if zh and role.vibe_zh else role.vibe).strip()
    persona_card, method = split_card_prompt(role.prompt)
    description = "\n\n".join(part for part in (summary, vibe, persona_card) if part)
    return RoleProfile(role_id=role.id, name=name, description=description,
                       method=method, source="catalog")



def from_user_prompt(*, role_id: str, name: str, prompt: str) -> RoleProfile:
    return RoleProfile(role_id=role_id, name=name, description=prompt, source="user")
