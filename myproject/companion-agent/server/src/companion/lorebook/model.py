"""世界书条目与从角色卡 ``character_book`` 的转换。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

LOGICS = ("and_any", "not_all", "not_any", "and_all")
POSITIONS = ("before_char", "after_char", "at_depth")

# SillyTavern 在 entry.extensions 里用整数编码：selectiveLogic 0..3、position 0..7、role 0..2。
_ST_LOGIC = {0: "and_any", 1: "not_all", 2: "not_any", 3: "and_all"}
_ST_POSITION = {0: "before_char", 1: "after_char", 4: "at_depth"}
_ST_ROLE = {0: "system", 1: "user", 2: "assistant"}

MAX_KEY_CHARS = 200


@dataclass(frozen=True)
class LoreEntry:
    uid: str
    keys: tuple[str, ...]
    content: str
    secondary_keys: tuple[str, ...] = ()
    logic: str = "and_any"
    constant: bool = False
    enabled: bool = True
    position: str = "before_char"
    depth: int = 4
    role: str = "system"
    order: int = 100
    case_sensitive: bool = False
    whole_word: bool = False
    scan_depth: int | None = None

    def __post_init__(self) -> None:
        if self.logic not in LOGICS:
            raise ValueError(f"logic must be one of {LOGICS}")
        if self.position not in POSITIONS:
            raise ValueError(f"position must be one of {POSITIONS}")


@dataclass(frozen=True)
class Lorebook:
    entries: tuple[LoreEntry, ...]
    scan_depth: int = 2                  # 扫描最近几条消息
    budget_chars: int | None = None      # 本书的预算上限；None 时用调用方的预算
    unsupported: tuple[str, ...] = ()    # 第一版不支持、已按「角色前」处理的条目 uid


def _keys(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return ()
    return tuple(k.strip()[:MAX_KEY_CHARS] for k in value if isinstance(k, str) and k.strip())


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def from_character_book(book: Mapping[str, Any] | None) -> Lorebook | None:
    """把 V2/V3 的 ``character_book`` 转成 Lorebook。无效条目跳过，不抛错（卡片来自用户）。"""
    if not book:
        return None
    raw_entries = book.get("entries")
    if isinstance(raw_entries, Mapping):  # SillyTavern 导出的 world 文件是 {uid: entry}
        raw_entries = list(raw_entries.values())
    if not isinstance(raw_entries, list):
        return None

    entries: list[LoreEntry] = []
    unsupported: list[str] = []
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, Mapping):
            continue
        ext = raw.get("extensions") if isinstance(raw.get("extensions"), Mapping) else {}
        uid = str(raw.get("id", raw.get("uid", index)))
        content = str(raw.get("content") or "").strip()
        if not content:
            continue

        position = "before_char"
        if "position" in ext:
            code = _int(ext.get("position"), 0)
            position = _ST_POSITION.get(code, "before_char")
            if code not in _ST_POSITION:
                unsupported.append(uid)
        elif raw.get("position") in ("before_char", "after_char"):
            position = str(raw["position"])

        selective = bool(raw.get("selective", False))
        secondary = _keys(raw.get("secondary_keys")) if selective else ()
        entries.append(LoreEntry(
            uid=uid,
            keys=_keys(raw.get("keys")),
            content=content,
            secondary_keys=secondary,
            logic=_ST_LOGIC.get(_int(ext.get("selectiveLogic"), 0), "and_any"),
            constant=bool(raw.get("constant", False)),
            enabled=bool(raw.get("enabled", True)),
            position=position,
            depth=max(0, _int(ext.get("depth"), 4)),
            role=_ST_ROLE.get(_int(ext.get("role"), 0), "system"),
            order=_int(raw.get("insertion_order", raw.get("order")), 100),
            case_sensitive=bool(raw.get("case_sensitive") or ext.get("case_sensitive") or False),
            whole_word=bool(ext.get("match_whole_words") or False),
            scan_depth=_int(ext.get("scan_depth"), 0) or None,
        ))

    return Lorebook(
        entries=tuple(entries),
        scan_depth=max(1, _int(book.get("scan_depth"), 2)),
        budget_chars=_int(book.get("token_budget"), 0) or None,
        unsupported=tuple(unsupported),
    )
