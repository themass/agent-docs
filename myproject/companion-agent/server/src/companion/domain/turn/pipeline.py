"""回合管线：主脑 token 流 → 可朗读整句 + 形象事件，并持有取消入口。

断句与事件编码来自 ``companion.text``，不在这里重写。这一层不依赖 LiveKit：
HTTP 的 SSE 接口与房间内的 ``llm_node`` 共用它，语音场景最难调的断句与打断
也就不必只在真机房间里验证。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from companion.ports.brain import BrainPort, BrainTurn, TurnRequest
from companion.domain.text.events import strip_emotion_tags, to_avatar_events
from companion.domain.text.splitter import SentenceSplitter

logger = logging.getLogger(__name__)

EventSink = Callable[[str], None]
"""形象事件的出口。真实实现写进 LiveKit 数据通道；测试里收集进列表。"""


@dataclass
class PipelineOutput:
    """管线每轮吐给上层的东西：一句可朗读的文本，和这轮产生的形象事件。"""

    text: str
    events: list[dict]


class TurnPipeline:
    def __init__(
        self,
        brain: BrainPort,
        splitter: SentenceSplitter | None = None,
        event_sink: EventSink | None = None,
    ) -> None:
        self._brain = brain
        self._splitter = splitter or SentenceSplitter()
        self._event_sink = event_sink
        # 保留当前回合的句柄：用户打断时要真的 call 到 cancel_turn()，
        # 只记一条日志等于没取消，DeerFlow 那边会继续烧 token。
        self._turn: BrainTurn | None = None
        self._last: BrainTurn | None = None
        self._cancelled = False

    async def run(self, request: TurnRequest) -> AsyncIterator[PipelineOutput]:
        """跑一个回合。

        - 主脑中途抛错：已断好的句子照常交付，然后正常结束。语音场景里整段作废
          比吞一个异常更糟。
        - 被取消（LiveKit 打断 / 生成器被 aclose）：先 cancel 主脑回合再退出。
        """
        turn = await self._brain.start_turn(request)
        self._turn = turn
        self._last = turn
        self._cancelled = False
        completed = False
        try:
            async for chunk in turn.tokens:
                for sentence in self._splitter.feed(chunk):
                    yield self._emit(sentence)
            for sentence in self._splitter.flush():
                yield self._emit(sentence)
            completed = True
        except (asyncio.CancelledError, GeneratorExit):
            await self.cancel()
            raise
        except Exception as exc:  # noqa: BLE001 —— 见 docstring
            logger.warning("brain failed mid-turn: %s", exc)
            for sentence in self._splitter.flush():
                yield self._emit(sentence)
            completed = True
        finally:
            if not completed:
                await self.cancel()
            self._turn = None

    async def cancel(self) -> None:
        """取消当前回合。幂等：重复调用只生效一次。"""
        if self._cancelled or self._turn is None:
            return
        self._cancelled = True
        try:
            await self._turn.cancel_turn()
        except Exception as exc:  # noqa: BLE001 - 取消失败不该把打断变成报错
            logger.warning("cancel failed: %s", exc)

    @property
    def last_turn(self) -> BrainTurn | None:
        """最近一次回合的句柄。回合结束后 ``turn_id`` 会清空，质检记录要在结束后读，所以单独留。"""
        return self._last

    @property
    def turn_id(self) -> str:
        return self._turn.turn_id if self._turn is not None else ""

    def _emit(self, sentence: str) -> PipelineOutput:
        clean, emotions = strip_emotion_tags(sentence)
        events = to_avatar_events(emotions, state=None)
        if self._event_sink is not None:
            for event in events:
                self._safe_sink(event)
        return PipelineOutput(text=clean, events=events)

    def _safe_sink(self, event: dict[str, Any]) -> None:
        # 数据通道发不出去不能影响正在进行的回复
        try:
            self._event_sink(json.dumps(event, ensure_ascii=False))  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001
            logger.debug("avatar event dropped: %s", exc)
