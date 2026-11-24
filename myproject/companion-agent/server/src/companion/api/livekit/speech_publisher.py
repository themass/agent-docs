"""把 LLM 出的句子变成 ``speech.seg`` / ``speech.end`` / ``control.cancel``（§9.3 / §10）。

不 import livekit：只依赖 :class:`ProtocolBridge` 的方法，单测直接喂假 bridge。

顺序是本模块存在的理由（§13 不变量 1）：每一句在交给 TTS 之前，它的 ``speech.seg``
必须已经发出去。所以调用方要 ``await say(...)`` 之后才 ``yield`` 这一句；挂在这句上
的 presentation cue 也必须在 ``say`` 返回的 ``(speech_id, seg)`` 之后再发。

角色状态（契约 v2 §1）也挂在这里：``state_sink``（``(state) -> bool``，真实装配里
就是 ``bridge.presentation_state``）在回合边界发 ``thinking`` / ``speaking`` /
``idle`` / ``interrupted``。顺序与 §13-1 一致：``speaking`` 先于该段的 ``speech.seg``。
状态是表现层旁路：发不出去不影响语音本体。

所有方法都不抛：语音时间线是旁路，发不出去只意味着表现层没有时间锚点，不能拖停通话。
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass

from companion.agent.protocol.speech_plan import (
    PlannedSegment,
    SpeechStream,
    spoken_prefix,
)
from companion.api.livekit.protocol_bridge import ProtocolBridge

logger = logging.getLogger(__name__)

#: 状态词汇（契约 v2 §1，小写）——这里只用服务端会发的四个；``listening`` 是端侧本地推导。
STATE_THINKING = "thinking"
STATE_SPEAKING = "speaking"
STATE_IDLE = "idle"
STATE_INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class SpokenPrefix:
    """打断时刻的「已经说出口」快照（契约 v2 §2.2）。

    ``chars`` 是要写进 ``ca_chat_message.meta.spoken_prefix_chars`` 的字符数；
    ``text`` 是给 ``HistoryService.note_interrupted`` 的前缀（线程里只补记她真正
    说过的部分）。拿不到端侧 ``played_ms`` 时返回 ``None``——上层按「退回全量」
    处理，与改动前的行为一致。
    """

    speech_id: str
    turn_id: str
    text: str
    chars: int


class SpeechPublisher:
    """一个房间一个。同一时刻最多一条打开的 speech（一回合一条，§9.3）。"""

    def __init__(self, bridge: ProtocolBridge, *, state_sink: Callable[[str], bool] | None = None) -> None:
        self._bridge = bridge
        self._state_sink = state_sink
        self._stream: SpeechStream | None = None
        self._open = False
        # 本回合已声明的段。前缀计算要的就是这份——它是端侧 played_ms 唯一能对上的序列。
        self._segments: list[PlannedSegment] = []
        # 发过 ``thinking`` 还没收回：回合开着，但可能一段都没声明（未握手 / 全空白）。
        # finish 时即便没有 speech 也要把状态收回到 idle，否则端侧卡在 thinking。
        self._state_open = False

    @property
    def open_speech_id(self) -> str | None:
        return self._stream.speech_id if self._open and self._stream is not None else None

    async def say(self, text: str, *, turn_id: str) -> tuple[str, PlannedSegment] | None:
        """登记一句。在把它交给 TTS 之前调用。

        每句发一条 ``speech.seg``。成功时返回 ``(speech_id, PlannedSegment)``，调用方
        用它给同句的 presentation cue 挂 ``at``；失败 / 空白 / 超段数返回 ``None``
        （句子仍可朗读，只是没有锚点）。

        第一句若发不出去（未握手 / 未协商），本回合不再声明，下一句重新开始一条新的
        speech；之后的句子照样会被说出来。
        """
        try:
            if self._stream is None:
                self._stream = SpeechStream(turn_id=turn_id)
            seg = self._stream.push(text)
            if seg is None:
                return None                      # 空白，或已超过段数上限：说，但不声明
            speech_id = self._stream.speech_id
            # §13-1 / 契约 v2 §1 顺序：state(speaking) → speech.seg → cue → TTS。
            # 每段首发前发一次 speaking：端侧状态机幂等，换来「她确实在说这一段」的
            # 显式边界，端侧不必从 speech.seg 反推状态。
            await self._send_state(STATE_SPEAKING)
            sent = await self._bridge.speech_seg(speech_id, seg)
            if not self._open:
                if sent:
                    self._open = True
                else:
                    # seg 没发出去：这一回合不再声明，下一句重新开始。
                    self._reset()
                    return None
            if sent:
                self._segments.append(seg)
            return (speech_id, seg) if sent else None
        except Exception:  # noqa: BLE001 —— 旁路，不能影响语音
            logger.warning("speech say failed", exc_info=True)
            return None

    async def finish(self) -> None:
        """本轮 TTS **生成侧**排空：收状态到 ``idle``，再发 ``speech.end``（§9.3）。

        这里的“出完”是服务端把本轮音频帧全部交给传输，**不是**扬声器播完——
        服务端没有播放时钟，也测不到端侧播到哪。因此 ``speech.end`` 常会早于
        端侧 ``t0``；端侧收到后标 DONE，但不因此取消尚未到点的 cue。

        没有打开的 speech 时不发 ``speech.end``（避免孤儿 end），但若发过
        ``thinking`` 仍要把状态收回 ``idle``。
        """
        speech_id = self.open_speech_id
        state_open = self._state_open
        self._reset()
        if state_open:
            await self._send_state(STATE_IDLE)
        if speech_id is None:
            return
        try:
            await self._bridge.speech_end(speech_id)
        except Exception:  # noqa: BLE001
            logger.warning("speech end failed id=%s", speech_id, exc_info=True)

    async def cancel(self, reason: str = "user_barge_in",
                     played_ms: int | None = None) -> SpokenPrefix | None:
        """该 speech 作废：``interrupted`` → ``control.cancel``（§10.2）。幂等。

        ``played_ms`` 是端侧上报的播放位置（契约 v2 §2.1，提示性字段）：给了就算出
        「已说话前缀」并返回；没给返回 ``None``，上层按退回全量处理。
        """
        speech_id = self.open_speech_id
        turn_id = self._stream.turn_id if self._stream is not None else ""
        segments = list(self._segments)
        state_open = self._state_open
        self._reset()
        if speech_id is None:
            # 没有可作废的 speech；若状态还挂在 thinking，把它收到 interrupted，
            # 否则端侧会一直显示「在想」直到下一回合开始。
            if state_open:
                await self._send_state(STATE_INTERRUPTED)
            return None
        prefix = spoken_prefix(segments, int(played_ms)) if played_ms else None
        await self._send_state(STATE_INTERRUPTED)
        try:
            await self._bridge.cancel_speech(speech_id, reason=reason)
        except Exception:  # noqa: BLE001
            logger.warning("speech cancel failed id=%s", speech_id, exc_info=True)
        if prefix is None:
            return None
        text, chars = prefix
        return SpokenPrefix(speech_id=speech_id, turn_id=turn_id, text=text, chars=chars)

    async def start_reply(self) -> None:
        """新回合开始：先把上一回合挂着的 speech 按打断作废，再发 ``thinking``。

        规格里 ``control.cancel`` 的 reason 只定义了 ``user_barge_in``。新回合只在用户开口之后
        才会开始，所以把这种情况也记作 ``user_barge_in`` 是准确的。

        ``thinking`` 在语音回合开始生成时发（契约 v2 §1）。
        """
        if self.open_speech_id is not None:
            await self.cancel()
        self._reset()
        await self._send_state(STATE_THINKING)
        self._state_open = True

    async def _send_state(self, state: str) -> bool:
        """发一条 ``presentation.state``。没接 state_sink 或发送失败都返回 False。

        sink 可以是同步（假对象）或 async（``bridge.presentation_state``）——与
        ``on_barge`` 同样的鸭子约定，见 protocol_bridge。
        """
        if self._state_sink is None:
            return False
        try:
            result = self._state_sink(state)
            if inspect.isawaitable(result):
                result = await result
            return bool(result)
        except Exception:  # noqa: BLE001 —— 状态是表现层旁路
            logger.warning("presentation.state %s failed", state, exc_info=True)
            return False

    def _reset(self) -> None:
        self._stream = None
        self._open = False
        self._segments = []
        self._state_open = False
