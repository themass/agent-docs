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
        tts, stt, *rest = voice_factory()
        options["tts"] = tts
        options["stt"] = stt
        if rest:
            # 官方 silero VAD：语音端点检测交给框架的模型，不自己写
            options["vad"] = rest[0]
    return options


@dataclass
class VoiceParts:
    """一个房间需要的、由组合根按平台装配好的零件。接口层只认这几个形状，不认具体实现。"""

    brain: Any                 # BrainPort：把语音识别出的话交给回合引擎
    recorder: Any = None       # async (VoiceTurnRecord) -> None
    tts_sink: Any = None       # async (**turn 信息, segment=TtsSegment) -> None


class RoomEntrypoint:
    """worker 入口。

    ``platform_factory`` 是协程函数，返回和 HTTP 服务同一套 platform（同库、同 Redis、同回合引擎）。
    语音回合因此与文字共用会话、历史、对话线程和回合后处理，而不是另一条直连大脑的管线。
    它必须在事件循环里调用（checkpoint 连接池要用运行中的循环），所以放在入口里而不是启动时。

    ``wire_voice(platform) -> VoiceParts`` 由组合根提供：大脑、质检记录、TTS 采集的具体实现都在那里构造，
    本模块（接口层）不依赖适配器。

    **为什么是类而不是闭包**：LiveKit 在 Linux 上用 ``forkserver`` 给每个房间起子进程，
    ``entrypoint_fnc`` 要能被 pickle 序列化后传给子进程（默认 ``PROCESS`` 执行器）。
    闭包序列化不了，子进程起不来，上报的是
    ``AttributeError: Can't get local object 'make_entrypoint.<locals>.entrypoint'``——
    每来一个房间就失败一次，而 worker 本身看着是健康的。
    类的实例可以由 pickle 按"模块 + 类名 + __dict__"重建，所以这里顶层的三个依赖也要能 pickle：
    模块级的函数（``build_voice_stack``、``voice_wiring`` 返回的闭包不行，见 ``worker.py`` 的说明）。
    """

    def __init__(self, platform_factory: Any, voice_factory: Any = None, wire_voice: Any = None) -> None:
        self._platform_factory = platform_factory
        self._voice_factory = voice_factory
        self._wire_voice = wire_voice

    async def __call__(self, ctx: Any) -> None:
        """worker 的入口。由 LiveKit 的 job context 调用。"""
        require()

        from livekit.agents import AgentSession

        from companion.api.livekit.agent import build_agent_class
        from companion.domain.turn.pipeline import TurnPipeline

        try:
            identity = RoomIdentity.from_room_metadata(getattr(ctx.room, "metadata", None))
        except ValueError as exc:
            logger.error("refusing room: %s", exc)
            await ctx.room.disconnect()
            return

        if identity.chat_session_id is None:
            # 没有会话就没有可共享的历史。不退回独立的语音会话：那正是“文字一份、语音一份”的成因。
            logger.error("refusing room without chat_session_id user=%s", identity.user_id)
            await ctx.room.disconnect()
            return

        platform = await self._platform_factory()
        await platform.astart()
        ctx.add_shutdown_callback(platform.aclose)

        publisher = AvatarPublisher(ctx.room)
        publisher.set_local_participant(ctx.room.local_participant)

        parts: VoiceParts = self._wire_voice(platform)
        pipeline = TurnPipeline(parts.brain, event_sink=publisher)
        agent_class = build_agent_class()

        # 提示词由回合引擎按会话组装（角色卡、技能、记忆、画像），这里不再自己拼一份。
        agent = agent_class(
            pipeline=pipeline,
            character_id=identity.character_id,
            user_id=identity.user_id,
            chat_session_id=identity.chat_session_id,
            recorder=parts.recorder,
            tts_sink=parts.tts_sink,
        )

        # 语音栈必须显式按 voice 模式装配：不传 mode 时默认是 text，STT/TTS/VAD 都不会挂上，
        # 表现是「agent 进房间了但一句话不说」。
        session = AgentSession(**build_session_options(mode="voice", voice_factory=self._voice_factory))
        await session.start(agent, room=ctx.room)
        logger.info(
            "companion joined room user=%s character=%s",
            identity.user_id,
            identity.character_id,
        )


def make_entrypoint(platform_factory: Any, voice_factory: Any = None, wire_voice: Any = None) -> RoomEntrypoint:
    """装配好的 worker 入口。返回的是可 pickle 的对象（见 ``RoomEntrypoint`` 的说明）。"""
    return RoomEntrypoint(platform_factory, voice_factory, wire_voice)
