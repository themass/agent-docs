"""首轮招呼的 ``max_tokens`` 上限：这套提示词里唯一的确定性防线。

背景：用户对角色说 hello，得到一整篇「Core mission / Rules」的自述。提示词层改了三轮
（人设分层、约束移到末尾、文案重写），但那都是概率性的——283 张卡 × 长尾模型总会有漏网。
真正能保证「一句 hello 换不回八百字」的只有输出长度上限。

这里的断言分两半：
- **该压的压下去**：首轮 + 纯招呼 → ``model_settings["max_tokens"]`` 被设成上限；
- **不该动的绝不碰**：任何可能截断一份正常回答的情形（非首轮、正常提问、带图、
  已经在工具链里）都必须原样放行。误伤比话多是更严重的问题。
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from companion.agent.brain.graph_middleware import (
    FIRST_GREETING_MAX_TOKENS,
    PromptMiddleware,
    is_bare_greeting,
)


class _Request:
    """最小的 ModelRequest 替身：只保留中间件读到和写到的字段。"""

    def __init__(self, messages, *, model_settings=None, runtime=None):
        self.messages = list(messages)
        self.system_message = None
        self.model_settings = dict(model_settings or {})
        self.runtime = runtime

    def override(self, **kw):
        out = _Request(self.messages, model_settings=self.model_settings, runtime=self.runtime)
        out.system_message = kw.get("system_message", self.system_message)
        out.messages = list(kw.get("messages", self.messages))
        out.model_settings = dict(kw.get("model_settings", self.model_settings))
        return out


async def _run(request):
    """跑一遍中间件，返回交给 handler 的那个 request。"""
    seen = []

    async def handler(req):
        seen.append(req)
        return "ok"

    await PromptMiddleware().awrap_model_call(request, handler)
    return seen[0]


def _caps(request) -> int | None:
    return request.model_settings.get("max_tokens")


# --- 判定：什么算「一句招呼」 -----------------------------------------------------

@pytest.mark.parametrize("text", ["你好", "你好！", "您好呀", "嗨", "在吗", "在吗？", "早上好",
                                  "hello", "Hi!", "hey~", "How are you?", "hola", "こんにちは",
                                  "안녕하세요", "你好🙂", "  hello  "])
def test_bare_greetings_are_recognised(text):
    assert is_bare_greeting(text), f"{text!r} 应该算一句招呼"


@pytest.mark.parametrize("text", [
    "你好，帮我写一个 Python 脚本",
    "hello 你能做什么",
    "在吗？我有个问题想问",
    "今天天气怎么样",
    "讲个笑话",
    "", "   ",
    "hello " * 10,          # 超长
    "hey buddy what's up",  # 不是纯招呼
])
def test_real_questions_are_never_mistaken_for_greetings(text):
    assert not is_bare_greeting(text), f"{text!r} 不是纯招呼，压掉长度会截断正常回答"


# --- 该压的压下去 ---------------------------------------------------------------

async def test_first_turn_greeting_gets_the_cap():
    out = await _run(_Request([HumanMessage(content="你好")]))
    assert _caps(out) == FIRST_GREETING_MAX_TOKENS


async def test_the_cap_is_far_below_the_default_so_it_actually_bites():
    """不写死 4096——路由表一改这个断言就没意义了；只要求它明显小于常规上限。"""
    assert FIRST_GREETING_MAX_TOKENS < 1000


async def test_voice_channel_injections_do_not_mask_the_greeting():
    """语音通道在深度 0 注入 cue 片段（以用户消息形式落在最后）。判定必须看注入前的消息，
    否则「最后一条用户消息」永远是那段协议文本，招呼永远判不出来。"""
    plan = type("Plan", (), {
        "system": "系统提示词",
        "injections": [type("Inj", (), {"depth": 0, "role": "user", "text": "输出 cue JSON",
                                        "order": 0})()],
    })()
    runtime = type("Runtime", (), {"context": {"prompt_plan": plan}})()
    request = _Request([HumanMessage(content="你好")], runtime=runtime)
    out = await _run(request)
    assert _caps(out) == FIRST_GREETING_MAX_TOKENS
    # 注入本身仍然生效
    assert any("cue JSON" in str(getattr(m, "content", "")) for m in out.messages)


# --- 不该动的绝不碰 -------------------------------------------------------------

async def test_a_normal_question_on_the_first_turn_is_untouched():
    out = await _run(_Request([HumanMessage(content="帮我对比一下 Kafka 和 Pulsar 的取舍")]))
    assert _caps(out) is None


async def test_a_greeting_mid_conversation_is_untouched():
    """会话里已经有助手消息 → 不再动手。后来的「在吗」由上下文长度感自己拿捏。"""
    out = await _run(_Request([
        HumanMessage(content="你好"),
        AIMessage(content="嗨，今天想聊点什么？"),
        HumanMessage(content="在吗"),
    ]))
    assert _caps(out) is None


async def test_the_second_model_call_in_a_tool_turn_is_untouched():
    """工具返回后的第二次模型调用会看到本回合自己的 AI 消息，于是自动解除上限——
    否则一个「你好，帮我查下天气」的回合里，工具结果之后那句话也会被截断。"""
    out = await _run(_Request([
        HumanMessage(content="你好"),
        AIMessage(content="", tool_calls=[{"id": "c1", "name": "recall_memory", "args": {}}]),
    ]))
    assert _caps(out) is None


async def test_image_turns_are_untouched():
    out = await _run(_Request([HumanMessage(content=[
        {"type": "text", "text": "你好"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
    ])]))
    assert _caps(out) is None


async def test_a_stricter_existing_cap_is_not_relaxed():
    """调用方已经压得比我们更严时，我们的上限不该把它反手放宽。"""
    out = await _run(_Request([HumanMessage(content="你好")], model_settings={"max_tokens": 40}))
    assert _caps(out) == 40


async def test_a_looser_existing_cap_is_tightened():
    out = await _run(_Request([HumanMessage(content="你好")], model_settings={"max_tokens": 4096}))
    assert _caps(out) == FIRST_GREETING_MAX_TOKENS


async def test_other_model_settings_survive_the_override():
    out = await _run(_Request([HumanMessage(content="你好")],
                              model_settings={"max_tokens": 4096, "temperature": 0.3}))
    assert out.model_settings["temperature"] == 0.3


async def test_non_greeting_turns_keep_their_model_settings_exactly():
    out = await _run(_Request([HumanMessage(content="讲个笑话")],
                              model_settings={"max_tokens": 4096}))
    assert out.model_settings == {"max_tokens": 4096}


async def test_a_system_message_alone_never_triggers_the_cap():
    """只有系统消息、没有用户输入（不该发生，但别在这里炸）。"""
    out = await _run(_Request([SystemMessage(content="系统")]))
    assert _caps(out) is None
