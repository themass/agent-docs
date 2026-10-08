#!/usr/bin/env python3
"""Each *-architecture folder → exactly README.md, ARCHITECTURE.md, DESIGN_THINKING_SERIES.md."""

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1]

KEEP = {"README.md", "ARCHITECTURE.md", "DESIGN_THINKING_SERIES.md"}


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def strip_doc(md: str) -> str:
    lines = md.splitlines()
    i = 0
    if lines and lines[0].startswith("#"):
        i = 1
    while i < len(lines) and lines[i].strip() != "---":
        i += 1
    if i < len(lines):
        i += 1
    return "\n".join(lines[i:]).strip()


def narrative_body(base: Path) -> str:
    n = read(base / "NARRATIVE.md")
    if not n:
        arch = read(base / "ARCHITECTURE.md")
        m = re.search(
            r"(?ms)# 第一篇 · 项目与产品说明\n(.*?)# 第三篇 · 端到端",
            arch,
        )
        return m.group(1).strip() if m else ""
    lines = n.splitlines()
    out = []
    i = 0
    if lines and lines[0].startswith("# Part I"):
        i = 1
    while i < len(lines) and (lines[i].startswith(">") or lines[i].strip() in ("", "---")):
        i += 1
    if i < len(lines) and lines[i].strip() == "---":
        i += 1
    out = lines[i:]
    text = "\n".join(out)
    text = text.replace("[MODULE_CATALOG.md](./MODULE_CATALOG.md)", "monorepo 源码树")
    text = text.replace("[MODULE_TURN_LOOP_DEEP.md](./MODULE_TURN_LOOP_DEEP.md) · ARCHITECTURE Part II §3", "下文第四篇")
    text = text.replace("完整目录树：[MODULE_CATALOG.md](./MODULE_CATALOG.md)。", "源码在 monorepo 对应目录下按第二篇角色理解即可，不必背路径表。")
    return text.strip()


CODWHALE_DEEP = r"""
# 第四篇 · 实现深潜（叙述版）

> 本篇用 **行为与因果** 讲实现，不以目录树代替设计。源码根：`Codewhale/crates/`。

## 4.1 `run_turn`：一个用户回合为何常含多次模型调用

用户在作曲框里只按了一次回车，但引擎里可能发生 **多轮**「模型 → 工具 → 再模型」。`Engine::run_turn`（`tui/src/core/engine/turn_loop.rs`，入口约 L896）拥有整段生命周期的墙钟预算、工具调用计数、以及 steer 队列的边界语义。

进入 `run_turn` 后，引擎先做三件「整 turn 一次」的事：启动 `TurnWallClock`；对 `ToolActivationCache` 做 `revalidate`，把已断开 MCP 或策略变更后失效的延迟工具名剔掉；初始化 `ToolCallBudget`，避免单轮工具风暴。然后进入主循环：流式读模型输出（`process_stream`），把 assistant 文本、thinking、以及逐步完整的 tool_use 收进 `StreamOutcome`。一条 assistant 消息收齐后，`plan_tool_calls` 决定本批执行什么——来源可能是模型直接的 `ToolCallSource::Model`，也可能是 CodeMode 里程序发起的嵌套调用；两类路径必须走 **同一套** `resolve_tool_permission`，否则会出现「模型不能写盘但嵌套脚本能写」的洞。

执行阶段（`execute_planned_tools`）不是简单的 `spawn`：pre shell hook 可能直接 deny；sandbox 在 OS 层再包一层；写文件类工具可能触发 side-git snapshot 以便 `/restore`；post hook 与 receipts 决定模型看见的 observation 长什么样。`process_tool_results` 之后，若 LSP 有排队诊断，会在 **下一次请求之前** 合成 user 消息——这是产品上的关键细节：诊断是 **会话历史的一部分**，但不是 **KV 冻结前缀的一部分**，否则前缀每改一次文件就失效，成本与正确性都会崩。

终止 turn 的原因分散在多处分支：模型正常 end_turn 且无待执行 tool；工具预算耗尽（有时还有一次「final report」避免子任务静默失败）；用户取消；连续空 REPL 块；goal continuation 用尽。读代码时不要只找 `return`，要连同 `TurnOutcomeStatus` 回传给 `Engine` 状态机的路径一起看。

**Steer** 值得单独理解：用户在模型还在流式输出时插入新指令，不会立刻撕裂当前 tool JSON，而是进入 `pending_steers`，在 **消息边界** 提交或标记 Dropped。这是交互式终端与无头 exec 能共用同一 loop 的前提之一。

## 4.2 Session：什么算「模型见过的真相」

`session.rs` 里的 Session 不是「SQLite 里所有行的缓存」，而是 **本轮 loop 拼请求时信任的热路径视图**。messages 列表必须与日后审计、resume、以及 `prepare_primary_turn_request` 的 Append 段一致。任何「只存在于 UI、没入账」的展示层状态，都不能成为下一轮 prompt 的唯一来源。

`ToolActivationCache` 解决的是工具面爆炸：除永久路由（read/write/edit/bash/agent/tool_search）外，大量 MCP 工具以延迟 schema 存在，通过 `tool_search` 激活，且 **每会话** 有 8 个名字与 16KB schema 的上限。换会话或 `Op::SyncSession` 必须 `clear()`——否则旧权限姿态下激活的工具会在新会话里「复活」，这是真实 bug 类，不是文档洁癖。

`PrefixStabilityManager` 与 `prompt_zones` 一起服务 CACHE 策略：system 与工具目录应尽量钉在 FrozenPrefix；波动事实（失败用例名、一次性 stderr）只能作为 append 的 user/tool 结果进入历史。新人常犯的错误是把「当前测试名」写进 system prompt「方便模型」——这在 Codewhale 模型里属于 **破坏前缀稳定性**。

## 4.3 权限链：Plan 模式不是第二个 Agent

`/mode plan` 在用户感知上是「先想再干」，在实现上是 **tool_policy 拒绝副作用**：写盘、危险 shell 在 `plan_tool_calls` 与 `resolve_tool_permission` 层被拒，而不是另起一个只读模型。切到 `/mode work` 时 **同一条 Session 历史** 继续，避免 plan/work 各维护一套 transcript。

`execpolicy` crate 提供规则层：BuiltinDefault、Agent、User 规则叠代；`denied_prefixes` 硬拒；Ask 与 Auto-Review 与 Full Access 是 **姿态**，不是绕过 sandbox。Auto-Review Guardian 可在自动放行前再拦一刀。沙箱（Seatbelt、bwrap 等）在执行层包装——即使模型被 Full Access，仍可能因 policy 或 sandbox 拒绝。

## 4.4 子 Agent、Fleet、Runtime：身份与执行分离

Fleet 解决「哪个配置、谁有资格、lane 上挂什么任务」；Runtime worker 解决「在无 UI 的环境里跑同一个 `run_turn`」。`agent` 工具是模型侧启动子任务的门面；产品要求子 worker 的终态、重试、收据与 durable 路径 **同形**，父 UI 只见摘要与计数，不把每个子 transcript 灌回父上下文——否则多 Agent 在 token 与认知上不可扩展。

协调面在 `tools/subagent/coord.rs`（list/message/followup/interrupt/wait/coordinate），与上游 `AGENT_RUNTIME.md` 一起读，才能理解「子 Agent」在 Codewhale 里不是第二个弱生命周期进程花样。

## 4.5 Memory、Compaction、KV：三个不同问题

长对话压缩（`compaction/`）解决 **上下文长度**；Purge 解决 **Agent 主动删改历史** 的可审计需求；`memory` crate + `remember` 解决 **结构化事实库**（带 provenance）。KV-cache 文档解决 **前缀稳定降成本**。把三者做成一个「记忆开关」会在产品和代码里同时迷路。

## 4.6 修失败测试：把上文落到一条故事线

假设 `tests/test_app.py` 失败。用户在 TUI 或 `codewhale exec` 里说：「修失败测试并解释改了什么。」

引擎开 turn，写 checkpoint（发模型前可恢复点），用 FrozenPrefix 固定 BASE_PROMPT 与工具目录，把用户句 append 进历史，流式请求模型。模型返回 `bash pytest`；execpolicy 在 Ask 下可能停住等人点批准，Full Access 下直接进 sandbox 执行。失败栈作为 tool observation **入账**。第二轮请求里模型看见完整栈（不是钉在 system 里的一次性事实），于是发出 `edit`；执行后 LSP 可能追加 diagnostic 合成 user 块。再跑 pytest，通过后模型写自然语言总结。turn 结束清 checkpoint，可选 snapshot 文件状态。

TUI 与 exec 的差别仅在 **呈现与审批交互**；若你以为 exec「更简单」而在 exec 路径上绕开 permission，就会破坏「同一内核」不变量。

---

# 第五篇 · 设计检查清单

1. 新能力是否只需要改 `turn_loop` 一处，而不是在 core 起新 loop？  
2. 新上下文是 FrozenPrefix 还是 Append-only？  
3. 新工具是否走 catalog + permission + 可选延迟激活？  
4. 子 Agent 行为是否与 Runtime 文档同形？  
5. 改权限/沙箱是否同时有 execpolicy 与 hook 测试锚点？

**延伸阅读**：仓库内 `Codewhale/docs/`（ARCHITECTURE、AGENT_RUNTIME、MODES、CACHE）· 体例参照 [pi-agent/ARCHITECTURE.md](../pi-agent/ARCHITECTURE.md)。
"""

HARNESS_DEEP = r"""
# 第四篇 · 实现深潜

## 4.1 `event_loop_cycle` 才是唯一心脏

Harness 再厚的默认装配，也不会在 `strands_harness/` 里出现第二个 `while`。一次用户 `agent("…")` 可能触发 **多个 cycle**：每个 cycle 先检查 limits 与 checkpoint 恢复语义，再决定是调用模型还是跳过模型直接续执行未完成的 tool，然后在 `stop_reason == tool_use` 时执行工具并 `recurse_event_loop`。

`invocation_state` 里的 `request_state` 跨 cycle 保留；这与「每条 message 立刻落盘」的 Session 钩子并行存在——读代码时要分清 **单次 invocation 内的控制状态** 与 **跨 invocation 的 session 文件**。

## 4.2 `create_harness` 解决的是集成痛苦，不是循环语义

默认模型、编码工具、SnapshotSessionManager（`./.agent/sessions`）、Memory 注入、ContextOffloader、subagent 工厂、工具名碰撞检测——这些都是 **降低集成方决策成本**。若你要改「模型调用几次才停」，去 `event_loop.py`；若你要改「默认有没有 memory 工具」，去 `strands_harness/agent.py`。

## 4.3 Session 与 Memory 为何分开

Session 保存 transcript 快照；Memory 是跨会话检索库（默认 `./.agent/memory`），turn 前 injection 把检索结果并进上下文。短脚本跑完就退出时，应 `shutdown()` 等待 memory 抽取协调器落盘，否则你以为「没记住」其实是进程先退了。

## 4.4 Interventions 与 Sandbox

Interventions 在工具执行前短路为人审或策略；Sandbox 包装执行环境。Harness 会去掉与 sandbox 重复的内置工具名。不要把「ask」同时实现在应用层和 Strands 层两套互不感知的逻辑。

## 4.5 多 Agent

Swarm/Graph 编排多个 `Agent.__call__`；harness subagent 用同一 `create_harness` 工厂在后台跑。编排层 **不替代** event loop。

**参照**：[pi-agent](../pi-agent/ARCHITECTURE.md) 的 `runLoop` 章节对照阅读。
"""

SOLPI_DEEP = r"""
# 第四篇 · 四机制实现要点（叙述）

## 4.1 Action Fusion

在 Pi 的 edit/write 上增加 `then_run`：一次 tool 调用里先完成文件突变再跑验证命令，减少「请再执行 pytest」的 LLM 回合。失败语义：编辑失败则不跑命令；命令非零仍保留编辑——避免 silent rollback 误导用户。

## 4.2 ObservationPack

JSONL 真源不变；仅在 `context` 事件返回更短的 `messages` 给 Provider。大输出前几次全文，之后 placeholder + `obs_recall` 分页。切勿把 Evidence Reducer 收据再 Pack。

## 4.3 Evidence-Preserving Reducer

`tool_result` 钩子里：诊断类输出可走第二模型压缩，但 **quote 校验** 失败则退回 Pi 原文。journal 留审计链。

## 4.4 Online Context Compact

`update_plan` 标记 completed 步 → 经济性判断 → **调用 Pi 原生 compaction**，不自写摘要 LLM。压后注入 plan reminder。

**Pi 心脏**：[pi-agent/ARCHITECTURE.md](../pi-agent/ARCHITECTURE.md) §5、§14。
"""

UA_DEEP = r"""
# 第四篇 · 图引擎与流水线

## 4.1 为何是图而不是文件夹树

仓库结构回答「文件在哪」；KnowledgeGraph 回答「谁调用谁、属于哪层、改一处会波及谁」。边类型（imports/calls/extends…）支撑 tour 与 diff 冲击分析。`schema.ts` 的 validate/sanitize/autoFix 是多 Agent 产物的 **合并契约**。

## 4.2 脚本与模型的分工

`scan-project.mjs` 等脚本产出确定性清单与结构；file-analyzer 子 Agent 补语义 summary 与补边。让模型在 Skill 里手写 `find .` 会破坏可复现性与增量 fingerprint。

## 4.3 持久化与 Dashboard

校验失败不写坏图；路径消毒防泄漏 home。Dashboard **只读** 已落盘图，不在浏览器里重跑分析——分析与阅读解耦。

## 4.4 宿主 Loop

`/understand` 的 ReAct 在 Claude Code/Cursor 等宿主里；UA 提供 Skill 编排与 `packages/core` 库，不竞争宿主 loop。
"""

README_TEMPLATE = """# {title} — 文档

> 本项目文档 **仅三份**：**本 README** · **[ARCHITECTURE.md](./ARCHITECTURE.md)**（唯一技术主文档）· **[DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md)**（图解导读）

## 怎么读

1. **10 分钟**：DESIGN_THINKING_SERIES（九幕）  
2. **30–60 分钟**：ARCHITECTURE 第一篇～第三篇（项目说明 + 原理 + 场景）  
3. **改代码**：ARCHITECTURE 第四篇实现深潜  

## 交叉索引

- [四项目对照](../FOUR_PROJECT_ARCHITECTURE_INDEX.md)  
- [pi-agent 体例](../pi-agent/ARCHITECTURE.md)  
"""


def build_arch(base: Path, title: str, deep: str) -> str:
    narr = narrative_body(base)
    p2 = strip_doc(read(base / "ARCHITECTURE_PART2.md"))
    # 第三篇：把 PART2 包一层说明
    third = f"""
---

# 第三篇 · 端到端场景与数据流

> 用具体任务串起第二篇的概念；时序图可与第二篇对照阅读。

{p2}
"""

    toc = """
## 目录

- [第一篇 · 项目与产品](#第一篇--项目与产品说明)
- [第二篇 · 架构与原理](#第二篇--架构与原理)
- [第三篇 · 端到端场景](#第三篇--端到端场景与数据流)
- [第四篇 · 实现深潜](#第四篇--实现深潜叙述版)
- [第五篇 · 检查清单](#第五篇--设计检查清单)（Codewhale 含；其他项目见第四篇末）

---

# 第一篇 · 项目与产品说明

"""

    # Rename narrative sections: I.x -> fits under 第一篇 - keep ## I. headers as subsections
    header = f"""# {title} — 架构设计文档

> **唯一主文档**（体例对标 [pi-agent/ARCHITECTURE.md](../pi-agent/ARCHITECTURE.md)）。  
> 图解导读：[DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md)  
> **最后更新**：2026-09-29（三文件合并版）

{toc}

{narr}

{third}

{deep}
"""
    if "第五篇" not in deep and "检查清单" not in deep:
        header += "\n---\n\n# 第五篇 · 设计检查清单\n\n见第四篇末与第一篇不变量小节。\n"
    return header.strip() + "\n"


PROJECTS = [
    ("codewhale-architecture", "Codewhale", CODWHALE_DEEP),
    ("harness-sdk-architecture", "Strands Harness SDK（Python）", HARNESS_DEEP),
    ("sol-pi-architecture", "SoL-Pi", SOLPI_DEEP),
    ("understand-anything-architecture", "Understand-Anything", UA_DEEP),
]


def main() -> None:
    for folder, title, deep in PROJECTS:
        base = DOCS / folder
        arch = build_arch(base, title, deep)
        (base / "ARCHITECTURE.md").write_text(arch, encoding="utf-8")
        readme = README_TEMPLATE.format(title=title.split("（")[0].strip())
        (base / "README.md").write_text(readme, encoding="utf-8")
        for f in base.iterdir():
            if f.is_file() and f.suffix == ".md" and f.name not in KEEP:
                f.unlink()
                print(f"removed {f.relative_to(DOCS)}")
        print(f"{folder}: ARCHITECTURE {len(arch.splitlines())} lines, files={len(list(base.glob('*.md')))}")


if __name__ == "__main__":
    main()
