"""OpenAI-compatible chat client used for ONE job: rewording a scripted answer.

What goes in: the persona text, the scripted line, and the facts that role may read. What never goes in:
anything the learner typed, a learner profile, or history. What comes out must be JSON ``{say, uses}`` and
still has to pass the reviewer. Any failure is a typed error the service turns into the scripted answer.

Logging: model tier, latency, token counts. Never the address, the key, the prompt or the reply.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings
from .lesson import Fact
from .reviewer import SAY_LIMIT

log = logging.getLogger("student_agent.llm")


class LLMError(Exception):
    reason = "unavailable"


class LLMRejected(LLMError):
    """The gateway answered, but not with something usable (not JSON, empty, wrong shape). Not a gateway outage."""
    reason = "rejected"


class LLMTimeout(LLMError):
    reason = "timeout"


class LLMUnavailable(LLMError):
    reason = "unavailable"


@dataclass(frozen=True)
class Reworded:
    say: str
    uses: list[str]
    tier: str
    ms: int
    prompt_tokens: int
    completion_tokens: int


RULES = (
    "只改写措辞，不增加、不改变任何事实；不得出现脚本和事实清单里没有的人名、地名、年份和数字。"
    "只输出一个 JSON 对象：{\"say\": \"改写后的话\", \"uses\": [\"用到的事实 id\"]}。"
    "say 不超过 {limit} 个字。面向想弄懂这首诗的读者，不分年级：平实、简短，用到的词如果生僻就顺手说明白。"
)


def extract_json(text: str) -> dict[str, Any]:
    """Pull the JSON object out of a model reply, or raise LLMRejected.

    A reply whose first JSON value is an array ("["not", "an", "object"]") has no braces at all, so the
    old brace-slicing path reported "no json object" and a nested array inside an object was never
    type-checked. Try a full json.loads first when the text looks like a bare JSON value; fall back to
    brace slicing for replies that wrap the object in prose or a fenced block.
    """
    stripped = text.strip()
    if stripped[:1] in ("[", "{"):
        try:
            obj = json.loads(stripped)
        except ValueError:
            obj = None
        if obj is not None:
            if not isinstance(obj, dict):
                raise LLMRejected("not an object")
            return obj
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise LLMRejected("no json object")
    try:
        obj = json.loads(text[start:end + 1])
    except ValueError as exc:
        raise LLMRejected("invalid json") from exc
    if not isinstance(obj, dict):
        raise LLMRejected("not an object")
    return obj


class LLMClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.s = settings
        self._transport = transport

    def rephrase(self, *, role: str, soul: str, script_say: str, facts: list[Fact],
                 tier: str = "primary") -> Reworded:
        if not self.s.llm_configured:
            raise LLMUnavailable("not configured")
        model = self.s.model_primary if tier == "primary" else (self.s.model_fallback or self.s.model_primary)
        timeout = self.s.timeout_primary if tier == "primary" else self.s.timeout_fallback
        system = soul.strip() + "\n\n" + RULES.replace("{limit}", str(SAY_LIMIT))
        user = json.dumps({
            "script_say": script_say,
            "facts": [{"id": f.id, "text": f.text} for f in facts],
        }, ensure_ascii=False)
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.3, "max_tokens": 300, "response_format": {"type": "json_object"},
        }
        started = time.monotonic()
        try:
            with httpx.Client(timeout=timeout, transport=self._transport) as client:
                res = client.post(f"{self.s.llm_base}/chat/completions", json=body,
                                  headers={"Authorization": f"Bearer {self.s.llm_key}"})
                if res.status_code == 400 and "response_format" in body:
                    body.pop("response_format")  # a gateway without JSON mode: the prompt still demands JSON
                    res = client.post(f"{self.s.llm_base}/chat/completions", json=body,
                                      headers={"Authorization": f"Bearer {self.s.llm_key}"})
        except httpx.TimeoutException as exc:
            raise LLMTimeout("timeout") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailable("transport") from exc
        if res.status_code >= 400:
            raise LLMUnavailable(f"status {res.status_code}")
        # Any shape the gateway can return (null content, string usage, a list instead of an object) ends as
        # "rejected", so the caller falls back to the script. Nothing here may raise past this point.
        try:
            data = res.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise LLMRejected("content is not text")
            usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
            obj = extract_json(content)
            say = obj.get("say")
            if not isinstance(say, str) or not say.strip():
                raise LLMRejected("no say")
            say = say.strip()
            raw_uses = obj.get("uses", [])
            # A reply that names its grounding in something other than a list of ids cannot be checked,
            # so it is a rejected reply, not an empty one: silently dropping it would let an unverifiable
            # claim through the reviewer with no uses at all.
            if not isinstance(raw_uses, list):
                raise LLMRejected("uses is not a list")
            uses = [u for u in raw_uses if isinstance(u, str)]
            prompt_tokens = usage.get("prompt_tokens") if isinstance(usage.get("prompt_tokens"), int) else 0
            completion_tokens = usage.get("completion_tokens") if isinstance(usage.get("completion_tokens"), int) else 0
        except LLMError:
            raise
        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as exc:
            raise LLMRejected("unusable reply") from exc
        ms = int((time.monotonic() - started) * 1000)
        return Reworded(say, uses, tier, ms, prompt_tokens, completion_tokens)
