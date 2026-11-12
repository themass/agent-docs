"""语音回合的大脑：不自己跑模型，而是把话交给文字聊天同一条提交路径。

原来的语音链路是 ``TurnPipeline`` 直连大脑：说的话不落库、不拿会话锁、没有对话线程、
不触发 ``after_turn``（记忆、画像、时间线）。同一个用户在同一个会话里，文字和语音
成了两份互不相干的历史。

这里换成：语音识别出的文字走 ``SubmitService.submit``（与文字输入框完全相同），回合由
``TurnRunner`` 执行并落库；本类只负责把这一回合的 ``message.delta`` 事件当作 token 流
交还给 ``TurnPipeline``，由它断句、剥情绪标签、交给 TTS。这样断句与打断逻辑不变，
变的只有“文字从哪来”：从回合事件流，而不是直连大脑。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from companion.domain.turn.queue import Disposition
from companion.ports.brain import BrainTurn, TurnRequest

logger = logging.getLogger(__name__)

# 一个回合从提交到结束的上限。到了就收尾，不让房间一直静音等一个已经卡死的回合。
DEFAULT_TURN_TIMEOUT_SEC = 120.0
_POLL_MS = 1000
_END_EVENTS = frozenset({"message.done", "turn.cancelled", "error"})


class TurnRefused(Exception):
    """输入被拒绝（内容安全等）。语音端应该告诉用户“这个我不能聊”，而不是沉默。"""

    def __init__(self, reason: str | None) -> None:
        super().__init__(reason or "refused")
        self.reason = reason or ""


class PlatformBrain:
    """``BrainPort`` 的实现：提交到平台，读回同一回合的文字流。"""

    def __init__(self, *, submit: Any, control: Any, turn_timeout_sec: float = DEFAULT_TURN_TIMEOUT_SEC,
                 role: str = "user", kind: str = "voice") -> None:
        """``role`` / ``kind`` 是这条输入在历史里的身份：语音是 user/voice；
        服务端主动开口是 system/proactive（模型看到的是一条带标记的指令，不是用户说的话）。"""
        self._submit = submit
        self._control = control
        self._timeout = turn_timeout_sec
        self._role = role
        self._kind = kind

    async def start_turn(self, request: TurnRequest) -> BrainTurn:
        if request.session_id is None:
            # 没有会话就没有历史可共享：这是装配错误，不是运行时可以绕过的情况
            raise ValueError("voice turn needs a chat session id")
        try:
            owner_id = int(request.user_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"user id must be numeric, got {request.user_id!r}") from exc

        # 先记游标再提交：回合可能在 submit 返回前就开始吐字，晚记会漏掉开头几个字
        cursor = await self._control.tail_event_id(session_id=request.session_id)
        result = await self._submit.submit(
            owner_id=owner_id, session_id=request.session_id, character_id=request.character_id,
            text=request.message, client_message_id=None,
            # 语音一次一句，用户说完才提交；不做“插话进正在跑的回合”
            steerable=False,
            # 来源标记：转写文字和打字的区别在这里，质检与记忆降置信度都靠它
            role=self._role, kind=self._kind)

        if result.status == "denied":
            raise TurnRefused(getattr(result, "reason", None))
        if result.status != "accepted" or result.disposition is not Disposition.STARTED or not result.turn_id:
            # 重复，或会话正忙已排队：这句话已经落库，由当前回合结束后的 drain 接着处理。
            # 语音端不挂等一个还没开始的回合，否则用户会听到别的回合的内容。
            logger.info("voice turn not started status=%s disposition=%s", result.status, result.disposition)
            return BrainTurn(tokens=_empty(), cancel=_noop, turn_id=result.turn_id or "")

        turn_id = result.turn_id
        control, session_id, timeout = self._control, request.session_id, self._timeout

        async def tokens() -> AsyncIterator[str]:
            deadline = time.monotonic() + timeout
            after = cursor
            while time.monotonic() < deadline:
                events = await control.wait_events(session_id=session_id, after_id=after, block_ms=_POLL_MS)
                for entry_id, name, data in events:
                    after = entry_id
                    if data.get("turn_id") != turn_id:
                        continue
                    if name == "message.delta":
                        delta = data.get("delta")
                        if delta:
                            yield str(delta)
                    elif name in _END_EVENTS:
                        return
            logger.warning("voice turn timed out turn=%s", turn_id)

        async def cancel() -> None:
            await control.send_cancel(turn_id=turn_id)

        return BrainTurn(tokens=tokens(), cancel=cancel, turn_id=turn_id)

    async def aclose(self) -> None:
        # 提交服务与控制面由 platform 持有并关闭
        return None


async def _empty() -> AsyncIterator[str]:
    return
    yield ""  # pragma: no cover  让它成为异步生成器


async def _noop() -> None:
    await asyncio.sleep(0)
