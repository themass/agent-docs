"""回合接口：客户端用一个 HTTP 请求跑完一次对话（流式返回）。

LiveKit 房间是主链路；这个接口是它的降级与调试通道：
- 文字模式下，若房间建立失败（网络差、LiveKit 不可用），客户端仍能对话；
- 离线联调与压测不必起房间。

业务逻辑不在这里重复：提示词组装与记忆召回都走 ConversationService，
这个模块只负责「请求 → SSE 文本行」。

不用 ``from __future__ import annotations``：FastAPI 要在运行时读取函数的注解来
判定请求模型，PEP 563 会把注解变成字符串，函数内定义的模型就解析不出来，请求体
会被当成查询参数（表现为 422 missing body）。``sessions.py`` 同样没有这一行。
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

from companion.ports.brain import TurnRequest
from companion.app.chat.conversation import ConversationService, TurnContext
from companion.domain.turn.pipeline import TurnPipeline


@dataclass
class TurnRequestPayload:
    user_id: str
    character_id: str
    message: str
    thread_id: str | None = None
    mode: str = "text"


class TurnService:
    """把一次 HTTP 回合跑成文本流。

    输出是纯文本块，由 router 层包成 SSE 帧——这样这个类不依赖 fastapi，
    测试里可以直接读完整个流。
    """

    def __init__(self, *, conversation: ConversationService, pipeline: TurnPipeline) -> None:
        self._conversation = conversation
        self._pipeline = pipeline

    async def stream(self, payload: TurnRequestPayload) -> AsyncIterator[str]:
        ctx = TurnContext(
            user_id=payload.user_id,
            character_id=payload.character_id,
            message=payload.message,
            thread_id=payload.thread_id,
            mode=payload.mode,
        )
        # 提示词与记忆在 ConversationService 里组装，这里拿到的已经是可直接交给
        # 主脑的请求；断句与事件剥离在 pipeline 里。
        request = await self._conversation.prepare(ctx)
        try:
            async for output in self._pipeline.run(request):
                if output.text:
                    yield output.text
        except asyncio.CancelledError:
            # 客户端断开：取消主脑回合，避免后台继续生成、继续计费。
            await self._conversation.cancel_current()
            raise


def build_router(service: TurnService, current_user):
    """挂到 app 上。fastapi 在这里才导入，纯逻辑测试不需要它。

    用 SSE 而不是 WebSocket：文字模式只需要单向流；双向实时已经由 LiveKit
    房间负责，两条通道各管一件事。
    """
    from fastapi import APIRouter, Depends
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field

    class TurnBody(BaseModel):
        character_id: str = Field(min_length=1)
        message: str = Field(min_length=1)
        thread_id: str | None = None
        mode: str = "text"

    router = APIRouter(prefix="/companion", tags=["companion"])

    @router.post("/turns")
    async def create_turn(
        body: TurnBody,
        user_id: str = Depends(current_user),
    ) -> StreamingResponse:
        async def frames():
            payload = TurnRequestPayload(
                user_id=user_id,
                character_id=body.character_id,
                message=body.message,
                thread_id=body.thread_id,
                mode=body.mode,
            )
            async for chunk in service.stream(payload):
                # SSE 的 data 行不能含裸换行，否则一帧会被拆成两帧。
                for line in chunk.splitlines() or [""]:
                    yield f"data: {line}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(frames(), media_type="text/event-stream")

    return router
