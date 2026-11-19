"""渠道选择：语音回合走短句 + cue，文字回合不能收到 cue 指令。

这条链路之前是断的——``TurnPipeline`` 从不把消息的 kind 带到提示词构建，
语音回合一律按 ``channel="text"`` 组装，于是 ``VOICE_BREVITY_RULES`` 和
``CUE_OUTPUT_SNIPPET`` 对语音从来没生效过。这里锁住修复后的行为。
"""

from __future__ import annotations

from companion.agent.brain.port import TurnInputMessage
from companion.agent.prompt import templates as T
from companion.agent.prompt.assemble import assemble_system_prompt
from companion.agent.prompt.roleplay import build_prompt_plan
from companion.agent.prompt.role_profile import RoleProfile
from companion.service.chat.turn_runner import _channel_for


def _msg(kind: str) -> TurnInputMessage:
    return TurnInputMessage(message_id=1, text="你好", kind=kind)


def test_channel_for_maps_chat_to_text():
    assert _channel_for([_msg("chat")]) == "text"


def test_channel_for_maps_voice_to_voice():
    assert _channel_for([_msg("voice")]) == "voice"


def test_channel_for_is_voice_when_any_input_is_voice():
    assert _channel_for([_msg("chat"), _msg("voice")]) == "voice"


def test_channel_for_defaults_to_text_on_empty_inputs():
    assert _channel_for([]) == "text"


def test_text_channel_prompt_has_no_cue_instructions():
    profile = RoleProfile(role_id="r1", name="阿岚", description="一个话不多的女孩。")
    plan = build_prompt_plan(profile, channel="text")
    assert T.CUE_OUTPUT_SNIPPET not in plan.system
    assert all(T.CUE_OUTPUT_SNIPPET not in i.text for i in plan.injections)


def test_voice_channel_prompt_gets_cue_at_depth_zero():
    profile = RoleProfile(role_id="r1", name="阿岚", description="一个话不多的女孩。")
    plan = build_prompt_plan(profile, channel="voice")
    assert any(T.CUE_OUTPUT_SNIPPET in i.text and i.depth == 0 for i in plan.injections)


def test_voice_channel_uses_the_short_form_output_layer():
    profile = RoleProfile(role_id="r1", name="阿岚", description="一个话不多的女孩。")
    voice = build_prompt_plan(profile, channel="voice")
    text = build_prompt_plan(profile, channel="text")
    assert voice.system != text.system


def test_assemble_snip_only_on_voice():
    common = dict(persona="你是一个角色。", locale="zh-CN")
    assert T.CUE_OUTPUT_SNIPPET not in assemble_system_prompt(**common, channel="text").text
    assert T.CUE_OUTPUT_SNIPPET in assemble_system_prompt(**common, channel="voice").text
