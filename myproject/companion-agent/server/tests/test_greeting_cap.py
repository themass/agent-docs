"""回复长度交给模型：服务端不再判断用户说了什么。

这里原来守的是一张问候语词表加一道 ``max_tokens`` 硬上限：首轮 + 纯招呼就压到 160 token。
那是**服务端替模型理解对话**——词表永远漏（`您好呀` 漏过），也永远会误伤，而且用户能感觉到
自己在被一张规则表接话。产品要的是「角色有自己的性格」，不是「服务端认得出招呼」。

设计改成：

1. 中间件**不再看消息内容**，也不再改 ``model_settings``；
2. 「怎么说话」写进角色层——``templates.BREVITY_RULES`` 说人设不是台词，
   卡里的 ``## Communication style`` 摘成「这个人怎么说话」挂在角色层末尾。

所以这个文件现在守两件事：中间件不判断（下面），以及说话方式真的进了提示词
（``test_role_prompt_hygiene.py`` 与 ``test_voice_sample``）。
"""

from __future__ import annotations

import inspect

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from companion.agent.brain import graph_middleware as M
from companion.agent.brain.graph_middleware import PromptMiddleware


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
    seen = []

    async def handler(req):
        seen.append(req)
        return "ok"

    await PromptMiddleware().awrap_model_call(request, handler)
    return seen[0]


# --- 服务端不再判断用户说了什么 ---------------------------------------------------

def test_the_greeting_classifier_is_gone():
    """词表是这套设计的根：只要它还在，就总有人会再拿它做点什么。"""
    assert not hasattr(M, "is_bare_greeting")
    assert not hasattr(M, "FIRST_GREETING_MAX_TOKENS")
    assert not hasattr(M, "_GREETINGS")


def test_the_middleware_does_not_read_message_text():
    """结构断言：中间件里不该再出现按消息内容分支的代码。

    把文档字符串剔掉再看——里面提到旧设计是为了说明为什么删掉它。
    """
    source = inspect.getsource(PromptMiddleware)
    if PromptMiddleware.__doc__:
        source = source.replace(PromptMiddleware.__doc__, "")
    for forbidden in ("is_bare_greeting", "max_tokens", "_last_human_text", "_is_session_opening"):
        assert forbidden not in source, f"PromptMiddleware 里还有 {forbidden!r}"


@pytest.mark.parametrize("text", ["你好", "你好！", "您好呀", "hello", "在吗？", "嗨"])
async def test_a_greeting_does_not_get_a_token_cap(text):
    out = await _run(_Request([HumanMessage(content=text)], model_settings={"max_tokens": 4096}))
    assert out.model_settings == {"max_tokens": 4096}


async def test_a_normal_question_keeps_its_settings_exactly():
    out = await _run(_Request([HumanMessage(content="帮我对比一下 Kafka 和 Pulsar 的取舍")],
                              model_settings={"max_tokens": 4096, "temperature": 0.3}))
    assert out.model_settings == {"max_tokens": 4096, "temperature": 0.3}


async def test_caller_supplied_settings_are_never_rewritten():
    """调用方给什么就是什么——包括它自己压得很低的情况。"""
    out = await _run(_Request([HumanMessage(content="你好")], model_settings={"max_tokens": 40}))
    assert out.model_settings == {"max_tokens": 40}


async def test_a_system_message_alone_does_not_break():
    out = await _run(_Request([SystemMessage(content="系统")]))
    assert out.model_settings == {}


# --- 中间件该做的还照做 -----------------------------------------------------------

async def test_the_system_prompt_is_still_installed():
    plan = type("Plan", (), {"system": "这是系统提示词", "injections": ()})()
    runtime = type("Runtime", (), {"context": {"prompt_plan": plan}})()
    out = await _run(_Request([HumanMessage(content="你好")], runtime=runtime))
    assert out.system_message.content == "这是系统提示词"


async def test_injections_still_land_in_this_request_only():
    plan = type("Plan", (), {
        "system": "系统",
        "injections": [type("Inj", (), {"depth": 0, "role": "user", "text": "输出 cue JSON",
                                        "order": 0})()],
    })()
    runtime = type("Runtime", (), {"context": {"prompt_plan": plan}})()
    request = _Request([HumanMessage(content="你好")], runtime=runtime)
    original = list(request.messages)
    out = await _run(request)
    assert any("cue JSON" in str(getattr(m, "content", "")) for m in out.messages)
    assert request.messages == original, "注入不该写回对话线程"
