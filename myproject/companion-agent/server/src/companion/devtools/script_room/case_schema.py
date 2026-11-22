"""YAML 剧本 case 的加载与校验。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_ALLOWED_AUDIOS_PREFIXES = ("synthesize", "none", "fixture:")

#: 剧本房的两种跑法。
#: ``push``（默认）——把 YAML 里的 ``expect_reply`` 当台词推给房间：全程不调模型，
#: 也不碰 ``control.input`` 的附件槽，所以它验不了「图真的进了模型」。
#: ``real_turn``——用户 participant 在房里依次发 ``control.input(kind=attachments)`` 与
#: ``lk.chat`` 文字，房间里的 agent 走生产那一套装配把回合跑完，说的话由**真模型看着图**生成，
#: 再用 :attr:`RealTurn.keyword_family` 断言回复回扣了图内内容。见 ``real_turn.py``。
MODE_PUSH = "push"
MODE_REAL_TURN = "real_turn"
MODES = (MODE_PUSH, MODE_REAL_TURN)


@dataclass(frozen=True)
class RealTurn:
    """``mode: real_turn`` 的 case 独有的三样东西。

    ``fixture`` 是 :mod:`companion.devtools.script_room.real_turn` 里的机器生成图（内容已知，
    所以关键词族才敢写死）；``text`` 是那句 ``lk.chat`` 文字；``keyword_family`` 是图内要素的
    **一族**关键词，回复命中任一即算「引用了图内内容」——模型换措辞、中英混说都不该假红。
    """

    fixture: str
    text: str
    keyword_family: tuple[str, ...]


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
    #: 见 :data:`MODE_PUSH` / :data:`MODE_REAL_TURN`。
    mode: str = MODE_PUSH
    #: 仅 ``mode == MODE_REAL_TURN`` 时有值；push 模式恒为 ``None``。
    real_turn: RealTurn | None = None


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
    mode = raw.get("mode", MODE_PUSH)
    if not isinstance(mode, str) or mode not in MODES:
        raise ValueError(f"case.mode unsupported {mode!r} (expected one of {MODES}): {path}")
    real_turn = _parse_real_turn(raw.get("real_turn"), path=path, mode=mode)
    return ScriptCase(id=case_id.strip(), goal=goal, steps=steps, audios=audios.strip(),
                      mode=mode, real_turn=real_turn)


def _parse_real_turn(item: Any, *, path: Path, mode: str) -> RealTurn | None:
    """校验 ``real_turn`` 块，并与 ``mode`` 对齐。

    两个方向都要挡：real_turn 模式下缺块（跑不起来，且失败点在一个跑完真模型调用、
    花掉钱之后才出现，越晚越贵），以及 push 模式下多一个块（会被静默忽略，
    写的人以为在跑真回合）。
    """
    if mode != MODE_REAL_TURN:
        if item is not None:
            raise ValueError(f"case.real_turn requires mode: {MODE_REAL_TURN}: {path}")
        return None
    if not isinstance(item, dict):
        raise ValueError(f"case.real_turn must be a mapping when mode: {MODE_REAL_TURN}: {path}")

    keys = set(item)
    known = {"fixture", "text", "any_of"}
    if not keys <= known:
        raise ValueError(f"case.real_turn unknown keys {keys - known}: {path}")
    for name in ("fixture", "text"):
        value = item.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"case.real_turn.{name} must be a non-empty str: {path}")

    family = item["any_of"]
    if isinstance(family, str):
        family = [family]
    if not isinstance(family, list) or not family or not all(isinstance(x, str) and x.strip() for x in family):
        raise ValueError(f"case.real_turn.any_of must be a non-empty list[str]: {path}")

    return RealTurn(fixture=item["fixture"].strip(), text=item["text"].strip(),
                    keyword_family=tuple(x.strip() for x in family))


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
