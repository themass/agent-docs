"""聊天栈的组合：把存储、控制面、运行器、提交、排空接在一起（A §5.1–5.2）。

只在组合根里调用。produce 由调用方传入（把 DeerFlow 的事件流接进来），这里不认识 LangGraph。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from companion.app.chat.lifecycle import DrainState
from companion.api.http.routers.chat import ChatApi
from companion.app.chat.drain import DrainService
from companion.app.chat.submit import SubmitService
from companion.app.chat.turn_runner import Produce, TurnInput, TurnRunner
from companion.ports.store import MessageStore, QueueStore, SessionStore
from companion.ports.turn_control import TurnControlPort

log = logging.getLogger("companion.chat")


def build_chat_api(
    *,
    sessions: SessionStore,
    messages: MessageStore,
    queue: QueueStore,
    control: TurnControlPort,
    produce: Produce,
    drain: DrainState,
    process_name: str | None = None,
) -> tuple[ChatApi, Callable[[], None]]:
    """返回 (ChatApi, 关闭回调)。关闭回调目前只占位，停机收尾由 DrainState 等待。"""
    tasks: set[asyncio.Task] = set()
    runner_ref: dict[str, TurnRunner] = {}
    drainer_ref: dict[str, DrainService] = {}

    async def start_turn(*, owner_id: int, session_id: int, character_id: str, turn_id: str,
                         owner: str, text: str, message_ids: list[int]) -> None:
        turn = TurnInput(owner_id=owner_id, session_id=session_id, character_id=character_id,
                         turn_id=turn_id, owner=owner, text=text, message_ids=message_ids)
        task = asyncio.create_task(runner_ref["runner"].run(turn))
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    async def drain_after(*, owner_id: int, session_id: int, character_id: str) -> None:
        await drainer_ref["drainer"].drain(owner_id=owner_id, session_id=session_id, character_id=character_id)

    submit = SubmitService(messages=messages, queue=queue, control=control, start_turn=start_turn,
                           process_name=process_name)
    runner_ref["runner"] = TurnRunner(control=control, messages=messages, queue=queue, produce=produce,
                                      drain=drain_after, tracker=drain)
    drainer_ref["drainer"] = DrainService(queue=queue, submit=submit)

    api = ChatApi(sessions=sessions, messages=messages, queue=queue, control=control,
                  submit=submit, drain=drain, drainer=drainer_ref["drainer"])

    def close() -> None:
        for task in list(tasks):
            task.cancel()

    return api, close
