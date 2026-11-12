"""质检总开关：关闭后语音侧的记录与 TTS 采集不装配；配置默认开启。"""

from types import SimpleNamespace

from companion.bootstrap.voice_wiring import build_tts_archiver, build_voice_recorder, voice_wiring
from companion.config import Settings


def platform(**kw):
    base = dict(qa=object(), compliance=object(), objects=None, tos_key_prefix="", qa_enabled=True,
                chat=SimpleNamespace(submit=object(), control=object()))
    base.update(kw)
    return SimpleNamespace(**base)


def test_the_setting_defaults_to_on_and_can_be_turned_off_by_env(monkeypatch):
    monkeypatch.delenv("COMPANION_QA_ENABLED", raising=False)
    assert Settings(_env_file=None).companion_qa_enabled is True
    monkeypatch.setenv("COMPANION_QA_ENABLED", "false")
    assert Settings(_env_file=None).companion_qa_enabled is False


def test_with_the_switch_on_both_voice_hooks_are_built():
    assert build_voice_recorder(platform()) is not None
    assert build_tts_archiver(platform()) is not None


def test_with_the_switch_off_neither_voice_hook_is_built():
    off = platform(qa_enabled=False)
    assert build_voice_recorder(off) is None and build_tts_archiver(off) is None


def test_voice_parts_keep_the_brain_when_recording_is_off():
    parts = voice_wiring()(platform(qa_enabled=False))
    assert parts.brain is not None and parts.recorder is None and parts.tts_sink is None
