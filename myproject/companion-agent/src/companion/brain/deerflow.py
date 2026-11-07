"""DeerFlow 主脑：把真实 harness 的事件流接成 [`BrainPort`]。

三个必须处理的差异，决定了这个适配层的形状：

1. **DeerFlow 是同步的**。`DeerFlowClient.stream()` 是普通生成器（内部是 LangGraph
   的同步循环），直接 await 会卡住事件循环。所以回合跑在线程里，事件经队列回到
   异步侧。
2. **它发的是增量**。`messages-tuple` 事件的 `content` 是**增量**而非累计，同一个
   消息 id 会来很多次。这里只负责往下传增量；拼接是上层的事。
3. **没有 cancel API**。取消只能靠丢弃后续事件 + 让生成器被 GC。所以取消是
   「停止消费」，不是「通知服务端停止」——这一点必须在文档里说清，否则会误以为
   后台真的停了。

`deerflow` 是可选依赖：没装时构造抛 [`BrainUnavailable`]，HTTP 接口与测试照常工作。
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncIterator
from typing import Any

from companion.brain.port import BrainTurn, TurnRequest

logger = logging.getLogger(__name__)

# DeerFlow 用这个事件类型推 AI 文本增量。
_AI_TEXT_EVENT = "messages-tuple"


class BrainUnavailable(RuntimeError):
    """DeerFlow 未安装或不可用。"""


class DeerFlowBrain:
    """包装一个 DeerFlowClient。

    与 job-come 的 session client 不同，这里直接用官方 `DeerFlowClient`：它的
    `stream()` 就是我们要的入口，再包一层 session 抽象只会把「线程 + 队列」这
    件事藏得更深。
    """

    def __init__(self, client: Any) -> None:
        if client is None:
            raise BrainUnavailable("DeerFlow client is required")
        self._client = client

    async def start_turn(self, request: TurnRequest) -> BrainTurn:
        thread_id = request.thread_id or _thread_id_for(request)
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        # threading.Event 而不是 asyncio.Event：它要在线程里被设置。
        cancelled = threading.Event()

        def pump() -> None:
            """在工作线程里跑同步生成器，把增量丢回事件循环。"""
            try:
                for event in self._client.stream(request.message, thread_id=thread_id):
                    if cancelled.is_set():
                        return
                    text = _ai_text_delta(event)
                    if text:
                        loop.call_soon_threadsafe(queue.put_nowait, text)
            except Exception as exc:  # noqa: BLE001 —— 主脑失败由上层处理
                # 不能在错误里丢掉已经产出的内容：上层会照常交付已收到的句子，
                # 这里只把异常记下来作为结束信号。
                logger.warning("deerflow stream failed: %s", exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        worker = threading.Thread(target=pump, name=f"deerflow-{thread_id}", daemon=True)
        worker.start()

        async def tokens() -> AsyncIterator[str]:
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        return
                    # 线程可能在我们取消之前就把事件排进队列了。这里再查一次，
                    # 否则「取消之后仍然吐出一句」——语音场景里就是打断之后又开口。
                    if cancelled.is_set():
                        return
                    yield item
            finally:
                # 消费者提前退出（被打断 / 客户端断开）时，也要让线程停下。
                cancelled.set()

        async def cancel() -> None:
            cancelled.set()
            # 没有服务端 cancel API：这里只是停止消费，后台生成会跑到当前步骤结束。
            logger.info("deerflow turn %s cancelled (consumer side)", thread_id)

        return BrainTurn(tokens=tokens(), cancel=cancel, turn_id=thread_id)

    async def aclose(self) -> None:
        reset = getattr(self._client, "reset_agent", None)
        if callable(reset):
            try:
                reset()
            except Exception as exc:  # noqa: BLE001
                logger.debug("reset_agent failed: %s", exc)


def _ai_text_delta(event: Any) -> str:
    """从 StreamEvent 里取出 AI 文本增量。

    只认 `messages-tuple` + `type == "ai"` 且有非空 `content`。工具调用与工具结果
    也在同一个事件类型里，但它们的 content 是空串或工具输出，不该进对话文本。
    """
    if getattr(event, "type", None) != _AI_TEXT_EVENT:
        return ""
    data = getattr(event, "data", None)
    if not isinstance(data, dict):
        return ""
    if data.get("type") != "ai":
        return ""
    content = data.get("content")
    if not isinstance(content, str):
        return ""
    return content


def _thread_id_for(request: TurnRequest) -> str:
    """线程 = 一个用户与一个角色的长期会话。

    用稳定 id 而不是随机 id：DeerFlow 用 thread_id 做 checkpoint 的键，随机 id 会
    让每次进房都从零开始，用户的对话历史就断了。
    """
    return f"{request.user_id}:{request.character_id}"


def build_default_client(**kwargs: Any) -> Any:
    """按项目约定构造一个 DeerFlowClient。

    `deerflow` 与 `langgraph` 都是可选依赖：只有真正要用主脑时才需要它们。
    `checkpointer` 必须由调用方提供——没有它每次调用都是无状态的，多轮对话会断。
    """
    try:
        from deerflow.client import DeerFlowClient
    except ImportError as exc:
        raise BrainUnavailable(
            "deerflow 未安装：pip install deerflow-harness（含 deerflow 包）"
        ) from exc

    return DeerFlowClient(**kwargs)
