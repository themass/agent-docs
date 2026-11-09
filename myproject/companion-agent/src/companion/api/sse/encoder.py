"""SSE 帧编码（D §7.2–7.3）。纯函数，不依赖 fastapi。

data 用 json.dumps 编码，转义了换行，所以一帧永远不会被拆开。
"""

from __future__ import annotations

import json
from typing import Any

KEEPALIVE_FRAME = ": keepalive\n\n"


def encode_event(event_id: str, event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event_id}\nevent: {event}\ndata: {payload}\n\n"
