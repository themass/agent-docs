"""主动开口：让角色在用户和她的那段对话里说一句话。

和语音一样走回合引擎（``PlatformBrain`` → ``SubmitService``）：这句话会落进该用户与该角色唯一的
会话历史，下次用户打开对话能看到“她说过”，记忆与画像也跟着更新。以前主动消息走另一套内存版编排，
说过的话不在任何历史里。
"""

from __future__ import annotations

from typing import Any

from companion.service.room.resolve import ChatSessionError, resolve_chat_session
from companion.service.proactive.loop import SpeakDenied
from companion.service.turn.trigger import Trigger
from companion.agent.brain.port import TurnRefused, TurnRequest


class PlatformSpeaker:
    def __init__(self, *, sessions: Any, brain: Any, compliance: Any = None) -> None:
        """``brain`` 是 BrainPort，由组合根构造成 system/proactive 身份：模型看到的是带标记的指令，
        会话忙时排队而不是插进别人的回合。"""
        self._sessions = sessions
        self._compliance = compliance
        self._brain = brain

    async def __call__(self, trigger: Trigger) -> str:
        if not trigger.user_id.isdigit():
            raise SpeakDenied("bad_user")
        if self._compliance is not None and not await self._compliance.proactive_allowed(
                owner_id=int(trigger.user_id)):
            # 用户关了“主动联系”总开关：与偏好里的开关是两道，这是合规层的同意
            raise SpeakDenied("consent")
        try:
            session_id = await resolve_chat_session(
                self._sessions, user_id=trigger.user_id, character_id=trigger.character_id, chat_session_id=None)
        except ChatSessionError as exc:
            raise SpeakDenied("no_session") from exc
        request = TurnRequest(user_id=trigger.user_id, character_id=trigger.character_id,
                              message=trigger.message(), session_id=session_id)
        try:
            turn = await self._brain.start_turn(request)
        except TurnRefused as exc:
            raise SpeakDenied(exc.reason or "refused") from exc
        return "".join([chunk async for chunk in turn.tokens])
