"""会话事件流（D §7.3）。

- 首连（无 Last-Event-ID）：有运行中的回合则先发 turn.snapshot，再实时订阅。
- 续传（带 Last-Event-ID）：从该 id 之后接着读；早于保留窗口则发 gone，客户端改拉历史。
- 心跳：一段时间内没有事件就发注释帧 keepalive。
- 停机：draining 时发 reconnect 并结束流，客户端带 Last-Event-ID 去别的进程续传。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from companion.api.sse.encoder import KEEPALIVE_FRAME, encode_event
from companion.service.turn.control import TurnControlPort

RECONNECT_AFTER_MS = 1000


def _id_key(stream_id: str) -> tuple[int, int]:
    ms, _, seq = stream_id.partition("-")
    return int(ms), int(seq or 0)


async def event_stream(
    *,
    control: TurnControlPort,
    session_id: int,
    last_event_id: str | None,
    draining: Callable[[], bool],
    keepalive_sec: float = 15.0,
) -> AsyncIterator[str]:
    if last_event_id is None:
        cursor = await control.tail_event_id(session_id=session_id)
        turn = await control.active_turn(session_id=session_id)
        if turn is not None:
            text = await control.read_text(turn_id=turn["turn_id"])
            ids = [int(x) for x in turn.get("message_ids", "").split(",") if x]
            yield encode_event(cursor, "turn.snapshot",
                               {"turn_id": turn["turn_id"], "user_message_ids": ids, "text": text, "steps": []})
    else:
        oldest = await control.oldest_event_id(session_id=session_id)
        if oldest != "0-0" and _id_key(last_event_id) < _id_key(oldest):
            yield encode_event(last_event_id, "gone", {})
            return
        cursor = last_event_id

    block_ms = int(keepalive_sec * 1000)
    while True:
        if draining():
            yield encode_event(cursor, "reconnect", {"after_ms": RECONNECT_AFTER_MS})
            return
        events = await control.wait_events(session_id=session_id, after_id=cursor, block_ms=block_ms)
        if not events:
            yield KEEPALIVE_FRAME
            continue
        for entry_id, name, data in events:
            yield encode_event(entry_id, name, data)
            cursor = entry_id
