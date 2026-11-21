"""In-process budget, rate limit and answer cache. Not distributed; a Redis-backed ledger can replace it
behind the same three methods. Nothing here stores text a learner wrote: buckets are keyed by a short hash
of the bearer token (or one shared anonymous bucket), and the cache is keyed by fact ids only.
"""
from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field

TTL_SECONDS = 2 * 3600


def bucket_for(authorization: str | None) -> str:
    if not authorization:
        return "anon"
    return hashlib.sha256(authorization.encode("utf-8")).hexdigest()[:16]


@dataclass
class _Bucket:
    calls: int = 0
    tokens: int = 0
    stamps: list[float] = field(default_factory=list)
    touched: float = 0.0


class Ledger:
    def __init__(self, calls_per_lesson: int, tokens_per_lesson: int, turns_per_minute: int,
                 clock=time.monotonic) -> None:
        self.max_calls, self.max_tokens, self.max_turns = calls_per_lesson, tokens_per_lesson, turns_per_minute
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}

    def _bucket(self, key: str) -> _Bucket:
        now = self._clock()
        if len(self._buckets) > 2000:
            self._buckets = {k: b for k, b in self._buckets.items() if now - b.touched < TTL_SECONDS}
        b = self._buckets.setdefault(key, _Bucket())
        if now - b.touched > TTL_SECONDS:
            b.calls = b.tokens = 0
        b.touched = now
        return b

    def allow_turn(self, key: str) -> bool:
        b = self._bucket(key)
        now = self._clock()
        b.stamps = [s for s in b.stamps if now - s < 60]
        if len(b.stamps) >= self.max_turns:
            return False
        b.stamps.append(now)
        return True

    def can_call_llm(self, key: str) -> bool:
        b = self._bucket(key)
        return b.calls < self.max_calls and b.tokens < self.max_tokens

    def record_call(self, key: str, tokens: int) -> None:
        b = self._bucket(key)
        b.calls += 1
        b.tokens += max(0, tokens)


class AnswerCache:
    def __init__(self, size: int = 256) -> None:
        self.size = size
        self._data: OrderedDict[tuple, object] = OrderedDict()

    def get(self, key: tuple):
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        return None

    def put(self, key: tuple, value: object) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self.size:
            self._data.popitem(last=False)
