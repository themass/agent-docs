"""把 ProtocolBridge 接到 RtcAdapter.publish_data，并记录时间线事件类型名。

剧本房要求 v2 hello：**fail closed**（不静默退 v1）。入向 hello 可由
:meth:`simulate_hello` 注入（Memory 单测）；真房侧后续可把 data_received 喂进
``inner.on_data``。
"""

from __future__ import annotations

import asyncio
from typing import Any

from companion.agent.protocol import SERVER_CAPS, encode, new_envelope
from companion.agent.protocol.catalog import TOPIC_CTL
from companion.agent.protocol.handshake import HelloAck, LEGACY_WAIT_SECONDS
from companion.agent.protocol.speech_plan import PlannedSegment
from companion.api.livekit.protocol_bridge import ProtocolBridge
from companion.devtools.script_room.rtc import RtcAdapter


class BridgeOverRtc:
    """SpeechPublisher / cue 路径兼容的桥：外发走 ``rtc.publish_data``，并记 ``types``。"""

    def __init__(
        self,
        rtc: RtcAdapter,
        *,
        identity: str = "script-agent",
        sid: str | None = None,
        hello_timeout_sec: float = LEGACY_WAIT_SECONDS,
        client_identity: str = "script-client",
    ) -> None:
        self._rtc = rtc
        self.types: list[str] = []
        self.hello_timeout_sec = hello_timeout_sec
        self._client_identity = client_identity

        async def _send(topic: str, payload: bytes) -> None:
            await rtc.publish_data(topic, payload)

        self.inner = ProtocolBridge(
            send=_send,
            identity=identity,
            local_identity=identity,
            sid=sid or "script",
            legacy_timeout=hello_timeout_sec,
        )

    # ------------------------------------------------------------------ SpeechPublisher duck

    async def speech_seg(self, speech_id: str, seg: PlannedSegment) -> bool:
        ok = await self.inner.speech_seg(speech_id, seg)
        if ok:
            self.types.append("speech.seg")
        return ok

    async def speech_end(self, speech_id: str) -> bool:
        ok = await self.inner.speech_end(speech_id)
        if ok:
            self.types.append("speech.end")
        return ok

    async def cancel_speech(self, speech_id: str, reason: str = "user_barge_in") -> bool:
        ok = await self.inner.cancel_speech(speech_id, reason=reason)
        if ok:
            self.types.append("control.cancel")
        return ok

    async def cue_emotion(
        self,
        name: str,
        intensity: float | None = None,
        *,
        at: dict[str, Any] | None = None,
    ) -> bool:
        ok = await self.inner.cue_emotion(name, intensity, at=at)
        if ok:
            self.types.append("presentation.emotion")
        return ok

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
        from companion.agent.protocol.catalog import TOPIC_CUE

        ok = await self.inner.publish(
            event_type,
            args,
            topic=topic or TOPIC_CUE,
            force=force,
            at=at,
            dst=dst,
        )
        if ok:
            self.types.append(event_type)
        return ok

    # ------------------------------------------------------------------ hello

    async def wait_for_hello(self) -> HelloAck:
        """等 ``control.hello``。超时 **raise**（剧本房不静默 v1）。"""
        if self.inner.ack is not None and not self.inner.legacy:
            return self.inner.ack
        try:
            await asyncio.wait_for(
                self.inner._hello_seen.wait(),  # noqa: SLF001 — 与 ProtocolBridge 同进程门禁
                timeout=self.hello_timeout_sec,
            )
        except TimeoutError as exc:
            raise TimeoutError(
                "script room requires control.hello (fail closed; no silent v1)"
            ) from exc
        if self.inner.ack is None:
            raise TimeoutError(
                "script room requires control.hello (fail closed; no silent v1)"
            )
        return self.inner.ack

    async def simulate_hello(self) -> None:
        """测试 / Memory 路径：注入一条合法 ``control.hello``。"""
        payload = encode(
            new_envelope(
                "control.hello",
                args={
                    "proto": {"min": 2, "max": 2},
                    "caps": dict(SERVER_CAPS),
                    "limits": {"max_payload_bytes": 4096},
                    "client": {"app": "companion", "version": "script-test", "sdk": "test"},
                },
                seq=0,
                ep="ep-script",
                ident="h-script",
            )
        )
        await self.inner.on_data(
            payload,
            topic=TOPIC_CTL,
            publisher_identity=self._client_identity,
            publisher_kind="STANDARD",
        )
