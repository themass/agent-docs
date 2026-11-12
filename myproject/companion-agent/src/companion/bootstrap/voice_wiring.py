"""语音房间的零件装配（组合根）：大脑、质检记录、TTS 采集的具体实现在这里构造。

接口层（``api/livekit``）只认 ``VoiceParts`` 的形状；分层契约不允许它引适配器和组合根，
所以"用哪个实现"这个决定只能放在这里，由 ``worker.py`` 传给 ``make_entrypoint``。
"""

from __future__ import annotations

from typing import Any

from companion.adapters.brain.platform_brain import PlatformBrain
from companion.adapters.voice.tts_archive import TtsArchiver
from companion.api.livekit.entrypoint import VoiceParts


def build_voice_recorder(platform: Any, voice_info: dict[str, str] | None = None):
    """语音回合的质检记录写入口。内容（识别文本、送去合成的句子）只在用户同意质检留存时才写；
    供应商与音色这类不含用户原话的信息总是写。"""
    info = voice_info or {}
    qa, compliance = getattr(platform, "qa", None), getattr(platform, "compliance", None)
    if qa is None or not getattr(platform, "qa_enabled", True):
        return None

    async def record(rec: Any) -> None:
        rec.stt_provider = info.get("stt_provider", "")
        rec.tts_provider, rec.tts_voice = info.get("tts_provider", ""), info.get("tts_voice", "")
        keep = await compliance.qa_content_allowed(owner_id=rec.owner_id) if compliance is not None else False
        await qa.record_voice_turn(rec, keep_content=keep)

    return record


def build_tts_archiver(platform: Any, voice_info: dict[str, str] | None = None):
    """TTS 采集的归档器：文本与耗时写库，音频（用户同意后）传对象存储。没有质检存储就不采集。"""
    if getattr(platform, "qa", None) is None or not getattr(platform, "qa_enabled", True):
        return None
    info = voice_info or {}
    return TtsArchiver(qa=platform.qa, compliance=getattr(platform, "compliance", None),
                       objects=getattr(platform, "objects", None), key_prefix=getattr(platform, "tos_key_prefix", ""),
                       provider=info.get("tts_provider", ""), voice=info.get("tts_voice", ""))


def voice_wiring(voice_info: dict[str, str] | None = None):
    """返回 ``wire_voice(platform) -> VoiceParts``，供 ``make_entrypoint`` 使用。"""

    def wire(platform: Any) -> VoiceParts:
        return VoiceParts(brain=PlatformBrain(submit=platform.chat.submit, control=platform.chat.control),
                          recorder=build_voice_recorder(platform, voice_info),
                          tts_sink=build_tts_archiver(platform, voice_info))

    return wire
