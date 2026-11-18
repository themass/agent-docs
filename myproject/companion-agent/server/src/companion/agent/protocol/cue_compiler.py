"""CueCompiler：意图 → 带 ``at`` 的可发布 cue（§13 / v1 §7.1）。

顺序与上限是本模块存在的理由：

1. 只发协商过的能力（F12 = caps 交集；本轮 gesture/gaze 仍为 0）。
2. 每段 ≤ :data:`MAX_CUES_PER_SEG`，每回合 ≤ :data:`MAX_CUES_PER_TURN`。
3. 给每条挂上 ``at={speech, seg, phase}``，保证端侧能锚到 ``speech.seg(k)``。
4. 编码后超 :data:`MAX_PAYLOAD_BYTES` 的整条丢掉并计数（§13 不变量 3）。

纯函数 + 可选计数桶；不碰网络。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from companion.agent.protocol.cue_intent import EVENT_FOR_KIND, CueIntent
from companion.agent.protocol.envelope import MAX_PAYLOAD_BYTES, encode, new_envelope

MAX_CUES_PER_SEG = 2
MAX_CUES_PER_TURN = 4


@dataclass(frozen=True)
class CompiledCue:
    """一条准备交给 ``ProtocolBridge.publish`` 的表现指令。"""

    event_type: str
    args: dict[str, Any]
    at: dict[str, Any]


@dataclass
class CompileStats:
    """编译期计数（§14.3）。调用方可累加到 bridge / 进程级桶。"""

    structured_hits: int = 0
    tag_fallback: int = 0
    cues_emitted: int = 0
    cues_dropped_cap: int = 0
    cues_dropped_unsupported: int = 0
    cues_dropped_overflow: int = 0
    cues_dropped_bad: int = 0

    def note_source(self, source: str) -> None:
        if source == "structured":
            self.structured_hits += 1
        else:
            self.tag_fallback += 1


@dataclass
class CueBudget:
    """跨段共享的回合预算。一个 ``SpeechPublisher`` / 回合一个。"""

    remaining: int = MAX_CUES_PER_TURN
    stats: CompileStats = field(default_factory=CompileStats)


def compile_cues(
    intents: Iterable[CueIntent],
    *,
    speech_id: str,
    seg_idx: int,
    caps: Mapping[str, int] | None = None,
    budget: CueBudget | None = None,
) -> list[CompiledCue]:
    """把意图编译成带锚点的 cue 列表。

    ``caps`` 形如握手交集（``{presentation.emotion: 1, ...}``）；``None`` 视为
    只开 emotion（与当前 :data:`SERVER_CAPS` 一致），避免测试每次手填。
    """
    if budget is None:
        budget = CueBudget()
    caps_map = dict(caps) if caps is not None else {"presentation.emotion": 1}
    out: list[CompiledCue] = []

    for intent in intents:
        if len(out) >= MAX_CUES_PER_SEG or budget.remaining <= 0:
            budget.stats.cues_dropped_cap += 1
            continue
        event_type = EVENT_FOR_KIND.get(intent.kind)
        if event_type is None:
            budget.stats.cues_dropped_bad += 1
            continue
        if caps_map.get(event_type, 0) <= 0:
            budget.stats.cues_dropped_unsupported += 1
            continue
        if not intent.name:
            budget.stats.cues_dropped_bad += 1
            continue

        args: dict[str, Any] = {"name": intent.name}
        for key, value in intent.params.items():
            if key == "name":
                continue
            args[key] = value
        at = {"speech": speech_id, "seg": seg_idx, "phase": intent.phase}
        compiled = CompiledCue(event_type=event_type, args=args, at=at)
        if _overflows(compiled):
            budget.stats.cues_dropped_overflow += 1
            continue
        out.append(compiled)
        budget.remaining -= 1
        budget.stats.cues_emitted += 1
    return out


def _overflows(cue: CompiledCue) -> bool:
    """用真实编码器量一下：超限就丢，绝不分批（§14.1）。"""
    try:
        encode(
            new_envelope(
                cue.event_type,
                args=cue.args,
                seq=0,
                ep="x",
                ident="overflow-check",
                at=cue.at,
            )
        )
    except ValueError:
        return True
    return False
