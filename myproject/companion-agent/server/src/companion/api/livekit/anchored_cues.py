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
        caps = self._caps()
        compiled = compile_cues(
            intents,
            speech_id=speech_id,
            seg_idx=seg_idx,
            caps=caps,
            budget=self._budget,
        )
        sent = 0
        for cue in compiled:
            if await self._send(cue):
                sent += 1
        return sent

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
