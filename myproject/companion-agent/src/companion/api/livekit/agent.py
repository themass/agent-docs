"""LiveKit 房间内的 agent：``llm_node`` 交给回合管线，自己只做壳。

重写 ``llm_node`` 让 DeerFlow 成为真正的主脑；TTS、VAD、打断、音频发布仍是
LiveKit Agents 的事。所有会写错的逻辑（断句、剥情绪标签、取消）都在
``TurnPipeline`` 里，这里只负责：读用户数据 → 组 ``TurnRequest`` → 转发管线输出。

livekit-agents 只在 ``build_agent_class`` 里导入，模块本身可以脱离它被 import，
否则 HTTP 接口与单测都会被语音栈连带拖垮。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from companion.domain.turn.pipeline import EventSink, TurnPipeline
from companion.ports.brain import TurnRequest
from companion.api.livekit.bridge import require

logger = logging.getLogger(__name__)

__all__ = ["build_agent_class", "build_event_sink", "build_request", "last_user_message"]


def build_request(*, user_id: str, character_id: str, message: str, instructions: str) -> TurnRequest:
    """组一回合的请求。

    线程由主脑实现按 ``user_id`` + ``character_id`` 管；这里不生成 thread_id，
    免得每次说话都开新线程、丢掉上文。
    """
    return TurnRequest(
        user_id=user_id or "anonymous",
        character_id=character_id or "default",
        message=message,
        system_prompt=instructions,
    )


def last_user_message(chat_ctx: Any) -> str:
    """取上下文里最后一条用户消息。

    ChatContext 的字段随版本变过，这里按「items → role/text_content」读，也兼容
    纯字符串 content 列表。读不到就返回空串：宁可不回复，也不要拿半截上下文去问。
    """
    items = getattr(chat_ctx, "items", None)
    if not items:
        return ""
    for item in reversed(list(items)):
        if getattr(item, "role", None) != "user":
            continue
        text = getattr(item, "text_content", None)
        if not isinstance(text, str) or not text.strip():
            content = getattr(item, "content", None)
            if isinstance(content, list):
                text = "".join(part for part in content if isinstance(part, str))
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


def build_event_sink(room: Any) -> EventSink:
    """把形象事件写成 LiveKit 数据通道里的文本消息。

    发送失败只记日志：事件是装饰，丢了不该让正在说的那句话出错。任务引用留在
    集合里，否则 ``publish_data`` 可能被 GC 提前回收。
    """
    pending: set[asyncio.Task[Any]] = set()

    def sink(payload: str) -> None:
        participant = getattr(room, "local_participant", None)
        if participant is None:
            return
        try:
            task = asyncio.create_task(_publish(participant, payload))
        except RuntimeError:
            # 没有运行中的事件循环（例如同步调用）——直接放弃，不阻塞回复
            logger.debug("avatar event dropped: no running loop")
            return
        pending.add(task)
        task.add_done_callback(pending.discard)

    async def _publish(participant: Any, payload: str) -> None:
        try:
            await participant.publish_data(payload.encode("utf-8"), reliable=True)
        except Exception as exc:  # noqa: BLE001
            logger.debug("avatar event publish failed: %s", exc)

    return sink


def build_agent_class() -> type:
    """构造 ``Agent`` 子类。父类必须在 import 时存在，所以包缺失在这里报错。"""
    require()

    from livekit.agents import Agent  # noqa: PLC0415 —— 见 docstring

    class CompanionAgent(Agent):
        """房间内的单个角色。依赖在房间建立时注入，agent 自己不查角色、不开线程。"""

        def __init__(
            self,
            *,
            pipeline: TurnPipeline,
            user_id: str,
            character_id: str,
            instructions: str,
        ) -> None:
            super().__init__(instructions=instructions)
            self._pipeline = pipeline
            self._user_id = user_id
            self._character_id = character_id
            self._instructions = instructions

        async def llm_node(
            self,
            chat_ctx: Any,
            tools: list[Any],
            model_settings: Any,
        ) -> AsyncIterator[str]:
            """产出整句文本。

            断句已在管线里完成，LiveKit 拿到的每一段都是可读的整句，TTS 不必再猜
            句末；情绪标签在这里已经被剥掉，只以事件的形式走数据通道。
            """
            message = last_user_message(chat_ctx)
            if not message:
                return
            request = build_request(
                user_id=self._user_id,
                character_id=self._character_id,
                message=message,
                instructions=self._instructions,
            )
            async for output in self._pipeline.run(request):
                if output.text:
                    yield output.text

        async def cancel_turn(self) -> None:
            """用户打断。由框架或上层调用；幂等。"""
            await self._pipeline.cancel()

    return CompanionAgent
