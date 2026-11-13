"""PlatformSpeaker：主动开口走回合引擎，落进用户与角色唯一的那段会话。"""

from types import SimpleNamespace

import pytest

from companion.service.proactive.loop import SpeakDenied
from companion.service.proactive.speaker import PlatformSpeaker
from companion.service.turn.queue import Disposition
from companion.service.turn.trigger import Trigger, TriggerKind
from test_platform_brain import FakeControl, FakeSubmit, TURN, _happy
from test_voice_session import Sessions


def _trigger(user="1002", role="linche") -> Trigger:
    return Trigger(kind=TriggerKind.EVENT_DUE, user_id=user, character_id=role,
                   payload={"title": "面试", "event_id": "e1"}, origin="event:e1")


class Compliance:
    def __init__(self, allowed=True):
        self.allowed, self.asked = allowed, []

    async def proactive_allowed(self, *, owner_id):
        self.asked.append(owner_id)
        return self.allowed


def _speaker(submit, control, sessions=None, compliance=None):
    from companion.service.turns.platform_brain import PlatformBrain

    brain = PlatformBrain(submit=submit, control=control, role="system", kind="proactive")
    return PlatformSpeaker(sessions=sessions or Sessions(), brain=brain, compliance=compliance)


async def test_she_speaks_through_the_turn_engine_as_a_system_proactive_message():
    control = FakeControl()
    submit = FakeSubmit(control, _happy)
    text = await _speaker(submit, control)(_trigger())

    assert text == "先歇一会儿，我在。"
    call = submit.calls[0]
    assert (call["role"], call["kind"], call["steerable"]) == ("system", "proactive", False)
    assert call["owner_id"] == 1002 and call["character_id"] == "linche"


async def test_it_lands_in_the_one_session_of_this_user_and_role():
    control, sessions = FakeControl(), Sessions()
    submit = FakeSubmit(control, _happy)
    speaker = _speaker(submit, control, sessions)
    await speaker(_trigger())
    await speaker(_trigger())
    assert len(sessions.rows) == 1                       # 复用，而不是每次主动开口新建一段
    assert {c["session_id"] for c in submit.calls} == set(sessions.rows)


async def test_a_user_who_turned_proactive_off_is_not_spoken_to():
    control = FakeControl()
    submit = FakeSubmit(control, _happy)
    compliance = Compliance(allowed=False)
    with pytest.raises(SpeakDenied) as info:
        await _speaker(submit, control, compliance=compliance)(_trigger())
    assert info.value.reason == "consent"
    assert submit.calls == [] and compliance.asked == [1002]


async def test_a_content_check_refusal_becomes_a_denial():
    control = FakeControl()
    submit = FakeSubmit(control, _happy, status="denied", disposition=None, turn_id=None)
    with pytest.raises(SpeakDenied) as info:
        await _speaker(submit, control)(_trigger())
    assert info.value.reason == "blocked"


async def test_a_busy_session_yields_no_text_so_the_loop_sends_nothing():
    # 会话正忙：这条指令已排队，由当前回合结束后处理；这里不挂等，返回空串，循环会按 empty_turn 跳过
    control = FakeControl()
    submit = FakeSubmit(control, _happy, disposition=Disposition.QUEUED, turn_id=None)
    assert await _speaker(submit, control)(_trigger()) == ""


async def test_a_non_numeric_user_is_denied_before_anything_happens():
    control = FakeControl()
    submit = FakeSubmit(control, _happy)
    with pytest.raises(SpeakDenied):
        await _speaker(submit, control)(_trigger(user="alice"))
    assert submit.calls == []
