"""把编译好的 cue 按 §13 不变量 1 发出去：先有 ``speech.seg(k)``，再发挂着它的 cue。

调用方必须在 ``SpeechPublisher.say`` 返回之后、把文本交给 TTS 之前调用。
caps 取自当前握手交集；未握手时整批跳过（bridge 自己会记 ``unsent``）。
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any

from companion.agent.protocol.cue_compiler import CompiledCue, CompileStats, CueBudget, compile_cues
from companion.agent.protocol.cue_intent import CueIntent
from companion.agent.protocol.catalog import TOPIC_CUE
from companion.api.livekit.protocol_bridge import ProtocolBridge

logger = logging.getLogger(__name__)

#: 端侧梯子的最高档（§12.3 L0–L4）。看不懂的数字档位按它处理。
_MAX_LEVEL = 4

#: L1 起端侧 `DegradeController.shouldEmit` 仍会放行的 kind。
#: emotion 留在服务端全发、端上自己半频丢；gesture/gaze 端上直接丢，这里就别占弱网带宽。
_LEVEL1_KINDS = frozenset({"emotion"})


def _degrade_level(telemetry: object) -> int:
    """从客户端自报的 ``telemetry.health`` 里取档位，取不到按 0。

    垃圾字符串（``"degraded"``）回退 0：照发最差也就是客户端丢包前的现状，
    而误判成高段会把她的表情整条抹掉。数字越界往 L4 夹——能写出 L9 的
    只会是真降级的怪值，不该多占带宽。
    """
    if not isinstance(telemetry, dict):
        return 0
    raw = telemetry.get("degrade_level")
    if not isinstance(raw, str):
        return 0
    text = raw.strip().upper()
    if not text.startswith("L"):
        return 0
    try:
        level = int(text[1:])
    except ValueError:
        return 0
    if level < 0:
        return 0
    return min(level, _MAX_LEVEL)


class AnchoredCuePublisher:
    """一个房间一个。跨段共享回合预算（每回合 ≤4 条）。"""

    def __init__(self, bridge: ProtocolBridge) -> None:
        self._bridge = bridge
        self._budget = CueBudget()

    @property
    def stats(self) -> CompileStats:
        return self._budget.stats

    def reset_turn(self) -> None:
        """新回合开始时清预算；计数桶跨回合保留（诊断用）。"""
        kept = self._budget.stats
        self._budget = CueBudget(stats=kept)

    async def publish_for_segment(
        self,
        intents: Iterable[CueIntent],
        *,
        speech_id: str,
        seg_idx: int,
        source: str = "tag",
    ) -> int:
        """编译并发送本段 cue。返回实际发出的条数。"""
        self._budget.stats.note_source(source)
        level = _degrade_level(getattr(self._bridge, "telemetry", None))
        caps = self._caps()
        compiled = compile_cues(
            self._gate(intents, level, speech_id=speech_id, seg_idx=seg_idx),
            speech_id=speech_id,
            seg_idx=seg_idx,
            caps=caps,
            budget=self._budget,
        )
        sent = 0
        for cue in compiled:
            if await self._send(cue):
                sent += 1
                # 「服务端有没有发 cue」以前只能从静默的 publish 反推——11-23 对账
                # 拿 `grep presentation.emotion` 判没发，而正常发送本来就没有这一行。
                # 发一条记一条，下次排障直接 grep。
                logger.info("cue sent t=%s speech=%s seg=%d", cue.event_type, speech_id, seg_idx)
        return sent

    def _gate(self, intents: Iterable[CueIntent], level: int, *,
              speech_id: str = "", seg_idx: int = 0) -> list[CueIntent]:
        """按端侧自报档位丢掉「客户端反正会丢」的意图，并计数。

        丢在编译前而不是发送后：降级的意图不该再占每段/每回合的预算——
        弱网时 budget 是给 emotion 这类还要保的 cue 用的。
        """
        if level <= 0:
            return list(intents)
        allowed = _LEVEL1_KINDS if level == 1 else frozenset()
        kept: list[CueIntent] = []
        dropped = 0
        for intent in intents:
            if intent.kind in allowed:
                kept.append(intent)
            else:
                dropped += 1
                self._budget.stats.cues_dropped_degrade += 1
        # 闸掉也要留痕：11-23 三个陪伴通话 job 的 cue 全被 L3 闸掉，voice.log 里
        # 却与「模型没生成 cue」一模一样。没这行，两种成因无法区分。
        if dropped:
            logger.info("cue gate speech=%s seg=%d level=L%d dropped=%d kept=%d",
                        speech_id, seg_idx, level, dropped, len(kept))
        return kept

    def _caps(self) -> Mapping[str, int]:
        ack = self._bridge.ack
        if ack is None or ack.compat != "v2":
            return {}
        return ack.caps

    async def _send(self, cue: CompiledCue) -> bool:
        try:
            return await self._bridge.publish(
                cue.event_type, cue.args, topic=TOPIC_CUE, at=cue.at
            )
        except Exception:  # noqa: BLE001 —— 旁路
            logger.warning("anchored cue publish failed t=%s", cue.event_type, exc_info=True)
            return False
