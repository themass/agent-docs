#!/usr/bin/env python3
"""One-off reorganizer for AgentScopev2.md — run from docs/agentscope/."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "AgentScopev2.md"
DST = ROOT / "AgentScopev2.md"

JUNK_EXACT = {
    "预览",
    "查看代码",
    "生成失败，请重试",
    "豆包",
    "你的 AI 助手，助力每日工作学习",
    "表格",
}

META_LINE_PATTERNS = (
    re.compile(r"^如果你需要，我可以"),
    re.compile(r"^如果你愿意我可以"),
    re.compile(r"^你可以选择："),
)


def is_junk(line: str) -> bool:
    s = line.strip()
    if s in JUNK_EXACT:
        return True
    return any(p.match(s) for p in META_LINE_PATTERNS)


def filter_lines(chunk: list[str]) -> list[str]:
    return [ln for ln in chunk if not is_junk(ln)]


def demote_headings(chunk: list[str], levels: int = 1) -> list[str]:
    out: list[str] = []
    for line in chunk:
        m = re.match(r"^(#+)(\s+.*)$", line)
        if m and len(m.group(1)) + levels <= 6:
            line = "#" * (len(m.group(1)) + levels) + m.group(2)
        out.append(line)
    return out


def slice_lines(lines: list[str], start: int, end: int) -> list[str]:
    """1-based inclusive start and end."""
    return filter_lines(lines[start - 1 : end])


APPENDIX = """
---

## 附录 A：与 main 分支源码命名对照

正文大量以 **HarnessAgent / Session 快照 / `memory/short_term` / ChatRoom** 等表述；当前 **main** 更常见的划分如下。细节以专题文档为准。

| 正文常见表述 | main / 专题文档中的对应 |
|--------------|-------------------------|
| `memory/`、`ShortTermMemory.context_messages` | **`AgentState.context`** + `summary`（无独立 `memory/` 包）→ [MEMORY_SYSTEM.md](./MEMORY_SYSTEM.md) |
| `save_snapshot` / JSON 会话文件 | 库层应用自管 `AgentState.model_dump_json()`；生产 **Session** → `app/storage` → [APP_ARCHITECTURE.md](./APP_ARCHITECTURE.md) |
| `ChatRoom` / 通用 `Pipeline` 多 Agent 广播 | **MsgHub 已移除**；库级编排 → **`GoalPipeline`**（executor + verifier）→ [PIPELINE_AND_GOALS.md](./PIPELINE_AND_GOALS.md) |
| `AgentService` + RPC | 仍存在；多渠道 HTTP/SSE → **`agentscope.app.create_app`** |
| 仅 Harness 包装 | 单 **`Agent`** + **Middleware**（7 钩子）→ [ARCHITECTURE.md](./ARCHITECTURE.md) §4、§7 |
| 「框架无 RAG」 | ❌ 已有 **`rag.KnowledgeBase`** + `RAGMiddleware` → [RAG_AND_KNOWLEDGE.md](./RAG_AND_KNOWLEDGE.md) |
| Workspace 仅 DataBlock | 沙箱谱系 + `WorkspaceManager` → [WORKSPACE_AND_SANDBOX.md](./WORKSPACE_AND_SANDBOX.md) |

---

## 附录 B：`AgentState` 与记忆（补充正文第四～五部分）

**三分钟心智模型**（摘自 [MEMORY_SYSTEM.md](./MEMORY_SYSTEM.md)）：

```text
LLM 每次看到的输入 =
    system_prompt（固定，不进 context）
  + summary（可选，压缩后的旧历史）
  + context（当前会话完整近期对话）
  + tool schemas
```

| 机制 | 载体 | 作用 |
|------|------|------|
| 短期对话 | `AgentState.context: list[Msg]` | 用户/助手/tool 往返 |
| 中期摘要 | `AgentState.summary` | 头部旧消息经 `compress_context()` 压成固定格式后**物理删除**出 context |
| 工具结果上限 | `ContextConfig.tool_result_limit` | 防止单次 tool 撑爆 context |
| 卸载 | `Offloader`（常与 Workspace 配合） | 被删内容落盘，路径写入 summary 提醒 |
| 断点续聊 | `AgentState.model_dump_json()` | 应用或 `app/storage` 持久化 |

压缩策略：**去头（压成 summary）+ 保尾（`reserve_ratio` 近期 context）**，非传统「只滑窗丢头」。

---

## 附录 C：`GoalPipeline` 与多 Agent 编排（补充正文中的 ChatRoom 章节）

v2 **`pipeline/`** 核心是 **`GoalPipeline`**（`pipeline/_goal_pipeline.py`）：

- **Executor** 产出结构化 `_ExecutionReport`；**Verifier** 产出 `_VerificationResult`：`pass` | `fail` | `impossible`。
- `fail` 带 feedback 回到 Executor，直到 pass/impossible 或 `max_iters`。
- 实现 **`reply_stream`**，HITL 按 `reply_id` 路由；`_iters` 在实例上，resume 不重置预算。

**与 App Team 区分**：`app/_tool/` 的 `AgentCreate` / `TeamSay` 等是 **另一套** 生产编排（inbox + worker session），见 [APP_ARCHITECTURE.md](./APP_ARCHITECTURE.md) §7。

---

## 附录 D：App 服务层要点（正文第九部分「Service/Channel」延伸）

**库（`agent/`）管一轮 ReAct；App（`app/`）管谁触发、存哪、怎么推前端/飞书。** 统一收敛点：**`ChatService.run`**。

| 模块 | 职责 |
|------|------|
| `_app.py` | `create_app()` 工厂 |
| `_service/` | `ChatService`、`SessionService`、`get_toolkit` |
| `_router/` | FastAPI：chat、session **SSE**、channel、schedule… |
| `message_bus/` | 锁、wakeup 队列、事件 replay（**非**持久化真源） |
| `storage/` | Session / Team / Agent / 消息历史 |
| `channel/` | 飞书、钉钉等 + `ChannelGateway` |

触发路径要点：新消息 `ChatRunRegistry.spawn`（重复 409）；HITL resume 走 `enqueue_run_trigger` → `WakeupDispatcher`，避免与 parked run 竞态。完整时序见 [APP_ARCHITECTURE.md](./APP_ARCHITECTURE.md) §4。

---

## 附录 E：ReAct 主循环（main 分支，补充第二部分 Agent 小节）

```mermaid
flowchart TD
    START["reply / reply_stream"] --> IMPL["_reply_impl"]
    IMPL --> LOOP{"cur_iter < max_iters?"}
    LOOP -->|否| MAX["ExceedMaxIters"]
    LOOP -->|是| ACT{"_check_next_action"}
    ACT -->|reasoning| COMP["compress_context"]
    COMP --> REAS["LLM 采样"]
    REAS -->|无待执行 tool| END["ReplyEnd"]
    ACT -->|acting| TOOL["执行 tool_calls"]
    TOOL -->|ASK / External| WAIT["暂停 · 等事件"]
    TOOL -->|完成| INC["cur_iter++"]
    INC --> LOOP
```

| 未完成 tool_call | 下一步 |
|------------------|--------|
| 有可执行 (PENDING/ALLOWED) | **acting** |
| 仅等待 (ASKING/SUBMITTED) | **exit**（暂停 reply） |
| 无 | **reasoning** |

源码锚点：`agent/_agent.py` — `_reply_impl`、`_check_next_action`、`_reasoning_impl`、`_execute_tool_call`。

---

## 附录 F：整理说明与延伸阅读

- 本文由多轮对话导出合并；已删除 UI 复制残留（「预览 / 查看代码 / 生成失败」等），**未删**技术段落与代码块。
- 第一、二部分存在**视角重叠**（速览 vs 完整拆解），保留互补细节；若只需维护一套，请以 [ARCHITECTURE.md](./ARCHITECTURE.md) + 专题为准，本文件作**长文归档**。
- 后续可单独深挖的方向（原整理笔记）：`react_agent.py` 逐行；ChatRoom/GoalPipeline 源码；Workspace MCP 网关。
- 官方 API：https://doc.agentscope.io/ · GitHub：https://github.com/agentscope-ai/agentscope

"""


HEADER = """# AgentScope v2 设计整理（合并版）

> **仓库**: [agentscope-ai/agentscope](https://github.com/agentscope-ai/agentscope) · **源码根**: `src/agentscope`  
> **性质**: 多篇笔记合并的实现级设计整理；部分章节基于 Harness / Session 快照 / `memory` 子包等**历史或概念模型**命名。与 **main** 不一致处见 **附录 A**。  
> **维护用专题**（较新、较短）: [README.md](./README.md) · [ARCHITECTURE.md](./ARCHITECTURE.md) · [MEMORY_SYSTEM.md](./MEMORY_SYSTEM.md) · [APP_ARCHITECTURE.md](./APP_ARCHITECTURE.md)

---

## 阅读导航

| 部分 | 内容 |
|------|------|
| [第一部分](#第一部分架构速览与演进) | 分层速览、子系统、ReAct 时序、2.0 演进、设计原则、总览 Mermaid |
| [第二部分](#第二部分完整架构目录树与端到端流程) | 源码目录、端到端调用栈、模块设计摘要 |
| [第三部分](#第三部分分层图时序图与核心模块内部设计) | 分层/时序/依赖图，Session～编排内部设计 |
| [第四部分](#第四部分sessionmessagememory-设计与示例) | 数据结构、Workspace 沉淀、多轮示例 |
| [第五部分](#第五部分session-消息列表快照与-eventstream) | 内存消息列表、快照、DataBlock、LTM 布局 |
| [第六部分](#第六部分崩溃场景推演) | kill -9 / IO 半途 / LTM 未写完等变体 |
| [第七部分](#第七部分持久层改造json--db-append) | JSON 快照 → DB Append 事件日志 |
| [第八部分](#第八部分待拆解模块清单) | 尚未深挖的模块与推荐顺序 |
| [第九部分](#第九部分全模块源码级架构分析模块-111) | 模块 1–11 类图、时序、风险汇总 |
| [附录](#附录-a与-main-分支源码命名对照) | AgentState、GoalPipeline、App 层、ReAct 循环补充 |

---

"""


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines()

    parts_spec: list[tuple[str, list[str]]] = []

    # Part 1: overview + mermaid (skip junk 209-216, 260-270)
    p1 = slice_lines(lines, 8, 208)  # from 一、 to end of 五、
    p1_mermaid = slice_lines(lines, 217, 258)
    part1_body = demote_headings(
        ["### 一、整体分层架构（源码模块分层）"]  # placeholder; line 8 was ##
        + p1[1:]  # skip duplicate if we rebuilt title
    )
    # p1 started at line 8 "## 一、" — use slice 8-208 directly
    part1 = filter_lines(lines[7:208])
    part1 = demote_headings(part1, 1)
    parts_spec.append(
        (
            "## 第一部分：架构速览与演进",
            part1
            + ["", "### 六、Mermaid 架构图", ""]
            + demote_headings(p1_mermaid, 2),
        )
    )

    ranges = [
        ("## 第二部分：完整架构、目录树与端到端流程", 271, 681),
        ("## 第三部分：分层图、时序图与核心模块内部设计", 683, 1289),
        ("## 第四部分：Session、Message、Memory 设计与示例", 1290, 1713),
        ("## 第五部分：Session 消息列表、快照与 EventStream", 1714, 2121),
        ("## 第六部分：崩溃场景推演", 2122, 2398),
        ("## 第七部分：持久层改造（JSON → DB Append）", 2399, 2791),
        ("## 第八部分：待拆解模块清单", 2792, 2941),
        ("## 第九部分：全模块源码级架构分析（模块 1–11）", 2942, 3706),
    ]
    for title, start, end in ranges:
        chunk = slice_lines(lines, start, end)
        parts_spec.append((title, demote_headings(chunk, 1)))

    out: list[str] = [HEADER.rstrip(), ""]
    for title, body in parts_spec:
        out.append(title)
        out.append("")
        out.extend(body)
        out.append("")
        out.append("---")
        out.append("")

    out.append(APPENDIX.lstrip())

    DST.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {DST} ({len(out)} lines)")


if __name__ == "__main__":
    main()
