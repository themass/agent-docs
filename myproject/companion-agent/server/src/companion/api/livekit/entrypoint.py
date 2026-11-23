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

import asyncio
import inspect
import json
import logging
from dataclasses import dataclass
from typing import Any

from companion.api.livekit.bridge import require
from companion.api.livekit.protocol_bridge import ProtocolBridge, attach, local_sender
from companion.api.livekit.barge_in import BargeInRelay
from companion.api.livekit.inbound_audio_probe import attach_inbound_audio_probe
from companion.api.livekit.input_attachments import CompositeInputRelay, PendingAttachmentSlot
from companion.api.livekit.outbound_audio_probe import attach_outbound_audio_probe
from companion.api.livekit.touch_input import DEFAULT_COOLDOWN_S
from companion.api.livekit.speech_publisher import SpeechPublisher
from companion.api.livekit.anchored_cues import AnchoredCuePublisher

logger = logging.getLogger(__name__)

# 文本流 topic 的本尊在 ``api.livekit.topics``，这里**不再导出**它。
# 曾经有一行 ``from ...topics import TEXT_TOPIC`` 作为兼容再导出，但全仓零读者
# （生产与剧本房都直接 import ``topics``），留着反而邀请人走错门：剧本房一旦
# ``from ...entrypoint import TEXT_TOPIC``，就把本模块模块级的音频探针
# （``from livekit import rtc`` + ``from livekit.agents.voice.io``）整块拖进它的模块图，
# 「离线」的剧本房测试就得装 ``--extra livekit`` 才跑得动（见 topics.py 的模块 docstring，
# 以及 ``tests/test_script_room_real_turn.py`` 那条挡住 livekit.agents 的子进程探针）。

# 我们自己加的通道：形象事件、主动消息、待确认动作。不用 lk.chat，避免和用户
# 输入混在一起——客户端要能区分「她说的话」和「她让你确认一件事」。
#
# 都是**服务端 → 客户端**单向。确认回执不走这里：它是用户的决定，走 HTTP
# `POST /v1/actions/{id}/confirm`（见 api/http/routers/actions.py），带鉴权、
# 幂等和错误码。这里曾经有一个 `TOPIC_CONFIRM`，但两端都没有实现过——删掉，
# 不留一个指向不存在的消费者的通道名。
TOPIC_AVATAR = "companion.avatar"
TOPIC_PROACTIVE = "companion.proactive"
TOPIC_ACTION = "companion.action"

#: 握手的后台任务。asyncio 只对任务持弱引用，不自己留一份的话可能在等 hello 的
#: 3 秒里被 GC 回收，超时回落永远不会发生。
_HANDSHAKES: set[asyncio.Task[Any]] = set()

# LiveKit 打断默认 min_words=0、min_duration=0.5；叠麦/短 VAD 会在首句 TTS 出声前 interrupt。
VOICE_INTERRUPTION_MIN_WORDS = 2
VOICE_INTERRUPTION_MIN_DURATION = 0.9
# agent 开口前几秒：收紧 VAD/叠麦误打断（75e90fda：Hello 重复 final + VAD）。
VOICE_INTERRUPTION_BACKCHANNEL_BOUNDARY: tuple[float, float] = (2.0, 1.0)
# 190d782a：SDK 默认 preemptive_generation=True，STT 变体每来一条就 cancel+新开 llm_node。
VOICE_PREEMPTIVE_GENERATION_ENABLED = False
# 略拉长 endpointing，减少连续 final 叠成多轮 user turn。
VOICE_ENDPOINTING_MIN_DELAY = 0.75
VOICE_ENDPOINTING_MAX_DELAY = 4.0


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


class ProtocolCueSink:
    """管线 ``event_sink`` → **只**走 v1 ``companion.avatar``。

    P3 起 v2 ``presentation.*`` 改由 :class:`AnchoredCuePublisher` 在
    ``speech.seg(k)`` 之后、TTS 之前发出（带信封 ``at``）。这里再发一条无锚点
    的 ``cue_emotion`` 会和锚点路径赛跑，并破坏 §13 不变量 1——所以 v2 从这里拿掉。

    握手窗口里对面可能还是 v1：老路径必须继续发；v2 客户端会忽略
    ``companion.avatar``。

    **事件解析失败不影响回复**（§14.1）：legacy 抛了只记日志。
    """

    def __init__(self, legacy: Any) -> None:
        self._legacy = legacy

    def __call__(self, event_json: str) -> None:
        try:
            self._legacy(event_json)
        except Exception as exc:  # noqa: BLE001
            logger.debug("legacy avatar sink failed: %s", exc)


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


def _pipeline_llm() -> Any:
    """房间会话必须挂的一个 LLM 占位对象。

    出字的是被重写的 ``llm_node``（回合管线），LiveKit 自己从不调用这个对象。
    但 livekit-agents 1.8 的 ``AgentActivity._generate_reply`` 在**进入 llm_node 之前**
    就检查 ``self.llm is None``，为 None 时直接抛
    ``RuntimeError: trying to generate reply without an LLM model``。
    于是房间里说一句话就静默失败，一个字都不回——线上日志里攒的就是这条。

    真被调用时报错而不是返回空串：空串会让上层以为「模型无话可说」，
    比直接失败更难查。
    """

    from livekit.agents import llm as _llm

    class _PipelineLLM(_llm.LLM):
        @property
        def model(self) -> str:
            return "companion-pipeline"

        @property
        def provider(self) -> str:
            return "companion"

        def chat(self, *, chat_ctx: Any, tools: Any = None, conn_options: Any = None,
                 **kwargs: Any) -> Any:
            raise RuntimeError(
                "CompanionAgent.llm_node 已经接管出字，不应有人调用 LLM.chat()；"
                "如果看到这条，说明 llm_node 没有被调用到")

    return _PipelineLLM()


def room_voice_id(identity: "RoomIdentity", characters: Any) -> str | None:
    """这个房间该用哪个说话人：从角色卡的 ``voice_ref`` 里取。

    取不到就返回 ``None``，让语音栈退回环境变量的默认值——**不在这一层猜**。
    猜错的表现是「两个角色一个嗓子」，而那正是这条链路要解决的问题本身。

    卡读不出来也不抛：角色卡是发布资产，读盘失败不该让整个房间连不上。入口
    已经拿到了 ``character_id``，人设与历史都按它走，只有音色退回默认。
    """
    if characters is None:
        return None
    try:
        card = characters.load(identity.character_id)
    except Exception as exc:  # noqa: BLE001 —— 缺卡 / 坏卡都不该拦住房间
        logger.warning("voice: cannot load character %s: %s", identity.character_id, exc)
        return None
    voice_id = str((getattr(card, "voice_ref", None) or {}).get("voice_id") or "").strip()
    return voice_id or None


def _preloaded_vad(ctx: Any) -> Any:
    """取 prewarm 在进程级热好的 VAD 模型（`proc.userdata["vad"]`），取不到返回 None。

    链条的最后一棒：prewarm 放、这里取、`build_session_options` 传给 factory。
    少任何一环，`build_voice_stack` 都会在事件循环里重新 load ONNX——stage-3 生产
    每房间冻 7–23s 就是这么来的。dev 模式与测试替身没有 proc，一律容错成 None。
    """
    userdata = getattr(getattr(ctx, "proc", None), "userdata", None)
    if isinstance(userdata, dict):
        return userdata.get("vad")
    return None


def build_session_options(*, mode: str = "text", voice_factory: Any = None,
                          voice_id: str | None = None, vad: Any = None) -> dict:
    """AgentSession 的构造参数。

    文字模式不挂 STT/TTS，语音模式才需要；两者都挂会让文字模式也去合成语音，
    白白烧钱。语音栈由调用方（组合根）注入，接口层不认识具体供应商。

    ``voice_id`` 是**这个房间**的说话人（来自角色卡 ``voice_ref``）。它必须一路
    传到 ``voice_factory``：音色由角色决定，不是进程级配置——否则同一台 worker
    上所有角色共用一个嗓子。

    ``vad`` 是 prewarm 在进程级加载好的 VAD 模型（`ctx.proc.userdata["vad"]`）。
    传进去就绝不会再 load——每房间 load 一次曾把事件循环冻 7–23s（stage-3 生产）。

    ``llm`` 两种模式都要给（原因见 ``_pipeline_llm``）：不给的话房间里的文字输入
    与被识别的语音都走不到 ``llm_node``。
    """
    options: dict[str, Any] = {"llm": _pipeline_llm()}
    if mode == "voice":
        # Continuous VAD activity can hold soft-pause playback indefinitely.
        # Keep hard interruptions, including the explicit client barge-in relay.
        options["turn_handling"] = {
            "endpointing": {
                "min_delay": VOICE_ENDPOINTING_MIN_DELAY,
                "max_delay": VOICE_ENDPOINTING_MAX_DELAY,
            },
            "preemptive_generation": {
                "enabled": VOICE_PREEMPTIVE_GENERATION_ENABLED,
            },
            "interruption": {
                "resume_false_interruption": False,
                "min_words": VOICE_INTERRUPTION_MIN_WORDS,
                "min_duration": VOICE_INTERRUPTION_MIN_DURATION,
                "backchannel_boundary": VOICE_INTERRUPTION_BACKCHANNEL_BOUNDARY,
            },
        }
    if mode == "voice" and voice_factory is not None:
        kwargs: dict[str, Any] = {}
        if voice_id:
            kwargs["voice_id"] = voice_id
        if vad is not None:
            kwargs["vad"] = vad
        tts, stt, *rest = voice_factory(**kwargs)
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


def _checked_wire_voice(wire_voice: Any) -> Any:
    """装配时就确认 ``wire_voice`` 收得下三个位置参，别等到房间 join 才 TypeError。

    入口按 ``wire_voice(platform, voice_id, pending_attachments)`` 调它（第三个是附件槽）。
    这个参数原先是 ``Any``，一个还按两参写的注入会活到 ``_run`` 里才炸——那一刻房间已经
    连上、platform 已经起来，异常落在 LiveKit 的 job 里，日志看不出根因是装配少了一个参数。
    判据是「能不能收下这三个位置参」，不是参数个数：带默认值的可选第三参同样合法。
    """
    if wire_voice is None:
        return None
    try:
        inspect.signature(wire_voice).bind(None, None, None)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "wire_voice 必须是 wire_voice(platform, voice_id, pending_attachments) —— "
            f"这个注入收不下三个位置参：{exc}") from exc
    return wire_voice


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

    def __init__(self, platform_factory: Any, voice_factory: Any = None, wire_voice: Any = None,
                 characters: Any = None) -> None:
        self._platform_factory = platform_factory
        self._voice_factory = voice_factory
        self._wire_voice = _checked_wire_voice(wire_voice)
        # 角色卡来源：只用来解析本房间的说话人（见 ``room_voice_id``）。
        # 是 ``companion.service.roles.port.CharacterSourcePort``，一个 ``load(id)`` 就够；
        # 接口层只认这个形状，不认它读盘还是读服务。
        self._characters = characters

    async def __call__(self, ctx: Any) -> None:
        """worker 的入口。由 LiveKit 的 job context 调用。"""
        require()

        from livekit.agents import AgentSession

        from companion.api.livekit.agent import build_agent_class
        from companion.service.turn.pipeline import TurnPipeline

        # **必须先 connect 再读 metadata。**
        # LiveKit 的 JobContext.room 文档写得很清楚："When the entrypoint is called,
        # the worker has not connected to the Room yet. Certain properties of Room would
        # not be available before calling JobContext.connect()"——metadata 就是其中之一。
        # 原来在这里直接读 ctx.room.metadata，拿到的永远是 None，于是每个房间都被
        # "room metadata missing" 拒掉：语音从来没有成功进来过，而日志里攒了几千条
        # 这个错误，看着像"偶尔失败"，其实是一次都没成。
        await ctx.connect()
        identity = self._identity_of(ctx)
        if identity is None:
            await ctx.room.disconnect()
            return
        await self._run(ctx, identity)

    def _identity_of(self, ctx: Any) -> RoomIdentity | None:
        """连接之后解析身份。解析不出来就拒绝——用一个错误的身份聊一轮，记忆就写错了。"""
        try:
            return RoomIdentity.from_room_metadata(getattr(ctx.room, "metadata", None))
        except ValueError as exc:
            logger.error("refusing room: %s", exc)
            return None

    async def _run(self, ctx: Any, identity: RoomIdentity) -> None:
        from livekit.agents import AgentSession

        from companion.api.livekit.agent import build_agent_class
        from companion.service.turn.pipeline import TurnPipeline

        room = ctx.room
        if identity.chat_session_id is None:
            # 没有会话就没有可共享的历史。不退回独立的语音会话：那正是“文字一份、语音一份”的成因。
            # 断开而不是静默返回：留在房间里的 agent 不响应任何话，用户以为卡住了。
            logger.error("refusing room without chat_session_id user=%s", identity.user_id)
            await room.disconnect()
            return

        platform = await self._platform_factory()
        await platform.astart()
        ctx.add_shutdown_callback(platform.aclose)

        publisher = AvatarPublisher(room)
        publisher.set_local_participant(room.local_participant)

        # 协议 v2 的接线。**必须在 session.start 之前挂上**：客户端连上就会发 hello，
        # 晚挂一步就漏掉那一条，3 秒后会被当成 v1 客户端——一个 v2 客户端就这么被降级了。
        #
        # 两个 identity 都是「我们自己」：`identity` 用来判断 dst 指向谁（发给我才收），
        # `local_identity` 用来把房间回显回来的自家包挡掉。都不是 user_id——用户是对话
        # 的另一端，不是收信人。
        self_identity = getattr(room.local_participant, "identity", None)
        bridge = ProtocolBridge(
            send=local_sender(room),
            identity=self_identity,
            local_identity=self_identity,
        )
        attach(room, bridge)
        # speech.* 的发送口：seg/end/cancel 都经它出去，由 agent 在 TTS 前后调用。
        speech = SpeechPublisher(bridge)
        # v2 锚点 cue：必须在 speech.seg 之后、TTS 之前发（§13 不变量 1）。
        cues = AnchoredCuePublisher(bridge)
        # 握手等待放在后台：它只影响「现在能不能发 cmp.*」，不该拖住语音开场 3 秒。
        handshake = asyncio.create_task(bridge.wait_for_hello())
        # 在任务表里留个引用，避免被 GC 提前回收（asyncio 只持弱引用）。
        _HANDSHAKES.add(handshake)
        handshake.add_done_callback(_HANDSHAKES.discard)

        # 房间说话人解析一次，语音栈与质检记录都用它：TTS 用它出声，记录用它写 tts_voice。
        # 分成两处各自解析会出现「说的是 A、记的是 B」这种事后没法查的错。
        voice_id = room_voice_id(identity, self._characters)

        # 附件暂存位：写它的是数据通道（CompositeInputRelay），读它的是回合
        # （PlatformBrain.start_turn）。**必须是同一个实例**——两个实例的话事件写进 A、
        # 回合读 B，带图消息静默变成纯文本，一条错误都不报。
        pending = PendingAttachmentSlot()
        parts: VoiceParts = self._wire_voice(platform, voice_id, pending)
        # event_sink 只喂 v1 companion.avatar；v2 presentation.* 走 AnchoredCuePublisher。
        pipeline = TurnPipeline(parts.brain, event_sink=ProtocolCueSink(publisher))
        agent_class = build_agent_class()

        # 提示词由回合引擎按会话组装（角色卡、技能、记忆、画像），这里不再自己拼一份。
        agent = agent_class(
            pipeline=pipeline,
            character_id=identity.character_id,
            user_id=identity.user_id,
            chat_session_id=identity.chat_session_id,
            recorder=parts.recorder,
            tts_sink=parts.tts_sink,
            speech=speech,
            cues=cues,
        )

        # 语音栈必须显式按 voice 模式装配：不传 mode 时默认是 text，STT/TTS/VAD 都不会挂上，
        # 表现是「agent 进房间了但一句话不说」。
        #
        # 音色跟着角色走：说话人由本房间的 ``character_id`` 解析出的角色卡 ``voice_ref`` 决定。
        # 不传的话每个房间都落到进程级默认值，两个角色一个嗓子。
        session = AgentSession(**build_session_options(
            mode="voice", voice_factory=self._voice_factory, voice_id=voice_id,
            vad=_preloaded_vad(ctx)))

        await session.start(agent, room=room)
        # Mode B 探针：INFO 打出第一帧 / track_subscribed / user_state。
        # 必须在 start 之后——RoomIO 这时才把 audio input 挂到 session.input。
        attach_inbound_audio_probe(session, room)
        # Publish-path 探针：chain/source peak + pause/resume（静音下行 RCA）。
        # start 之后才挂：这时 Recorder/Synchronizer/RoomIO 链已经接好。
        attach_outbound_audio_probe(session)
        # control.input 的分发器：kind=touch → 触摸句 → generate_reply；
        # kind=attachments → 上面那个 pending 槽（由回合并入 submit）。
        # 必须在 start 之后挂：session 还没起来时发 generate_reply 会炸；
        # 挂晚一点没事，最多丢掉开场几秒内的点按与附件事件。
        bridge.on_input = CompositeInputRelay(session, pending, cooldown_s=DEFAULT_COOLDOWN_S)
        # 用户开口打断：interrupt 截断 TTS，speech.cancel 立刻发 control.cancel（§10）。
        bridge.on_barge = BargeInRelay(session, speech)
        logger.info(
            "companion joined room user=%s character=%s",
            identity.user_id,
            identity.character_id,
        )


def make_entrypoint(platform_factory: Any, voice_factory: Any = None, wire_voice: Any = None,
                    characters: Any = None) -> RoomEntrypoint:
    """装配好的 worker 入口。返回的是可 pickle 的对象（见 ``RoomEntrypoint`` 的说明）。"""
    return RoomEntrypoint(platform_factory, voice_factory, wire_voice, characters)
