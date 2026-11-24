"""端侧 ``control.barge_in`` → 打断当前语音（§10 / 契约 v2 §2.2）。

协议：客户端检测到用户开口后，先本地把时间线作废，再发 ``control.barge_in``。
服务端这里要做三件事：

1. ``AgentSession.interrupt()`` —— 截断正在播 / 正在生成的 TTS（框架路径）。
2. ``SpeechPublisher.cancel(played_ms=...)`` —— 立刻发 ``control.cancel``，不等 TTS 生成器的
   finally。LLM 已 ``say`` 但 TTS 还没挂上时，只靠 interrupt 不会走到
   ``_speech_scoped`` 的 cancel 分支，墓碑会晚一拍。cancel 同时按端侧上报的
   ``played_ms`` 算出「已说话前缀」，写进回合状态（``note_spoken_prefix``），
   让回合收尾能把**说过的部分**补记进对话线程（契约 v2 §2.2）。
3. ``TurnPipeline.cancel()`` —— 停生成。只截音频不 ``send_cancel(turn_id)`` 的话，
   模型会继续把整段烧完（DeerFlow 侧继续产 token、继续计费）。

冷却挡住连发：VAD 抖动能在几百毫秒里打出多条 barge_in，每条都 interrupt
一次没有好处，还会把 ``control.cancel`` 消息量放大。
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_COOLDOWN_S = 0.4


def barge_args_ok(args: dict[str, Any] | None) -> bool:
    """``control.barge_in`` 的 args 是否可消费。

    ``speech_id`` / ``played_ms`` / ``reason`` 都是提示性字段：打断的目标是「当前
    正在说的那句」，不要求与客户端报的 id 严格相等（客户端可能已经本地 cancel
    掉了，服务端 open_speech_id 才是权威）。缺字段或类型不对时仍可打断——丢掉
    不如让她停下来。只有整包不是 dict 才拒绝。
    """
    return isinstance(args, dict)


def _played_ms(args: dict[str, Any]) -> int | None:
    """端侧上报的播放位置。缺失或非法返回 None——前缀宁可不写也不瞎猜。"""
    value = args.get("played_ms")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    played = int(value)
    return played if played > 0 else None


class BargeInRelay:
    """``ProtocolBridge.on_barge`` 的消费者：冷却 → interrupt → cancel speech → 停生成。

    ``session`` 只要有同步的 ``interrupt(*, force=False)``（LiveKit ``AgentSession``
    就是）；``speech`` 只要有 async ``cancel(reason=..., played_ms=...)``
    （``SpeechPublisher``）；``pipeline`` 只要有 async ``cancel()``（``TurnPipeline``）；
    ``control`` 只要有 async ``note_spoken_prefix(turn_id=..., chars=...)``
    （``RedisControl``）。单测喂假对象即可，缺哪个就跳过哪步。
    """

    def __init__(
        self,
        session: Any,
        speech: Any | None = None,
        *,
        pipeline: Any | None = None,
        control: Any | None = None,
        cooldown_s: float = DEFAULT_COOLDOWN_S,
    ) -> None:
        self._session = session
        self._speech = speech
        self._pipeline = pipeline
        self._control = control
        self._cooldown_s = max(0.0, float(cooldown_s))
        self._last_mono = 0.0
        self.accepted = 0
        self.ignored = 0

    async def __call__(self, args: dict[str, Any]) -> None:
        if not barge_args_ok(args):
            self.ignored += 1
            return

        now = time.monotonic()
        if self._cooldown_s > 0.0 and (now - self._last_mono) < self._cooldown_s:
            self.ignored += 1
            return
        self._last_mono = now

        interrupted = False
        try:
            self._session.interrupt()
            interrupted = True
        except Exception as exc:  # noqa: BLE001 —— §14.1：打断失败不拖停消息链
            # 没有在说话 / 当前句不允许打断时框架会抛；仍然尝试发 cancel。
            logger.info("barge interrupt skipped: %s", exc)

        cancelled = False
        prefix = None
        if self._speech is not None:
            try:
                prefix = await self._speech.cancel(reason="user_barge_in",
                                                    played_ms=_played_ms(args))
                cancelled = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("barge speech cancel failed: %s", exc)

        # 前缀要在停生成**之前**落进回合状态：cancel 一旦送达，TurnRunner 可能在
        # 下一个事件处就收尾，读前缀必须读得到。
        if prefix is not None and self._control is not None and prefix.turn_id:
            try:
                await self._control.note_spoken_prefix(turn_id=prefix.turn_id, chars=prefix.chars)
            except Exception as exc:  # noqa: BLE001 —— 前缀是旁路，不能拖停打断
                logger.warning("barge note_spoken_prefix failed turn=%s: %s", prefix.turn_id, exc)

        if self._pipeline is not None:
            try:
                await self._pipeline.cancel()
            except Exception as exc:  # noqa: BLE001 —— 停生成失败不能让打断半途而废
                logger.warning("barge pipeline cancel failed: %s", exc)

        if interrupted or cancelled:
            self.accepted += 1
        else:
            self.ignored += 1
