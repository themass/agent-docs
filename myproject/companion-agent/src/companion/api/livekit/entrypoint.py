"""房间入口：一个房间一个 agent。

装配顺序有讲究，写错会造成很难查的问题：

1. 先解析房间元数据，拿到 user_id 与 character_id —— 没有身份就没有记忆与角色，
   先建 session 再拿身份会导致第一次回复用错人设。
2. 再建 ConversationService / 管线（按角色组装提示词一次，不要每句重拼）。
3. 最后 `session.start(agent, room=ctx.room)`，把音频与文本通道都交给 LiveKit。

文本与语音共用同一个 session：文字走 `lk.chat` 文本流，语音走音轨，两者进的是
同一个对话上下文，所以切模式不会丢上下文、也不会变成两个人。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from companion.api.livekit.bridge import require

logger = logging.getLogger(__name__)

TEXT_TOPIC = "lk.chat"
# 我们自己加的通道：形象事件、主动消息、待确认动作。不用 lk.chat，避免和用户
# 输入混在一起——客户端要能区分「她说的话」和「她让你确认一件事」。
TOPIC_AVATAR = "companion.avatar"
TOPIC_PROACTIVE = "companion.proactive"
TOPIC_ACTION = "companion.action"
TOPIC_CONFIRM = "companion.confirm"


@dataclass
class RoomIdentity:
    user_id: str
    character_id: str
    # 新服务的会话 id：有它时语音回合走新服务的会话（共享对话线程、记忆与画像），没有就走旧的进程内管线。
    chat_session_id: int | None = None

    @classmethod
    def from_room_metadata(cls, metadata: str | None) -> "RoomIdentity":
        """从房间元数据解析身份。

        元数据由服务端建房间时写入，客户端改不了；解析失败就拒绝入场，而不是
        退回到一个默认身份——用一个错误的身份聊一轮，记忆就写错了。
        """
        if not metadata:
            raise ValueError("room metadata missing")
        try:
            payload = json.loads(metadata)
        except json.JSONDecodeError as exc:
            raise ValueError("room metadata is not json") from exc
        user_id = str(payload.get("user_id") or "").strip()
        character_id = str(payload.get("character_id") or "").strip()
        if not user_id or not character_id:
            raise ValueError("room metadata missing user_id or character_id")
        raw_session = payload.get("chat_session_id")
        chat_session_id: int | None = None
        if raw_session is not None:
            try:
                chat_session_id = int(raw_session)
            except (TypeError, ValueError) as exc:
                # 写坏了就拒绝入场：用错会话聊一轮，会写进别人的对话线程。
                raise ValueError("room metadata has an invalid chat_session_id") from exc
            if chat_session_id <= 0:
                raise ValueError("room metadata has an invalid chat_session_id")
        return cls(user_id=user_id, character_id=character_id, chat_session_id=chat_session_id)


class AvatarPublisher:
    """把管线产出的形象事件发到数据通道。

    发不出去只记日志：形象是表现层，不能因为它断掉正在进行的回复。
    """

    def __init__(self, room: Any) -> None:
        self._room = room
        self._local: Any = None

    def set_local_participant(self, participant: Any) -> None:
        self._local = participant

    def __call__(self, event_json: str) -> None:
        try:
            import asyncio

            asyncio.get_running_loop().create_task(self._publish(event_json))
        except RuntimeError:
            # 没有运行中的事件循环（例如在同步测试里）——不做任何事。
            logger.debug("no loop for avatar event")

    async def _publish(self, payload: str) -> None:
        if self._local is None:
            return
        try:
            from livekit import rtc

            data = payload.encode("utf-8")
            await self._local.publish_data(data, topic=TOPIC_AVATAR)
        except Exception as exc:  # noqa: BLE001
            logger.debug("avatar publish failed: %s", exc)


async def publish_proactive(room: Any, text: str, kind: str) -> None:
    """向房间推一条主动消息。客户端据此把它渲染成「她主动说的」。"""
    await _publish_json(
        room, TOPIC_PROACTIVE, {"text": text, "kind": kind}
    )


async def publish_action(room: Any, confirmation_id: str, prompt: str) -> None:
    """推一个待确认动作。客户端会渲染成一对按钮。"""
    await _publish_json(
        room,
        TOPIC_ACTION,
        {"confirmation_id": confirmation_id, "prompt": prompt},
    )


async def _publish_json(room: Any, topic: str, payload: dict) -> None:
    try:
        local = room.local_participant
        await local.publish_data(
            json.dumps(payload, ensure_ascii=False).encode("utf-8"), topic=topic
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("publish to %s failed: %s", topic, exc)


def build_session_options(*, mode: str = "text", voice_factory: Any = None) -> dict:
    """AgentSession 的构造参数。

    文字模式不挂 STT/TTS，语音模式才需要；两者都挂会让文字模式也去合成语音，
    白白烧钱。语音栈由调用方（组合根）注入，接口层不认识具体供应商。
    """
    options: dict[str, Any] = {}
    if mode == "voice" and voice_factory is not None:
        tts, stt = voice_factory()
        options["tts"] = tts
        options["stt"] = stt
    return options


def make_entrypoint(container: Any, voice_factory: Any = None):
    """装配好的 worker 入口。容器与语音栈由组合根传入，本模块不自己装配。"""

    async def entrypoint(ctx: Any) -> None:
        """worker 的入口。由 LiveKit 的 job context 调用。"""
        require()

        from livekit.agents import AgentSession

        from companion.api.livekit.agent import build_agent_class
        from companion.domain.turn.pipeline import TurnPipeline

        """worker 的入口。由 LiveKit 的 job context 调用。"""

        try:
            identity = RoomIdentity.from_room_metadata(getattr(ctx.room, "metadata", None))
        except ValueError as exc:
            logger.error("refusing room: %s", exc)
            await ctx.room.disconnect()
            return

        publisher = AvatarPublisher(ctx.room)
        publisher.set_local_participant(ctx.room.local_participant)

        pipeline = TurnPipeline(container.brain, event_sink=publisher)
        agent_class = build_agent_class()

        instructions = container.prompts.build(identity.character_id)
        agent = agent_class(
            pipeline=pipeline,
            character_id=identity.character_id,
            user_id=identity.user_id,
            instructions=instructions,
        )

        session = AgentSession(**build_session_options(voice_factory=voice_factory))
        await session.start(agent, room=ctx.room)
        logger.info(
            "companion joined room user=%s character=%s",
            identity.user_id,
            identity.character_id,
        )

    return entrypoint
