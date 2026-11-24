"""离线跑 YAML case：FakeBrain 文本 → SpeechPublisher + cue 编译 → 录协议时间线。

不 import LiveKit；假 bridge 只记调用类型字符串，供 pytest 断言。
"""

from __future__ import annotations

from typing import Any

from companion.agent.brain.fake import FakeBrain
from companion.agent.brain.port import TurnRequest
from companion.agent.protocol.cue_compiler import CueBudget, compile_cues
from companion.agent.protocol.fragment import ingest
from companion.agent.text.splitter import SentenceSplitter
from companion.api.livekit.speech_publisher import SpeechPublisher
from companion.devtools.script_room.case_schema import ScriptCase


class RecordingBridge:
    """``SpeechPublisher`` / cue 路径用的假 bridge：按调用顺序记下事件类型名。

    ``presentation.state`` 额外把状态值记进 ``states``：时间线断言既要看见
    「发过状态事件」，也要看见是哪一个（thinking→speaking→…的次序是契约 v2 §1
    的验收点）。
    """

    def __init__(self) -> None:
        self.types: list[str] = []
        self.states: list[str] = []

    async def speech_seg(self, speech_id: str, seg: Any) -> bool:
        self.types.append("speech.seg")
        return True

    async def speech_end(self, speech_id: str) -> bool:
        self.types.append("speech.end")
        return True

    async def cancel_speech(self, speech_id: str, reason: str = "user_barge_in") -> bool:
        self.types.append("control.cancel")
        return True

    async def presentation_state(self, state: str) -> bool:
        self.types.append("presentation.state")
        self.states.append(state)
        return True

    async def cue_emotion(
        self,
        name: str,
        *,
        intensity: float | None = None,
        at: dict[str, Any] | None = None,
    ) -> bool:
        self.types.append("presentation.emotion")
        return True

    async def publish(
        self,
        event_type: str,
        args: dict[str, Any],
        *,
        topic: str | None = None,
        force: bool = False,
        at: dict[str, Any] | None = None,
        dst: list[str] | None = None,
    ) -> bool:
        self.types.append(event_type)
        return True


async def drive_reply_line(
    text: str,
    *,
    publisher: SpeechPublisher,
    bridge: Any,
    turn_id: str,
    budget: CueBudget | None = None,
) -> list[str]:
    """驱动一句假脑输出：断句 → ``say`` → 解析标签/片段 → ``compile_cues`` → 记 emotion。

    返回本句实际朗读文本列表（剥标签后的 ``frag.say``），供 Task 5 TTS/PCM 复用。
    bridge 需提供 ``cue_emotion`` / ``publish``（RecordingBridge 或 BridgeOverRtc）。
    """
    if budget is None:
        budget = CueBudget()
    splitter = SentenceSplitter()
    said: list[str] = []
    for sentence in splitter.feed(text) + splitter.flush():
        frag = ingest(sentence)
        declared = await publisher.say(frag.say, turn_id=turn_id)
        if frag.say.strip():
            said.append(frag.say)
        if declared is None or not frag.intents:
            continue
        speech_id, seg = declared
        budget.stats.note_source(frag.source)
        compiled = compile_cues(
            frag.intents,
            speech_id=speech_id,
            seg_idx=seg.idx,
            budget=budget,
        )
        for cue in compiled:
            if cue.event_type == "presentation.emotion":
                await bridge.cue_emotion(cue.args.get("name", ""), at=cue.at)
            else:
                await bridge.publish(cue.event_type, cue.args, at=cue.at)
    return said


#: barge 注入时假定的播放位置：第一条句已播完、第二条播到一半。
#: 离线 case 没有真播放时钟，但前缀断言需要一个确定的数字（契约 v2 §2.2）。
DEFAULT_BARGE_PLAYED_MS = 900


async def run_offline(case: ScriptCase, *, bridge: RecordingBridge | None = None) -> list[str]:
    """按 case 步骤跑一遍离线协议路径，返回事件类型名序列。

    ``bridge`` 可注入（测试要单独读 ``states`` 时传自己的 RecordingBridge）。
    """
    if bridge is None:
        bridge = RecordingBridge()
    publisher = SpeechPublisher(bridge, state_sink=bridge.presentation_state)  # type: ignore[arg-type]
    budget = CueBudget()
    cancelled = False
    turn_id = f"script-{case.id}"

    reply_lines = [
        line
        for step in case.steps
        if step.expect_reply is not None
        for line in step.expect_reply
    ]
    brain = FakeBrain(script=reply_lines)

    # 用 FakeBrain 保证剧本与假脑脚本同源；离线按步骤消费，不走真实回合管线。
    await brain.start_turn(
        TurnRequest(user_id="script", character_id="script", message=case.id)
    )

    await publisher.start_reply()
    line_iter = iter(reply_lines)

    for step in case.steps:
        if step.expect_reply is not None:
            for _ in step.expect_reply:
                line = next(line_iter)
                await drive_reply_line(
                    line,
                    publisher=publisher,
                    bridge=bridge,
                    turn_id=turn_id,
                    budget=budget,
                )
        elif step.inject == "barge_in":
            # 离线没有播放时钟：按固定 played_ms 注入，让前缀路径在断言里真跑一遍。
            await publisher.cancel(played_ms=DEFAULT_BARGE_PLAYED_MS)
            cancelled = True
            break
        # user / protocol：离线不执行（protocol 由断言对照；user 留给 capture 阶段）

    if not cancelled:
        await publisher.finish()

    await brain.aclose()
    return list(bridge.types)
