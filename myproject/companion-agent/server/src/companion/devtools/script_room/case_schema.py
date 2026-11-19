"""YAML 剧本 case 的加载与校验。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_ALLOWED_AUDIOS_PREFIXES = ("synthesize", "none", "fixture:")


@dataclass(frozen=True)
class Step:
    """一步剧本动作。四种互斥字段与 YAML 键一一对应。"""

    user: str | None = None
    expect_reply: tuple[str, ...] | None = None
    protocol: tuple[str, ...] | None = None
    inject: str | None = None


@dataclass(frozen=True)
class ScriptCase:
    id: str
    goal: str
    steps: list[Step]
    audios: str = "synthesize"


def load_case(path: Path) -> ScriptCase:
    """读 YAML → :class:`ScriptCase`。缺必填字段或形状不对就 ValueError。"""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"case root must be a mapping: {path}")
    case_id = raw.get("id")
    goal = raw.get("goal", "")
    audios = raw.get("audios", "synthesize")
    steps_raw = raw.get("steps")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError(f"case.id required: {path}")
    if not isinstance(goal, str):
        raise ValueError(f"case.goal must be str: {path}")
    if not isinstance(audios, str) or not audios.strip():
        raise ValueError(f"case.audios must be non-empty str: {path}")
    if not any(
        audios == p or (p.endswith(":") and audios.startswith(p)) for p in _ALLOWED_AUDIOS_PREFIXES
    ):
        raise ValueError(f"case.audios unsupported {audios!r}: {path}")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ValueError(f"case.steps must be a non-empty list: {path}")
    steps = [_parse_step(item, path=path, index=i) for i, item in enumerate(steps_raw)]
    return ScriptCase(id=case_id.strip(), goal=goal, steps=steps, audios=audios.strip())


def _parse_step(item: Any, *, path: Path, index: int) -> Step:
    if not isinstance(item, dict) or not item:
        raise ValueError(f"steps[{index}] must be a non-empty mapping: {path}")
    keys = set(item)
    known = {"user", "expect_reply", "protocol", "inject"}
    if not keys <= known:
        raise ValueError(f"steps[{index}] unknown keys {keys - known}: {path}")
    if len(keys) != 1:
        raise ValueError(f"steps[{index}] must have exactly one of {sorted(known)}: {path}")

    if "user" in item:
        user = item["user"]
        if not isinstance(user, str):
            raise ValueError(f"steps[{index}].user must be str: {path}")
        return Step(user=user)

    if "expect_reply" in item:
        lines = item["expect_reply"]
        if isinstance(lines, str):
            lines = [lines]
        if not isinstance(lines, list) or not lines or not all(isinstance(x, str) for x in lines):
            raise ValueError(f"steps[{index}].expect_reply must be str or list[str]: {path}")
        return Step(expect_reply=tuple(lines))

    if "protocol" in item:
        events = item["protocol"]
        if not isinstance(events, list) or not all(isinstance(x, str) for x in events):
            raise ValueError(f"steps[{index}].protocol must be list[str]: {path}")
        return Step(protocol=tuple(events))

    inject = item["inject"]
    if not isinstance(inject, str) or not inject.strip():
        raise ValueError(f"steps[{index}].inject must be non-empty str: {path}")
    return Step(inject=inject.strip())
