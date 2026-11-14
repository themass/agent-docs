"""会话事件流（D §7.3）。

- 首连（无 Last-Event-ID）：有运行中的回合则先发 turn.snapshot，再实时订阅。
- 续传（带 Last-Event-ID）：从该 id 之后接着读；早于保留窗口则发 gone，客户端改拉历史。
- 心跳：一段时间内没有事件就发注释帧 keepalive。
- 停机：draining 时发 reconnect 并结束流，客户端带 Last-Event-ID 去别的进程续传。
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Callable

from companion.api.sse.encoder import KEEPALIVE_FRAME, encode_event
from companion.service.turn.control import TurnControlPort

log = logging.getLogger("companion.sse")

RECONNECT_AFTER_MS = 1000

# 一次阻塞读最多等多久。**不能超过 Redis 服务端掐断空闲连接的阈值**：线上那个托管
# Redis 大约 5 秒就断开没有数据流动的连接，客户端设 block=15 秒的 XREAD 每次都以
# TimeoutError 结束，异常一路穿透到这里，整个事件流跟着断——表现就是 App 的回复
# 收到一半就没了。4 秒留了一秒余量（实测 4.5 秒仍稳定，5 秒必断）。
BLOCK_MS = 4000


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

    last_keepalive = time.monotonic()
    while True:
        if draining():
            yield encode_event(cursor, "reconnect", {"after_ms": RECONNECT_AFTER_MS})
            return
        try:
            events = await control.wait_events(session_id=session_id, after_id=cursor, block_ms=BLOCK_MS)
        except Exception as exc:  # noqa: BLE001
            # 读超时不算故障：托管 Redis 会掐断空闲连接，客户端看到的就是读超时。
            # 当成"这段时间没有事件"继续等，否则一次网络抖动就把整个流打断，
            # 用户那边表现为回复说到一半没了，而且不会自己恢复。
            # 其它异常（连接被拒、认证失败）也不在这里终止：断开会让客户端重连，
            # 重连比在这里抛栈更接近用户想要的结果。
            log.warning("event wait failed, keep streaming: %s", type(exc).__name__)
            events = []
        if not events:
            # 心跳按 keepalive_sec 发，不是每次空读都发：阻塞读现在 4 秒一次，
            # 每次都发心跳会在客户端积一堆无用的注释帧。
            if time.monotonic() - last_keepalive >= keepalive_sec:
                last_keepalive = time.monotonic()
                yield KEEPALIVE_FRAME
            continue
        last_keepalive = time.monotonic()
        for entry_id, name, data in events:
            yield encode_event(entry_id, name, data)
            cursor = entry_id
