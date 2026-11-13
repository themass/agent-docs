"""回合 id：ULID（26 位 Crockford Base32）。表结构 chat_message.turn_id 定长 26（D §3.3）。"""

from __future__ import annotations

import secrets
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_ulid() -> str:
    millis = int(time.time() * 1000)
    head = "".join(_ALPHABET[(millis >> shift) & 31] for shift in range(45, -1, -5))
    tail = "".join(secrets.choice(_ALPHABET) for _ in range(16))
    return head + tail
