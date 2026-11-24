"""P6 角色卡：可版本化的身份 / 声音偏好 / 关系边界。

设计参照 AIRI 的角色卡 ADR，但按**确定性策略**起步（ADR 自己标注真模型效果未验证）：
- 卡 = 一条基准（来自角色资产或空）+ 一串按版本号递增的变更集（version 覆盖链）；
- 合并规则只有「后写覆盖先写、null 清除、dict/list 整值替换」——没有模型生成、没有拼接；
- 本模块是纯策略层（受 .importlinter 的 agent-pure 契约同类约束：不碰 I/O）。

字段白名单是刻意的：卡是用户输入，能覆盖的只有 persona 里「这个人是谁」的那几项。
``system_prompt`` 之类在角色资产里由创作者控制，不从用户侧卡注入。
"""

from __future__ import annotations

from typing import Any

MAX_NAME_CHARS = 40
MAX_TEXT_CHARS = 1000
MAX_BOUNDARIES = 10
MAX_BOUNDARY_CHARS = 120

# 允许覆盖的字段 → 值形态。text=字符串；voice=映射；boundaries=字符串列表。
_FIELD_SHAPE: dict[str, str] = {
    "name": "text",
    "tagline": "text",
    "description": "text",
    "personality": "text",
    "scenario": "text",
    "voice": "voice",
    "boundaries": "boundaries",
}

# voice 是整值替换，但键也要有界：只接受这些，其余拒绝（防用户往里塞任意配置）。
_VOICE_KEYS = frozenset({"engine", "voice_id", "speed", "pitch", "style"})


class CardChangeInvalid(ValueError):
    """变更集不合法：未知字段、超长、类型不对、或合并后为空。"""


def normalize_changeset(changes: dict[str, Any]) -> dict[str, Any]:
    """校验并规范化一个变更集；返回去掉空白噪声后的副本。非法抛 CardChangeInvalid。

    值语义：None / 空串 = 清除该字段；有值 = 设置。至少要有一个非清除项，否则空版本
    会白白占一个版本号、还在覆盖链里制造无意义的节点。
    """
    if not isinstance(changes, dict) or not changes:
        raise CardChangeInvalid("changeset must be a non-empty mapping")
    out: dict[str, Any] = {}
    for key, value in changes.items():
        shape = _FIELD_SHAPE.get(key)
        if shape is None:
            raise CardChangeInvalid(f"unknown card field: {key}")
        if value is None:
            out[key] = None  # 显式清除
            continue
        if shape == "text":
            if not isinstance(value, str):
                raise CardChangeInvalid(f"{key} must be a string")
            text = value.strip()
            if not text:
                out[key] = None  # 空白等同清除
                continue
            limit = MAX_NAME_CHARS if key == "name" else MAX_TEXT_CHARS
            if len(text) > limit:
                raise CardChangeInvalid(f"{key} exceeds {limit} characters")
            out[key] = text
        elif shape == "voice":
            if not isinstance(value, dict) or not value:
                raise CardChangeInvalid("voice must be a non-empty mapping")
            unknown = set(value) - _VOICE_KEYS
            if unknown:
                raise CardChangeInvalid(f"unknown voice keys: {sorted(unknown)}")
            out[key] = dict(value)
        else:  # boundaries
            if not isinstance(value, (list, tuple)):
                raise CardChangeInvalid("boundaries must be a list of strings")
            items = [str(v).strip() for v in value if str(v).strip()]
            if len(items) > MAX_BOUNDARIES:
                raise CardChangeInvalid(f"at most {MAX_BOUNDARIES} boundaries")
            if any(len(v) > MAX_BOUNDARY_CHARS for v in items):
                raise CardChangeInvalid(f"each boundary ≤ {MAX_BOUNDARY_CHARS} characters")
            out[key] = items
    if all(v is None for v in out.values()):
        raise CardChangeInvalid("changeset clears everything and sets nothing")
    return out


def merge_chain(base: dict[str, Any], changesets: list[dict[str, Any]]) -> dict[str, Any]:
    """按顺序把变更集叠在基准上：后写覆盖先写；None 清除字段；dict/list 整值替换。

    不修改入参。changesets 的**顺序**就是版本顺序（调用方按 version 升序传入）。
    """
    merged = dict(base)
    for changes in changesets:
        for key, value in changes.items():
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
    return merged


_LABELS = [
    ("name", "名字"),
    ("tagline", "一句话"),
    ("description", "角色描述"),
    ("personality", "性格"),
    ("scenario", "场景"),
    ("voice", "声音偏好"),
]


def render_card_lines(fields: dict[str, Any]) -> list[str]:
    """把合并后的卡渲染成紧凑行（每行一个事实）。顺序固定，保证可复现。

    voice 整值摊平成 ``k=v``；boundaries 每条一行——记忆页与 prompt 注入共用这个形状。
    """
    lines: list[str] = []
    for key, label in _LABELS:
        value = fields.get(key)
        if value is None:
            continue
        if isinstance(value, dict):
            rendered = ", ".join(f"{k}={value[k]}" for k in sorted(value))
            lines.append(f"- {label}：{rendered}")
        else:
            lines.append(f"- {label}：{value}")
    for boundary in fields.get("boundaries") or []:
        lines.append(f"- 关系边界：{boundary}")
    return lines
