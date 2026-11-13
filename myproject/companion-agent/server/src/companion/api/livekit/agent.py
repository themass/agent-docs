"""LiveKit 房间内的 agent：``llm_node`` 交给回合管线，自己只做壳。

重写 ``llm_node`` 让 DeerFlow 成为真正的主脑；TTS、VAD、打断、音频发布仍是
LiveKit Agents 的事。所有会写错的逻辑（断句、剥情绪标签、取消）都在
``TurnPipeline`` 里，这里只负责：读用户数据 → 组 ``TurnRequest`` → 转发管线输出。

livekit-agents 只在 ``build_agent_class`` 里导入，模块本身可以脱离它被 import，
否则 HTTP 接口与单测都会被语音栈连带拖垮。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from companion.turn.pipeline import EventSink, TurnPipeline
from companion.brain.port import TurnRefused, TurnRequest
from companion.api.livekit.bridge import require

logger = logging.getLogger(__name__)

__all__ = ["build_agent_class", "build_event_sink", "build_request", "last_user_confidence", "last_user_message"]


REFUSED_LINE = "这个我不太方便聊，我们说点别的吧。"
UNAVAILABLE_LINE = "我这边出了点状况，你再说一次好吗？"


def build_request(*, user_id: str, character_id: str, message: str, chat_session_id: int) -> TurnRequest:
    """组一回合的请求。对话线程由 ``session_id`` 决定，与文字共用同一个。"""
    return TurnRequest(
        user_id=user_id,
        character_id=character_id,
        message=message,
        session_id=chat_session_id,
    )


def last_user_message(chat_ctx: Any) -> str:
    """取上下文里最后一条用户消息。

    ChatContext 的字段随版本变过，这里按「items → role/text_content」读，也兼容
    纯字符串 content 列表。读不到就返回空串：宁可不回复，也不要拿半截上下文去问。
    """
    items = getattr(chat_ctx, "items", None)
    if not items:
        return ""
    for item in reversed(list(items)):
        if getattr(item, "role", None) != "user":
            continue
        text = getattr(item, "text_content", None)
        if not isinstance(text, str) or not text.strip():
            content = getattr(item, "content", None)
            if isinstance(content, list):
                text = "".join(part for part in content if isinstance(part, str))
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


def last_user_confidence(chat_ctx: Any) -> float | None:
    """最后一条用户消息的识别置信度。供应商没返回时框架给的是 0.0，那是“未知”而不是“完全不确定”，
    存进去会让质检把所有这类回合都当成低置信度，所以 0 和缺失都按 None。"""
    for item in reversed(list(getattr(chat_ctx, "items", None) or [])):
        if getattr(item, "role", None) != "user":
            continue
        value = getattr(item, "transcript_confidence", None)
        return float(value) if isinstance(value, (int, float)) and 0.0 < value <= 1.0 else None
    return None


def build_event_sink(room: Any) -> EventSink:
    """把形象事件写成 LiveKit 数据通道里的文本消息。

    发送失败只记日志：事件是装饰，丢了不该让正在说的那句话出错。任务引用留在
    集合里，否则 ``publish_data`` 可能被 GC 提前回收。
    """
    pending: set[asyncio.Task[Any]] = set()

    def sink(payload: str) -> None:
        participant = getattr(room, "local_participant", None)
        if participant is None:
            return
        try:
            task = asyncio.create_task(_publish(participant, payload))
        except RuntimeError:
            # 没有运行中的事件循环（例如同步调用）——直接放弃，不阻塞回复
            logger.debug("avatar event dropped: no running loop")
            return
        pending.add(task)
        task.add_done_callback(pending.discard)

    async def _publish(participant: Any, payload: str) -> None:
        try:
            await participant.publish_data(payload.encode("utf-8"), reliable=True)
        except Exception as exc:  # noqa: BLE001
            logger.debug("avatar event publish failed: %s", exc)

    return sink


def build_agent_class() -> type:
    """构造 ``Agent`` 子类。父类必须在 import 时存在，所以包缺失在这里报错。"""
    require()

    from livekit.agents import Agent  # noqa: PLC0415 —— 见 docstring

    class CompanionAgent(Agent):
        """房间内的单个角色。依赖在房间建立时注入，agent 自己不查角色、不开线程。"""

        def __init__(
            self,
            *,
            pipeline: TurnPipeline,
            user_id: str,
            character_id: str,
            chat_session_id: int,
            recorder: Any = None,
            tts_sink: Any = None,
        ) -> None:
            # 提示词由回合引擎按会话组装；llm_node 被重写后框架不会用到这里的 instructions
            super().__init__(instructions="")
            self._pipeline = pipeline
            self._user_id = user_id
            self._character_id = character_id
            self._chat_session_id = chat_session_id
            # 语音质检记录的写入口：async (VoiceTurnRecord) -> None。不给就不记（离线测试）。
            self._recorder = recorder
            # TTS 采集的写入口：async (**turn 信息, segment=TtsSegment)。不给就不采集（不改变 tts_node 行为）。
            self._tts_sink = tts_sink
            self._background: set[asyncio.Task[Any]] = set()

        async def llm_node(
            self,
            chat_ctx: Any,
            tools: list[Any],
            model_settings: Any,
        ) -> AsyncIterator[str]:
            """产出整句文本。

            断句已在管线里完成，LiveKit 拿到的每一段都是可读的整句，TTS 不必再猜
            句末；情绪标签在这里已经被剥掉，只以事件的形式走数据通道。
            """
            message = last_user_message(chat_ctx)
            if not message:
                return
            confidence = last_user_confidence(chat_ctx)
            request = build_request(
                user_id=self._user_id,
                character_id=self._character_id,
                message=message,
                chat_session_id=self._chat_session_id,
            )
            started = time.monotonic()
            first_ms: int | None = None
            sentences: list[str] = []
            finished = False
            try:
                async for output in self._pipeline.run(request):
                    if output.text:
                        if first_ms is None:
                            first_ms = int((time.monotonic() - started) * 1000)
                        sentences.append(output.text)
                        yield output.text
                finished = True
            except TurnRefused:
                # 输入没过内容检查：用户该听到一句话，而不是房间突然安静
                finished = True
                yield REFUSED_LINE
            except ValueError as exc:
                logger.error("voice turn not startable: %s", exc)
                finished = True
                yield UNAVAILABLE_LINE
            finally:
                # 被打断时生成器会在这里被关闭：记录要放到后台任务里，不能在关闭路径上 await
                self._record(message, sentences, first_ms, int((time.monotonic() - started) * 1000),
                             interrupted=not finished, confidence=confidence)

        def _record(self, message: str, sentences: list[str], first_ms: int | None, total_ms: int, *,
                    interrupted: bool, confidence: float | None = None) -> None:
            turn = self._pipeline.last_turn
            if self._recorder is None or turn is None or not turn.turn_id:
                return    # 没有回合（被拒绝、排队）就没有可对账的记录
            from companion.adapters.store.sql.qa import VoiceTurnRecord

            record = VoiceTurnRecord(
                turn_id=turn.turn_id, session_id=self._chat_session_id, owner_id=int(self._user_id),
                role_id=self._character_id, user_message_id=turn.user_message_id, stt_text=message,
                stt_confidence=confidence, first_sentence_ms=first_ms, total_ms=total_ms,
                interrupted=True if interrupted else None)
            task = asyncio.ensure_future(self._safe_record(record))
            self._background.add(task)
            task.add_done_callback(self._background.discard)

        async def _safe_record(self, record: Any) -> None:
            try:
                await self._recorder(record)
            except Exception:  # noqa: BLE001 —— 记录是旁路，失败不能影响通话
                logger.warning("voice turn record failed turn=%s", record.turn_id)

        async def tts_node(self, text: Any, model_settings: Any):
            """合成语音，同时留一份“送进 TTS 的文本 + 出来的音频”，供质检判断 TTS 准不准。

            这里拿到的文本是框架做完文本变换（默认过滤 markdown / emoji）之后真正送给合成引擎的那份。
            没配采集（离线、没开质检）时直接走默认实现，行为完全不变。
            """
            if self._tts_sink is None:
                return Agent.default.tts_node(self, text, model_settings)
            return self._captured_tts(text, model_settings)

        async def _captured_tts(self, text: Any, model_settings: Any):
            from companion.voice.tts_capture import TtsCapture

            capture = TtsCapture()
            turn_ref: dict[str, Any] = {}

            async def watched(chunks: Any):
                async for chunk in chunks:
                    # 第一段文本到达时，这句话属于哪个回合就定了；等到结束再取，可能已经是下一个回合
                    turn_ref.setdefault("turn", self._pipeline.last_turn)
                    yield chunk

            completed = False
            try:
                # 默认实现是异步生成器（async def + yield），调用得到的就是生成器，不能 await
                frames = Agent.default.tts_node(self, capture.tee_text(watched(text)), model_settings)
                async for frame in capture.tee_frames(frames):
                    yield frame
                completed = True
            finally:
                self._archive_tts(capture, turn_ref.get("turn"), completed)

        def _archive_tts(self, capture: Any, turn: Any, completed: bool) -> None:
            # 被打断时生成器在这里被关闭：写库放后台，不能在关闭路径上 await
            if self._tts_sink is None or turn is None or not turn.turn_id or not capture.started:
                return
            segment = capture.finish(completed=completed)
            task = asyncio.ensure_future(self._safe_tts(turn, segment))
            self._background.add(task)
            task.add_done_callback(self._background.discard)

        async def _safe_tts(self, turn: Any, segment: Any) -> None:
            try:
                await self._tts_sink(turn_id=turn.turn_id, session_id=self._chat_session_id,
                                     owner_id=int(self._user_id), role_id=self._character_id,
                                     user_message_id=turn.user_message_id, segment=segment)
            except Exception:  # noqa: BLE001 —— 记录是旁路，失败不能影响通话
                logger.warning("tts record failed turn=%s", turn.turn_id)

        async def cancel_turn(self) -> None:
            """用户打断。由框架或上层调用；幂等。"""
            await self._pipeline.cancel()

    return CompanionAgent
