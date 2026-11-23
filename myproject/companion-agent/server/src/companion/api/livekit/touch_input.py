"""端侧触摸（``control.input`` kind=touch）→ 用户句。

协议只声明 ``{kind, region}``，不规定服务端怎么反应。端侧已经先给了本地反馈
（缩放 + Toast），服务端这边最轻的兑现是：把触摸翻成一句自然语言，塞进当前
``AgentSession``，走和语音/文字一样的回合管线——她回不回、回什么由角色自己定，
不另开表情/手势通道。

冷却是为了挡住连点：``generate_reply`` 会起一整轮 LLM + TTS，没有节流就会
把消息量和费用线性放大。"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

#: 与端侧 ``AvatarRegion`` / ``LayeredAvatar`` 的 region 名对齐。
#: 未知 region 仍会回一句通用话——丢掉不如让她知道被碰了。
TOUCH_LINES: dict[str, str] = {
    "head": "摸了摸她的头",
    "body": "碰了她一下",
    "chest": "碰了碰她的胸口",
    "hand_l": "碰了碰她的左手",
    "hand_r": "碰了碰她的右手",
}

DEFAULT_COOLDOWN_S = 1.5
# 进房头几秒不跟 STT 抢首轮 user turn（npFD：摸头 generate_reply + Hello 叠麦）。
DEFAULT_TOUCH_WARMUP_S = 3.0

_BUSY_AGENT_STATES = frozenset({"thinking", "speaking"})
_BUSY_USER_STATES = frozenset({"speaking"})


def voice_session_accepts_touch_turn(session: Any) -> bool:
    """触摸不要再起一轮 ``generate_reply`` 的时机：agent/用户在说，或上句还没完。"""
    agent = getattr(session, "agent_state", None)
    if agent in _BUSY_AGENT_STATES:
        return False
    user = getattr(session, "user_state", None)
    if user in _BUSY_USER_STATES:
        return False
    speech = getattr(session, "current_speech", None)
    if speech is not None and not getattr(speech, "done", False):
        return False
    return True


def touch_user_message(args: dict[str, Any] | None) -> str | None:
    """把 ``control.input`` 的 args 翻成用户句；不是触摸或字段坏了返回 ``None``。"""
    if not isinstance(args, dict):
        return None
    if args.get("kind") != "touch":
        return None
    region = args.get("region")
    if not isinstance(region, str):
        return None
    region = region.strip()
    if not region:
        return None
    return TOUCH_LINES.get(region) or "碰了她一下"


class TouchInputRelay:
    """``ProtocolBridge.on_input`` 的消费者：校验 → 冷却 → ``generate_reply``。

    ``session`` 只需要有同步的 ``generate_reply(*, user_input=...)``——LiveKit
    ``AgentSession`` 就是这种形状；单测喂一个假对象即可，不必拉起语音栈。
    """

    def __init__(
        self,
        session: Any,
        *,
        cooldown_s: float = DEFAULT_COOLDOWN_S,
        warmup_s: float = 0.0,
    ) -> None:
        self._session = session
        self._cooldown_s = max(0.0, float(cooldown_s))
        warmup = max(0.0, float(warmup_s))
        start = time.monotonic()
        self._ready_mono = start + warmup
        self._last_mono = 0.0
        self.accepted = 0
        self.ignored = 0

    def __call__(self, args: dict[str, Any]) -> None:
        text = touch_user_message(args)
        if text is None:
            self.ignored += 1
            return
        now = time.monotonic()
        if now < self._ready_mono:
            self.ignored += 1
            return
        if not voice_session_accepts_touch_turn(self._session):
            self.ignored += 1
            return
        if self._cooldown_s > 0.0 and (now - self._last_mono) < self._cooldown_s:
            self.ignored += 1
            return
        self._last_mono = now
        try:
            self._session.generate_reply(user_input=text)
        except Exception as exc:  # noqa: BLE001 —— §14.1：输入处理失败不拖停消息链
            self.ignored += 1
            logger.warning("touch generate_reply failed: %s", exc)
            return
        self.accepted += 1
