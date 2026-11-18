"""把 LLM 出的句子变成 ``speech.begin`` / ``speech.extend`` / ``speech.end`` / ``control.cancel``（§9.3.1 / §10）。

不 import livekit：只依赖 :class:`ProtocolBridge` 的方法，单测直接喂假 bridge。

顺序是本模块存在的理由（§13 不变量 1）：每一句在交给 TTS 之前，它的 ``speech.begin``
或 ``speech.extend`` 必须已经发出去。所以调用方要 ``await say(...)`` 之后才 ``yield`` 这一句。

所有方法都不抛：语音时间线是旁路，发不出去只意味着表现层没有时间锚点，不能拖停通话。
"""

from __future__ import annotations

import logging

from companion.agent.protocol.speech_plan import SpeechStream
from companion.api.livekit.protocol_bridge import ProtocolBridge

logger = logging.getLogger(__name__)


class SpeechPublisher:
    """一个房间一个。同一时刻最多一条打开的 speech（一回合一条，§9.3）。"""

    def __init__(self, bridge: ProtocolBridge) -> None:
        self._bridge = bridge
        self._stream: SpeechStream | None = None
        self._open = False

    @property
    def open_speech_id(self) -> str | None:
        return self._stream.speech_id if self._open and self._stream is not None else None

    async def say(self, text: str, *, turn_id: str) -> None:
        """登记一句。在把它交给 TTS 之前调用。

        第一句发 ``speech.begin``（只带这一段）；之后每句发一条 ``speech.extend``。
        未协商 ``speech.extend`` 时之后的句子不声明，但照样会被说出来。
        """
        try:
            if self._stream is None:
                self._stream = SpeechStream(turn_id=turn_id)
            seg = self._stream.push(text)
            if seg is None:
                return                      # 空白，或已超过段数上限：说，但不声明
            if not self._open:
                sent = await self._bridge.speech_begin(self._stream.begin_plan(seg))
                if sent:
                    self._open = True
                else:
                    # begin 没发出去（未握手 / 未协商）：这一回合不再声明，下一句重新开始。
                    self._reset()
                return
            if self._bridge.can_batch():
                await self._bridge.speech_extend(self._stream.speech_id, (seg,))
        except Exception:  # noqa: BLE001 —— 旁路，不能影响语音
            logger.warning("speech say failed", exc_info=True)

    async def finish(self) -> None:
        """TTS 全部出完：``speech.end``。没有打开的 speech 时是空操作。"""
        speech_id = self.open_speech_id
        self._reset()
        if speech_id is None:
            return
        try:
            await self._bridge.speech_end(speech_id)
        except Exception:  # noqa: BLE001
            logger.warning("speech end failed id=%s", speech_id, exc_info=True)

    async def cancel(self, reason: str = "user_barge_in") -> None:
        """该 speech 作废：``control.cancel``（§10.2）。幂等。"""
        speech_id = self.open_speech_id
        self._reset()
        if speech_id is None:
            return
        try:
            await self._bridge.cancel_speech(speech_id, reason=reason)
        except Exception:  # noqa: BLE001
            logger.warning("speech cancel failed id=%s", speech_id, exc_info=True)

    async def start_reply(self) -> None:
        """新回合开始。上一回合的 speech 若还开着，按打断作废。

        规格里 ``control.cancel`` 的 reason 只定义了 ``user_barge_in``。新回合只在用户开口之后
        才会开始，所以把这种情况也记作 ``user_barge_in`` 是准确的。
        """
        if self.open_speech_id is not None:
            await self.cancel()
        self._reset()

    def _reset(self) -> None:
        self._stream = None
        self._open = False
