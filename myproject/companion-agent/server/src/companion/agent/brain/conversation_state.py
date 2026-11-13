"""对话线程状态的 DeerFlow 实现：经 LangGraph 的 ``aget_state`` / ``aupdate_state`` 改 checkpoint。

调用方必须持有会话锁（与回合互斥），这里不再加锁。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage

from companion.agent.brain.deerflow import thread_id_for

# 更新状态时以哪个节点的名义写入。消息通道的合并规则（按 id 追加、替换、删除）与节点无关；
# 指定节点只是为了让 LangGraph 不报「无法判断由谁写入」。
_AS_NODE = "model"


class DeerFlowConversationState:
    def __init__(self, graph: Any) -> None:
        self._graph = graph

    def _config(self, session_id: int) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id_for(session_id)}}

    async def _values(self, session_id: int) -> dict[str, Any]:
        snapshot = await self._graph.aget_state(self._config(session_id))
        return dict(getattr(snapshot, "values", None) or {})

    async def _update(self, session_id: int, values: dict[str, Any]) -> None:
        await self._graph.aupdate_state(self._config(session_id), values, as_node=_AS_NODE)

    async def present_ids(self, *, session_id: int) -> list[str]:
        values = await self._values(session_id)
        return [m.id for m in values.get("messages", []) if getattr(m, "id", None)]

    async def remove(self, *, session_id: int, ids: Sequence[str]) -> int:
        present = set(await self.present_ids(session_id=session_id))
        targets = [i for i in ids if i in present]
        if targets:
            await self._update(session_id, {"messages": [RemoveMessage(id=i) for i in targets]})
        return len(targets)

    async def replace_user_text(self, *, session_id: int, lc_id: str, text: str) -> bool:
        if lc_id not in set(await self.present_ids(session_id=session_id)):
            return False
        await self._update(session_id, {"messages": [HumanMessage(id=lc_id, content=text)]})
        return True

    async def append_assistant(self, *, session_id: int, lc_id: str, text: str) -> None:
        await self._update(session_id, {"messages": [AIMessage(id=lc_id, content=text)]})

    async def reset(self, *, session_id: int) -> int:
        present = await self.present_ids(session_id=session_id)
        if present:
            await self._update(session_id, {"messages": [RemoveMessage(id=i) for i in present]})
        # 摘要也要清：留着它等于把旧对话的梗概继续喂给模型
        await self._update(session_id, {"summary_text": ""})
        return len(present)

    async def summary(self, *, session_id: int) -> str:
        return str((await self._values(session_id)).get("summary_text") or "")

    async def set_summary(self, *, session_id: int, text: str) -> None:
        await self._update(session_id, {"summary_text": text})


class CheckpointThreadEraser:
    """注销用：删除会话对应的对话线程（checkpoint 与写入记录）。线程不存在时什么也不做。"""

    def __init__(self, checkpointer: Any) -> None:
        self._checkpointer = checkpointer

    async def delete_threads(self, *, session_ids: Sequence[int]) -> None:
        for sid in session_ids:
            await self._checkpointer.adelete_thread(thread_id_for(sid))
