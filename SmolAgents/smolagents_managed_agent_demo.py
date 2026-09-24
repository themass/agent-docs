#!/usr/bin/env python3
"""Minimal demo: SmolAgents「子代理 = 可调用的工具」机制（无需真实 API Key）。

运行（在仓库根目录）::

    uv run python examples/smolagents_managed_agent_demo.py

说明要点:
1. 子代理仍是 MultiStepAgent，初始化时被写上与普通 Tool 相同的 ``inputs`` / ``output_type``，
   便于 ``get_tool_json_schema`` 发给 LLM。
2. 父代理 ``ToolCallingAgent`` 把 ``tools`` 与 ``managed_agents`` 合并进 ``tools_to_call_from``。
3. 模型返回的 tool call 名若等于子代理的 ``name``，``execute_tool_call`` 会执行
   ``子代理(**arguments)``，即 ``MultiStepAgent.__call__(task=..., additional_args=...)``：
   先用 ``managed_agent`` 模板包一层任务再 ``run()``；返回值再经 ``report`` 模板包成字符串写进 observation。
"""

from __future__ import annotations

import json
import textwrap

from smolagents import ToolCallingAgent
from smolagents.models import (
    ChatMessage,
    ChatMessageToolCall,
    ChatMessageToolCallFunction,
    MessageRole,
    Model,
    get_tool_json_schema,
)


def _print_title(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def demo_schema_only() -> None:
    """Part A: 子代理在 API 里长什么样（OpenAI tools 里的 function schema）。"""
    _print_title("Part A — 子代理对外暴露的 JSON Schema（与 Tool 同源）")

    child = ToolCallingAgent(
        tools=[],
        model=Model(),  # 占位，本段不调用 generate
        name="mini",
        description="A tiny sub-agent that only answers with final_answer.",
        max_steps=2,
    )
    # inputs / output_type 由**父代理**在 _setup_managed_agents 里改写到子代理上；
    # 单独 new 子代理时没有这一步，这里用父代理挂载一次以与真实行为一致。
    ToolCallingAgent(tools=[], model=Model(), managed_agents=[child], max_steps=2)
    print("子代理 mini 的 inputs（父代理 init 时 _setup_managed_agents 写入）:")
    print(json.dumps(child.inputs, indent=2, ensure_ascii=False))
    schema = get_tool_json_schema(child)
    print("\n发给大模型的 function 定义（get_tool_json_schema）:")
    print(json.dumps(schema, indent=2, ensure_ascii=False))


class ChildScriptedModel(Model):
    """子代理用的假模型：第一步就直接 final_answer。"""

    def __init__(self) -> None:
        super().__init__(model_id="scripted-child")
        self.call_count = 0

    def generate(
        self,
        messages: list[ChatMessage],
        stop_sequences: list[str] | None = None,
        tools_to_call_from: list | None = None,
        **kwargs: object,
    ) -> ChatMessage:
        self.call_count += 1
        print(f"\n>>> [子代理 LLM] generate() 第 {self.call_count} 次")
        print(f"    当前可选工具名: {[getattr(t, 'name', '?') for t in (tools_to_call_from or [])]}")
        print("    最近几条消息（子代理自己的对话）:")
        for i, m in enumerate(messages[-4:]):
            preview = str(m.content)[:280].replace("\n", " ")
            print(f"      [{i}] role={m.role.value!r} content={preview!r}...")

        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content=None,
            tool_calls=[
                ChatMessageToolCall(
                    id="child_fc_1",
                    type="function",
                    function=ChatMessageToolCallFunction(
                        name="final_answer",
                        arguments={"answer": "BANANA"},
                    ),
                )
            ],
            token_usage=None,
        )


class ParentScriptedModel(Model):
    """父代理用的假模型：第 1 步调用子代理 mini；第 2 步 final_answer。"""

    def __init__(self) -> None:
        super().__init__(model_id="scripted-parent")
        self.call_count = 0

    def generate(
        self,
        messages: list[ChatMessage],
        stop_sequences: list[str] | None = None,
        tools_to_call_from: list | None = None,
        **kwargs: object,
    ) -> ChatMessage:
        self.call_count += 1
        print(f"\n>>> [父代理 LLM] generate() 第 {self.call_count} 次")
        names = [getattr(t, "name", "?") for t in (tools_to_call_from or [])]
        print(f"    当前可选工具名: {names}")

        if self.call_count == 1:
            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content="先把任务交给 mini。",
                tool_calls=[
                    ChatMessageToolCall(
                        id="parent_fc_1",
                        type="function",
                        function=ChatMessageToolCallFunction(
                            name="mini",
                            arguments={
                                "task": "用一句话说明你最喜欢的水果单词。",
                                "additional_args": {"hint": "只要一个英文单词"},
                            },
                        ),
                    )
                ],
                token_usage=None,
            )

        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content=None,
            tool_calls=[
                ChatMessageToolCall(
                    id="parent_fc_2",
                    type="function",
                    function=ChatMessageToolCallFunction(
                        name="final_answer",
                        arguments={"answer": "父代理已收到子代理报告，任务结束。"},
                    ),
                )
            ],
            token_usage=None,
        )


def demo_full_parent_child() -> None:
    """Part B: 父 ToolCallingAgent 调用子 ToolCallingAgent 的完整链路。"""
    _print_title("Part B — 父代理 → tool call(mini) → 子代理 __call__ → run → 返回值 → 父 observation")

    child_model = ChildScriptedModel()
    child = ToolCallingAgent(
        tools=[],
        model=child_model,
        name="mini",
        description="子代理：收到 task 后内部再跑自己的小 ReAct，然后给出最终答案。",
        max_steps=3,
    )

    parent_model = ParentScriptedModel()
    parent = ToolCallingAgent(
        tools=[],
        model=parent_model,
        managed_agents=[child],
        max_steps=5,
    )

    print(
        textwrap.dedent("""
        执行 parent.run("根任务说明…") 时:
        - 父 LLM 第 1 次返回: tool_calls name=mini, arguments={task, additional_args}
        - execute_tool_call → mini(**arguments) → MultiStepAgent.__call__
          → populate_template(managed_agent.task) 包任务 → child.run(full_task, additional_args=...)
        - 子代理 run 内部: 子 LLM 返回 final_answer → 子 run 结束
        - __call__ 再用 populate_template(managed_agent.report) 把子输出包成字符串返回给父
        - 父 memory 里出现 Observation；父 LLM 第 2 次再决定 final_answer
        """)
    )

    out = parent.run("请协调子代理完成水果单词任务。")
    print("\n--- parent.run 最终返回值 ---")
    print(repr(out))


def main() -> None:
    demo_schema_only()
    demo_full_parent_child()


if __name__ == "__main__":
    main()
