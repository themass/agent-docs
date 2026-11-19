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

from companion.service.turn.pipeline import TurnPipeline
from companion.agent.brain.port import TurnRefused, TurnRequest
from companion.api.livekit.bridge import require

logger = logging.getLogger(__name__)

__all__ = ["build_agent_class", "build_request", "last_user_confidence", "last_user_message"]


REFUSED_LINE = "这个我不太方便聊，我们说点别的吧。"
UNAVAILABLE_LINE = "我这边出了点状况，你再说一次好吗？"


class _NoSpeech:
    """没注入 SpeechPublisher 时的空实现：离线测试与未接协议的路径照旧走，什么都不发。"""

    async def start_reply(self) -> None:
        return None

    async def say(self, text: str, *, turn_id: str):
        return None

    async def finish(self) -> None:
        return None

    async def cancel(self, reason: str = "user_barge_in") -> None:
        return None


class _NoCues:
    """没注入 AnchoredCuePublisher 时的空实现。"""

    def reset_turn(self) -> None:
        return None

    async def publish_for_segment(self, intents: Any, *, speech_id: str, seg_idx: int, source: str = "tag") -> int:
        return 0


_NO_SPEECH = _NoSpeech()
_NO_CUES = _NoCues()


def build_request(*, user_id: str, character_id: str, message: str, chat_session_id: int) -> TurnRequest:
    """组一回合的请求。对话线程由 ``session_id`` 决定，与文字共用同一个。"""
    return TurnRequest(
        user_id=user_id,
        character_id=character_id,
        message=message,
        session_id=chat_session_id,
    )


def _clip(text: str, limit: int = 200) -> str:
    """日志里的一行放不下整段转写：截断并注明，别让排查的人以为话说完了。"""
    return text if len(text) <= limit else text[:limit] + f"…(+{len(text) - limit})"


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
            speech: Any = None,
            cues: Any = None,
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
            # 协议 v2 的 speech.* 发送口（SpeechPublisher 形状）。不给就整段跳过，行为与之前一致。
            self._speech = speech if speech is not None else _NO_SPEECH
            # 协议 v2 的锚点 cue 发送口。不给就跳过 presentation.*（离线测试）。
            self._cues = cues if cues is not None else _NO_CUES
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
            # 现场排障全靠这两行：通话出问题时，QA 库未必存了内容（要用户同意），
            # 而"她到底听错了什么、她回了什么"必须先看见。截断防超长转写刷屏。
            logger.info("voice turn user=%s role=%s said=%r", self._user_id, self._character_id,
                        _clip(message))
            confidence = last_user_confidence(chat_ctx)
            request = build_request(
                user_id=self._user_id,
                character_id=self._character_id,
                message=message,
                chat_session_id=self._chat_session_id,
            )
            # 新回合先清掉上一回合挂着的 speech（若有）：§10，用户已经开口了。
            await self._speech.start_reply()
            self._cues.reset_turn()
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
                        # §13 不变量 1：speech.seg(k) → 挂着它的 presentation.* → TTS(k)。
                        turn_id = self._current_turn_id()
                        declared = None
                        if turn_id:
                            declared = await self._speech.say(output.text, turn_id=turn_id)
                        if declared is not None:
                            speech_id, seg = declared
                            intents = getattr(output, "intents", None) or []
                            if intents:
                                await self._cues.publish_for_segment(
                                    intents,
                                    speech_id=speech_id,
                                    seg_idx=seg.idx,
                                    source=getattr(output, "source", "tag"),
                                )
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
                logger.info("voice reply user=%s role=%s first_ms=%s total_ms=%s interrupted=%s said=%r",
                            self._user_id, self._character_id, first_ms,
                            int((time.monotonic() - started) * 1000), not finished,
                            _clip("".join(sentences)))
                # 被打断时生成器会在这里被关闭：记录要放到后台任务里，不能在关闭路径上 await
                self._record(message, sentences, first_ms, int((time.monotonic() - started) * 1000),
                             interrupted=not finished, confidence=confidence)

        def _record(self, message: str, sentences: list[str], first_ms: int | None, total_ms: int, *,
                    interrupted: bool, confidence: float | None = None) -> None:
            turn = self._pipeline.last_turn
            if self._recorder is None or turn is None or not turn.turn_id:
                return    # 没有回合（被拒绝、排队）就没有可对账的记录
            from companion.service.trace.qa import VoiceTurnRecord

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
            """合成语音，并留下 start/done（含 peak）观测；有质检 sink 时再 tee 归档。

            这里拿到的文本是框架做完文本变换（默认过滤 markdown / emoji）之后真正送给合成引擎的那份。
            观测日志**常开**——静音下行排查不能依赖 QA sink 是否挂上。没配 sink 时只记日志、不写归档。
            """
            frames = self._captured_tts(text, model_settings)
            if self._speech is _NO_SPEECH:
                return frames
            return self._speech_scoped(frames)

        async def _speech_scoped(self, frames: Any):
            """TTS 生成侧排空 → ``speech.end``；中途被关闭（打断、出错）→ ``control.cancel``。

            ``finish`` 挂在帧迭代正常结束后：表示本轮音频帧已全部 yield 给框架，
            **不是**端侧扬声器播完（§9.3）。被关闭时先把内层生成器也关掉：采集的
            归档写在它的 finally 里，不关就要等 GC。
            """
            done = False
            try:
                async for frame in frames:
                    yield frame
                done = True
            finally:
                if done:
                    await self._speech.finish()
                else:
                    close = getattr(frames, "aclose", None)
                    try:
                        if close is not None:
                            await close()
                    finally:
                        self._spawn(self._speech.cancel())

        async def _captured_tts(self, text: Any, model_settings: Any):
            from companion.service.voice.tts_capture import TtsCapture

            capture = TtsCapture()
            turn_ref: dict[str, Any] = {}

            async def watched(chunks: Any):
                async for chunk in chunks:
                    # 第一段文本到达时，这句话属于哪个回合就定了；等到结束再取，可能已经是下一个回合
                    turn_ref.setdefault("turn", self._pipeline.last_turn)
                    yield chunk

            completed = False
            # 静音下行排查：tts start 证明被调用；tts done 的 frames/audio_ms 是字节时长，
            # peak/nonzero 才是样本能量。零填充帧也会 frames>0——所以 peak=0 才说明合成侧静音。
            # 火山插件“无音频块”会抛错，但仍可能吐全零 PCM。
            from companion.api.livekit.inbound_audio_probe import frame_nonzero, frame_peak

            turn_id = self._current_turn_id()
            logger.info("tts start turn=%s", turn_id or "-")
            frames_out = 0
            audio_ms = 0
            peak_max = 0.0
            nonzero = 0
            try:
                # 默认实现是异步生成器（async def + yield），调用得到的就是生成器，不能 await
                # 没挂 tts_sink 时 TtsCapture 仍 tee，只是 finally 不归档。
                frames = Agent.default.tts_node(self, capture.tee_text(watched(text)), model_settings)
                async for frame in capture.tee_frames(frames):
                    frames_out += 1
                    rate = int(getattr(frame, "sample_rate", 0) or 0)
                    channels = int(getattr(frame, "num_channels", 1) or 1)
                    if rate and channels:
                        audio_ms += int(len(frame.data) * 1000 // (2 * rate * channels))
                    peak = frame_peak(frame)
                    if peak > peak_max:
                        peak_max = peak
                    nonzero += frame_nonzero(frame)
                    yield frame
                completed = True
            finally:
                logger.info(
                    "tts done turn=%s frames=%d audio_ms=%d peak=%.4f nonzero=%d completed=%s",
                    turn_id or "-", frames_out, audio_ms, peak_max, nonzero, completed,
                )
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
            await self._speech.cancel()
            await self._pipeline.cancel()

        def _current_turn_id(self) -> str:
            turn = self._pipeline.last_turn
            return turn.turn_id if turn is not None and turn.turn_id else ""

        def _spawn(self, coro: Any) -> None:
            task = asyncio.ensure_future(coro)
            self._background.add(task)
            task.add_done_callback(self._background.discard)

    return CompanionAgent
