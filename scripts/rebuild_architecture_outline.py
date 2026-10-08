#!/usr/bin/env python3
"""
Rebuild docs/*/ARCHITECTURE.md with pi-agent style outline:
  - Part I: I.0–I.10 (single authoritative copy, no pasted duplicates)
  - Part II: numbered module chapters + cross-refs to satellite docs

Satellite docs (GUIDE, PART1–3, MODULE_CATALOG) stay as split volumes for diff.
"""

from __future__ import annotations

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def strip_front_matter(md: str) -> str:
    """Remove leading # title and blockquote until first ---."""
    lines = md.splitlines()
    i = 0
    if lines and lines[0].startswith("#"):
        i = 1
    while i < len(lines):
        if lines[i].strip() == "---":
            i += 1
            break
        i += 1
    return "\n".join(lines[i:]).strip()


def section(md: str, heading: str, until: str | None = None) -> str:
    """Extract from ## heading (line may include title suffix) until next ##."""
    pat = rf"(?ms)^## {re.escape(heading)}[^\n]*\n(.*?)(?=^## |\Z)"
    m = re.search(pat, md)
    if not m:
        return ""
    body = m.group(1).strip()
    if until:
        pat2 = rf"(?ms)^## {re.escape(until)}[^\n]*\n"
        m2 = re.search(pat2, body)
        if m2:
            body = body[: m2.start()].strip()
    return body


def sections_range(md: str, start: str, end: str | None) -> str:
    """From ## start through content before ## end (or EOF)."""
    pat = rf"(?ms)^## {re.escape(start)}[^\n]*\n(.*)"
    m = re.search(pat, md)
    if not m:
        return ""
    rest = m.group(1)
    if end:
        pat2 = rf"(?ms)^## {re.escape(end)}[^\n]*\n"
        m2 = re.search(pat2, rest)
        if m2:
            rest = rest[: m2.start()]
    return rest.strip()


def part1_section(md: str, num: str) -> str:
    return section(md, f"§{num}")


def guide_section(md: str, cn: str) -> str:
    return section(md, cn)


def load_narrative(base: Path) -> str:
    """Part I 说明性正文（是什么 / 能做什么 / 怎么做的 / 分析）。"""
    path = base / "NARRATIVE.md"
    if not path.exists():
        return "_（缺少 NARRATIVE.md，请补充项目介绍正文。）_"
    text = read(path)
    # 去掉文首重复总标题与 blockquote（保留 ## I.x 结构）
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    if lines and lines[0].startswith("# Part I"):
        i = 1
    while i < len(lines) and (lines[i].startswith(">") or lines[i].strip() == ""):
        i += 1
    if i < len(lines) and lines[i].strip() == "---":
        i += 1
    out.extend(lines[i:])
    return "\n".join(out).strip()


def build_codewhale() -> str:
    base = DOCS / "codewhale-architecture"
    p1 = strip_front_matter(read(base / "ARCHITECTURE_PART1.md"))
    p2 = strip_front_matter(read(base / "ARCHITECTURE_PART2.md"))
    p3 = strip_front_matter(read(base / "ARCHITECTURE_PART3.md"))
    guide = strip_front_matter(read(base / "ARCHITECTURE_GUIDE.md"))
    catalog = strip_front_matter(read(base / "MODULE_CATALOG.md"))
    turn = strip_front_matter(read(base / "MODULE_TURN_LOOP_DEEP.md"))
    runtime = strip_front_matter(read(base / "RUNTIME_MODULES.md"))
    design = read(base / "DESIGN_THINKING_SERIES.md")

    design_snip = sections_range(design, "第 2 幕：状态 vs 执行", "第 3 幕")
    design_snip2 = sections_range(design, "第 3 幕：双层循环", "第 4 幕")

    narrative = load_narrative(base)

    header = """# Codewhale — 架构设计文档

> **文档版本**：`Codewhale/crates/` workspace + 源码级深潜  
> **阅读方式**：**Part I** = 项目说明与设计分析（正文见 [NARRATIVE.md](./NARRATIVE.md)）→ **Part II** = 模块深潜与示例  
> **图解导读**：[DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md)  
> **源码树**：[MODULE_CATALOG.md](./MODULE_CATALOG.md)（仅索引，非主阅读路径）  
> **体例参照**：[pi-agent/ARCHITECTURE.md](../pi-agent/ARCHITECTURE.md)  
> **最后更新**：2026-09-29

---

## 文档结构

| 部分 | 受众 | 内容 |
|------|------|------|
| **Part I** | 所有人 | **是什么、能做什么、怎么做的、为什么** — 非目录罗列 |
| **Part II** | 改实现的人 | Loop / Session / 权限 / 工具 / 端到端示例 |

---

## Part I 目录

- [I.0 总体框架](#i0-总体框架一页纸)
- [I.1 项目介绍](#i1-项目介绍是什么能做什么怎么做的)
- [I.2 运行时协作](#i2-运行时协作谁负责什么不是-crate-清单)
- [I.3 核心实体](#i3-核心实体与协作设计意图)
- [I.4 Session / Checkpoint / Thread](#i4-sessioncheckpointthread三套状态别混)
- [I.5 Agent Loop 专章](#i5-agent-loop-专章turn-内到底发生什么)
- [I.6–I.8 Memory / 权限 / 子 Agent](#i6-memory-与-compaction三套能力)
- [I.9 如何读源码](#i9-模块索引如何读源码而非文件树)
- [I.10 不变量](#i10-依赖规则与不变量写代码前自检)

## Part II 目录（源码深潜）

1. [Part I ↔ Part II 对照](#1-part-i--part-ii-对照)
2. [两层设计：状态、执行与唯一 Loop](#2-两层设计状态执行与唯一-loop)
3. [模块一：`turn_loop.rs`](#3-模块一turn_looprs--enginerun_turn)
4. [模块二：`session.rs`](#4-模块二sessionrs--会话与-toolactivationcache)
5. [模块三：权限链](#5-模块三authorityrs--execpolicy)
6. [模块四：Compaction / Memory / KV](#6-模块四compaction--memory--kv-cache)
7. [模块五：工具与 LSP](#7-模块五工具执行lsp-与-hooks)
8. [模块六：子 Agent / Fleet](#8-模块六子-agentfleet-与-runtime-api)
9. [端到端示例](#9-端到端示例修失败测试)
10. [工具十步与数据流](#10-工具执行十步与-session-数据流)
11. [源码速查](#11-源码速查表)
12. [设计模式与易错](#12-设计模式与易错清单)

---

# Part I · 高层架构

{narrative}

---

# Part II · 源码深潜

## 1. Part I ↔ Part II 对照

| Part I | Part II |
|--------|---------|
| I.5 时序 | §9 端到端示例 |
| I.6 Session | §4 `session.rs` |
| I.7 Memory / Compaction | §6 |
| I.8 权限 | §5 |
| I.9 模块索引 | §3–§8 分模块 |
| I.0 Loop 心智 | §3 `turn_loop` 深潜 |

---

## 2. 两层设计：状态、执行与唯一 Loop

{design_snip2}

{guide3}

---

## 3. 模块一：`turn_loop.rs` — `Engine::run_turn`

{turn_body}

---

## 4. 模块二：`session.rs` — 会话与 ToolActivationCache

{runtime_session}

---

## 5. 模块三：`authority.rs` + `execpolicy`

{runtime_auth}

---

## 6. 模块四：Compaction / Memory / KV-cache

{runtime_compact}

{part3_llm}

---

## 7. 模块五：工具执行、LSP 与 hooks

{part3_tools}

{runtime_lsp}

---

## 8. 模块六：子 Agent、Fleet 与 Runtime API

{part3_runtime}

---

## 9. 端到端示例：修失败测试

{p2_s1}

---

## 10. 工具执行十步与 Session 数据流

{p2_s2}

{p2_s3}

---

## 11. 源码速查表

{part5}

---

## 12. 设计模式与易错清单

{part3_tail}

**分卷延伸**：更长的模块文件表 → [MODULE_CATALOG.md](./MODULE_CATALOG.md)；九幕图解 → [DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md)。
"""

    part5 = part1_section(p1, "5")

    guide3 = guide_section(guide, "三、Agent Loop（唯一实现）")
    guide4 = guide_section(guide, "四、Session 与持久化账本")
    guide5 = guide_section(guide, "五、Memory 与 Compaction")
    guide6 = guide_section(guide, "六、权限、模式与沙箱")

    part3_mem = section(p3, "§4 Memory 与 Compaction")
    part3_perm = section(p3, "§2 权限、模式、沙箱")
    part3_tools = section(p3, "§1 工具系统")
    part3_llm = section(p3, "§3 LLM 与 Prompt")
    part3_runtime = sections_range(p3, "§5 子 Agent / Fleet / Runtime", "§7")
    part3_tail = sections_range(p3, "§8", None) or sections_range(p3, "§7", None)

    runtime_session = section(runtime, "6. `session.rs` — Session 与 ToolActivationCache")
    runtime_auth = section(runtime, "7. `authority.rs` + `execpolicy` — 权限链")
    runtime_compact = section(runtime, "8. Compaction / Memory / KV-cache")
    runtime_lsp = section(runtime, "9. 工具执行与 LSP") + "\n\n" + section(runtime, "10. 端到端逐步追踪（修测试）")

    p2_s1 = sections_range(p2, "§1 示例", "§2")
    p2_s2 = section(p2, "§2 交互 Session 数据流（上游对照）")
    p2_s3 = section(p2, "§3 工具执行十步")

    # turn: renumber headings to fit under section 3
    turn_lines = []
    for line in turn.splitlines():
        if re.match(r"^## \d+\.", line):
            line = re.sub(r"^## (\d+)\.", r"### 3.", line)
        turn_lines.append(line)
    turn_body = "\n".join(turn_lines)

    part_ii = header.split("# Part II · 源码深潜", 1)[1]
    part_ii = part_ii.format(
        design_snip2=design_snip2,
        guide3=guide3,
        turn_body=turn_body,
        runtime_session=runtime_session,
        runtime_auth=runtime_auth,
        runtime_compact=runtime_compact,
        part3_llm=part3_llm,
        part3_tools=part3_tools,
        runtime_lsp=runtime_lsp,
        part3_runtime=part3_runtime,
        p2_s1=p2_s1,
        p2_s2=p2_s2,
        p2_s3=p2_s3,
        part5=part5,
        part3_tail=part3_tail,
    )
    return header.split("# Part II · 源码深潜", 1)[0].format(narrative=narrative) + "# Part II · 源码深潜" + part_ii


def build_harness() -> str:
    base = DOCS / "harness-sdk-architecture"
    p1 = strip_front_matter(read(base / "ARCHITECTURE_PART1.md"))
    p2 = strip_front_matter(read(base / "ARCHITECTURE_PART2.md"))
    p3 = strip_front_matter(read(base / "ARCHITECTURE_PART3.md"))
    guide = strip_front_matter(read(base / "ARCHITECTURE_GUIDE.md"))
    catalog = strip_front_matter(read(base / "MODULE_CATALOG.md"))
    runtime = strip_front_matter(read(base / "RUNTIME_MODULES.md"))

    header = """# Strands Harness SDK（Python）— 架构设计文档

> **文档版本**：`harness-sdk/strands-py` + `harness-py`  
> **阅读方式**：Part I 建地图 → Part II 改 `event_loop_cycle`  
> **分卷**：[PART1–3](./ARCHITECTURE_PART1.md) · [GUIDE](./ARCHITECTURE_GUIDE.md) · [MODULE_CATALOG](./MODULE_CATALOG.md)  
> **体例参照**：[pi-agent/ARCHITECTURE.md](../pi-agent/ARCHITECTURE.md)  
> **最后更新**：2026-09-29（大纲重组）

---

## 文档结构

| 部分 | 受众 | 内容 |
|------|------|------|
| **Part I** | 架构师、集成方 | 分层、`Agent` / `event_loop` 实体、时序、Session/Memory/权限 |
| **Part II** | 改循环与装配的开发者 | `event_loop.py`、`create_harness`、插件与干预 |

---

## Part I 目录

- [I.0 总体框架](#i0-总体框架一页纸)
- [I.1 产品定位](#i1-产品定位)
- [I.2 包依赖与边界](#i2-包依赖与边界)
- [I.3 核心实体](#i3-核心实体)
- [I.4 分层协作图](#i4-分层协作图)
- [I.5 关键时序](#i5-关键时序)
- [I.6 Session 与持久化](#i6-session-与持久化)
- [I.7 Memory 与 Context](#i7-memory-与-context)
- [I.8 权限、沙箱与 Interventions](#i8-权限沙箱与-interventions)
- [I.9 模块索引](#i9-模块索引)
- [I.10 不变量](#i10-不变量)

## Part II 目录

1. [Part I ↔ Part II 对照](#1-part-i--part-ii-对照)
2. [模块一：`event_loop_cycle`](#2-模块一event_loop_cycle)
3. [模块二：`Agent.__call__` 与 invocation](#3-模块二agent__call__-与-invocation)
4. [模块三：SessionManager](#4-模块三sessionmanager)
5. [模块四：MemoryManager](#5-模块四memorymanager)
6. [模块五：ContextManager 与 Offloader](#6-模块五contextmanager-与-offloader)
7. [模块六：Interventions 与 Sandbox](#7-模块六interventions-与-sandbox)
8. [模块七：`create_harness` 装配](#8-模块七create_harness-装配)
9. [端到端示例](#9-端到端示例)
10. [多 Agent 与 subagent](#10-多-agent-与-subagent)

---

# Part I · 高层架构

## I.0 总体框架（一页纸）

Harness Python 栈：**`create_harness()` 装配默认电池** + **`strands.Agent` 门面** + **唯一循环 `event_loop_cycle`**（`strands/event_loop/event_loop.py`）。Harness crate **不写**第二套 loop。

{part0}

{part1}

---

## I.1 产品定位

可嵌入的 Strands Agent SDK：`create_harness` 提供编码向默认（模型路由、工具、session 文件、memory 注入、context offloader、subagent）。应用可只用 `strands.Agent` 自建，Harness 是「电池 included」层。

---

## I.2 包依赖与边界

{part2}

---

## I.3 核心实体

{part3}

---

## I.4 分层协作图

（见 I.0 §1 图；多 Agent 在 L4，仍调用同一 `Agent.__call__`。）

---

## I.5 关键时序

{guide_e2e}

---

## I.6 Session 与持久化

{guide_session}

---

## I.7 Memory 与 Context

{guide_memory}

{guide_context}

---

## I.8 权限、沙箱与 Interventions

{guide_perm}

---

## I.9 模块索引

摘要见 [MODULE_CATALOG.md](./MODULE_CATALOG.md)。改循环：`strands/event_loop/`；改默认装配：`strands_harness/agent.py`。

---

## I.10 不变量

1. 循环只在 `event_loop_cycle` + `recurse_event_loop`。  
2. `create_harness` 工具名碰撞检查（builtin / tools / plugins / memory）。  
3. Limits 在 **cycle 边界**检查（`turns` / tokens）。  
4. 子 Agent 通过 `build_default_subagent(create_harness, …)` 共享父配置语义。

---

# Part II · 源码深潜

## 1. Part I ↔ Part II 对照

| Part I | Part II |
|--------|---------|
| I.5 时序 | §9 |
| I.6 Session | §4 |
| I.7 Memory | §5–§6 |
| I.8 权限 | §7 |

---

## 2. 模块一：`event_loop_cycle`

{guide_loop}

{rt5}

---

## 3. 模块二：`Agent.__call__` 与 invocation

{rt6}

---

## 4. 模块三：SessionManager

{rt7}

---

## 5. 模块四：MemoryManager

{rt8}

---

## 6. 模块五：ContextManager 与 Offloader

{rt9}

---

## 7. 模块六：Interventions 与 Sandbox

{rt10}

---

## 8. 模块七：`create_harness` 装配

{rt11}

---

## 9. 端到端示例

{p2}

---

## 10. 多 Agent 与 subagent

{p3}

"""

    guide_e2e = guide_section(guide, "二、端到端：create_harness → agent()")
    guide_session = guide_section(guide, "四、Session")
    guide_memory = guide_section(guide, "五、Memory")
    guide_context = guide_section(guide, "六、Context、Compaction、Offload")
    guide_perm = guide_section(guide, "七、权限与干预（Interventions）")
    guide_loop = guide_section(guide, "三、Agent Loop（event_loop_cycle）")

    rt = runtime
    rt5 = section(rt, "5. `event_loop_cycle` — Agent Loop")
    rt6 = section(rt, "6. `Agent.__call__` — 外层 invocation")
    rt7 = section(rt, "7. `SessionManager` — 会话钩子")
    rt8 = section(rt, "8. `MemoryManager` — 跨会话记忆")
    rt9 = section(rt, "9. ContextManager 与 Offloader")
    rt10 = section(rt, "10. Interventions 与 Sandbox")
    rt11 = section(rt, "11. `create_harness` 装配表")

    narrative = load_narrative(base)
    part_ii = header.split("# Part II · 源码深潜", 1)[1].format(
        guide_e2e=guide_e2e,
        guide_session=guide_session or guide_section(guide, "四、Session 与持久化"),
        guide_memory=guide_memory,
        guide_context=guide_context,
        guide_perm=guide_perm,
        guide_loop=guide_loop,
        rt5=rt5,
        rt6=rt6,
        rt7=rt7,
        rt8=rt8,
        rt9=rt9,
        rt10=rt10,
        rt11=rt11,
        p2=p2,
        p3=p3,
    )
    meta = header.split("# Part I · 高层架构", 1)[0]
    return meta + "# Part I · 高层架构\n\n" + narrative + "\n\n---\n\n# Part II · 源码深潜" + part_ii


def build_sol_pi() -> str:
    """SoL-Pi: Part I from GUIDE + preserved I.2 block; Part II modular."""
    base = DOCS / "sol-pi-architecture"
    guide = strip_front_matter(read(base / "ARCHITECTURE_GUIDE.md"))
    p1 = strip_front_matter(read(base / "ARCHITECTURE_PART1.md"))
    runtime = strip_front_matter(read(base / "RUNTIME_MODULES.md"))
    p2 = strip_front_matter(read(base / "ARCHITECTURE_PART2.md"))
    p3 = strip_front_matter(read(base / "ARCHITECTURE_PART3.md"))

    i2_block = guide_section(guide, "二、与 Pi 的整体关系（必读）")

    header = """# SoL-Pi — 架构设计文档

> **宿主**：`pi/packages/coding-agent` · **扩展**：`SoL-Pi/src/sol-pi/`  
> **Pi 边界**：[prime-agent ARCHITECTURE_GUIDE §三](../prime-agent-architecture/ARCHITECTURE_GUIDE.md#三与-pi-的整体关系) · [pi-agent](../pi-agent/ARCHITECTURE.md)  
> **分卷**：[PART1–3](./ARCHITECTURE_PART1.md) · [GUIDE](./ARCHITECTURE_GUIDE.md)  
> **最后更新**：2026-09-29（大纲重组）

---

## 文档结构

| 部分 | 受众 | 内容 |
|------|------|------|
| **Part I** | 先搞清 Pi vs SoL-Pi | 挂接点、时序、四机制职责 |
| **Part II** | 改 `extensions/*` | 工厂、Fusion/Pack/Reducer/Compact 源码 |

---

## Part I 目录

- [I.0 总体框架](#i0-总体框架一页纸)
- [I.1 产品定位](#i1-产品定位)
- [I.2 与 Pi 的整体关系（必读）](#i2-与-pi-的整体关系对标-prime-architecture_guide-三)
- [I.3 核心实体](#i3-核心实体)
- [I.4 关键时序](#i4-关键时序端到端--四机制全开)
- [I.5 Agent Loop（Pi）](#i5-agent-loop-专章pi-心脏--sol-pi-不碰)
- [I.6 Session](#i6-session-专章双账本)
- [I.7 Memory / Compaction](#i7-memory--compaction-专章)
- [I.8 权限](#i8-权限专章)
- [I.9 模块索引](#i9-模块索引)
- [I.10 不变量](#i10-运行时不变量)

## Part II 目录

1. [Part I ↔ Part II 对照](#1-part-i--part-ii-对照)
2. [模块一：Pi `runLoop` 边界](#2-模块一pi-runloop-边界)
3. [模块二：Session 投影 vs Pack](#3-模块二session-投影-vs-pack)
4. [模块三：扩展工厂](#4-模块三扩展工厂-indexts)
5. [模块四：Action Fusion](#5-模块四action-fusion)
6. [模块五：ObservationPack](#6-模块五observationpack)
7. [模块六：Evidence-Preserving Reducer](#7-模块六evidence-preserving-reducer)
8. [模块七：Online Context Compact](#8-模块七online-context-compact)
9. [ExtensionAPI 事件索引](#9-extensionapi-事件索引)
10. [全流程示例与配置](#10-全流程示例与配置)

---

"""

    narrative = load_narrative(base)
    part_i_body = "# Part I · 高层架构\n\n" + narrative

    rt_map = [
        ("2. 模块一：Pi `runLoop` 边界", "5. Pi `runLoop` 与 SoL-Pi 边界"),
        ("3. 模块二：Session 投影 vs Pack", "6. Pi Session 投影 vs Pack"),
        ("4. 模块三：扩展工厂", "7. 扩展工厂 `index.ts`"),
        ("5. 模块四：Action Fusion", "8. Action Fusion 源码"),
        ("6. 模块五：ObservationPack", "9. ObservationPack 源码"),
        ("7. 模块六：Evidence-Preserving Reducer", "10. Evidence-Preserving Reducer 源码"),
        ("8. 模块七：Online Context Compact", "11. Online Context Compact 源码"),
    ]
    part_ii = ["# Part II · 源码深潜\n", "## 1. Part I ↔ Part II 对照\n\n| Part I | Part II |\n|--------|---------|\n| I.2 Pi 边界 | §2 |\n| I.4 时序 | §10 |\n| 四机制 | §5–§8 |\n\n---\n"]
    for title, src_heading in rt_map:
        body = section(runtime, src_heading)
        part_ii.append(f"\n## {title}\n\n{body}\n\n---\n")
    ext = section(runtime, "ExtensionAPI 事件索引")
    part_ii.append(f"\n## 9. ExtensionAPI 事件索引\n\n{ext}\n\n---\n")
    part_ii.append(f"\n## 10. 全流程示例与配置\n\n{p2}\n\n{p3}\n")

    return header + part_i_body + "\n\n---\n\n" + "".join(part_ii)


def build_ua() -> str:
    base = DOCS / "understand-anything-architecture"
    p1 = strip_front_matter(read(base / "ARCHITECTURE_PART1.md"))
    p2 = strip_front_matter(read(base / "ARCHITECTURE_PART2.md"))
    p3 = strip_front_matter(read(base / "ARCHITECTURE_PART3.md"))
    guide = strip_front_matter(read(base / "ARCHITECTURE_GUIDE.md"))
    runtime = strip_front_matter(read(base / "RUNTIME_MODULES.md"))

    header = """# Understand-Anything — 架构设计文档

> **源码**：`Understand-Anything/understand-anything-plugin/`  
> **阅读方式**：Part I 分清宿主 loop vs 插件流水线 → Part II 改 `packages/core`  
> **分卷**：[PART1–3](./ARCHITECTURE_PART1.md) · [GUIDE](./ARCHITECTURE_GUIDE.md) · [MODULE_CATALOG](./MODULE_CATALOG.md)  
> **体例参照**：[pi-agent/ARCHITECTURE.md](../pi-agent/ARCHITECTURE.md)  
> **最后更新**：2026-09-29（大纲重组）

---

## 文档结构

| 部分 | 受众 | 内容 |
|------|------|------|
| **Part I** | 产品 / 架构师 | 图模型、流水线、子 Agent 编排 |
| **Part II** | 改 core / skills 的开发者 | GraphBuilder、schema、persistence、脚本 |

---

## Part I 目录

- [I.0 总体框架](#i0-总体框架一页纸)
- [I.2 包与模块地图](#i2-包与模块地图)
- [I.3 图实体与类图](#i3-图实体与类图)
- [I.4 流水线时序](#i4-流水线时序)
- [I.5 子 Agent 编排](#i5-子-agent-编排)
- [I.6 持久化与校验](#i6-持久化与校验)
- [I.7 产品面 Skill / Dashboard](#i7-产品面-skill--dashboard)
- [I.9 模块索引](#i9-模块索引)

## Part II 目录

1. [宿主 Loop vs 插件边界](#1-宿主-loop-vs-插件边界)
2. [`packages/core` 图引擎](#2-packagescore-图引擎)
3. [扫描与抽取脚本](#3-扫描与抽取脚本)
4. [子 Agent 规格](#4-子-agent-规格)
5. [持久化与增量](#5-持久化与增量)
6. [Dashboard 与下游 Skill](#6-dashboard-与下游-skill)
7. [端到端 `/understand` 示例](#7-端到端-understand-示例)

---

# Part I · 高层架构

## I.0 总体框架（一页纸）

Understand-Anything：**ReAct loop 在宿主 IDE Agent**；本仓库提供 `/understand` 编排、`KnowledgeGraph` 落盘与 Dashboard。核心图引擎在 `packages/core`。

{part0}

{part1}

---

## I.2 包与模块地图

{part2}

---

## I.3 图实体与类图

{part3}

---

## I.4 流水线时序

{guide_pipe}

---

## I.5 子 Agent 编排

{guide_agents}

---

## I.6 持久化与校验

{rt_persist}

---

## I.7 产品面 Skill / Dashboard

{rt_dash}

---

## I.9 模块索引

完整目录：[MODULE_CATALOG.md](./MODULE_CATALOG.md)。

---

# Part II · 源码深潜

## 1. 宿主 Loop vs 插件边界

{rt5}

---

## 2. `packages/core` 图引擎

{rt6}

---

## 3. 扫描与抽取脚本

{rt7}

---

## 4. 子 Agent 规格

{rt8}

---

## 5. 持久化与增量

{rt9}

---

## 6. Dashboard 与下游 Skill

{rt10}

---

## 7. 端到端 `/understand` 示例

{p2}

{p3}

"""

    guide_pipe = guide_section(guide, "二、端到端：/understand 全流水线")
    guide_agents = guide_section(guide, "四、多 Agent 编排（非 SDK loop）")
    guide_core = guide_section(guide, "三、图引擎（core）内部")
    rt_persist = guide_section(guide, "五、持久化与增量")
    rt_dash = guide_section(guide, "六、下游 Skill（chat / diff / dashboard）")

    narrative = load_narrative(base)
    part_ii = header.split("# Part II · 源码深潜", 1)[1].format(
        guide_pipe=guide_pipe,
        guide_agents=guide_agents,
        rt_persist=rt_persist,
        rt_dash=rt_dash,
        rt5=section(runtime, "5. 宿主 Loop vs 插件边界"),
        rt6=section(runtime, "6. `packages/core` — 图引擎") + "\n\n" + guide_core,
        rt7=section(runtime, "7. 扫描与抽取脚本"),
        rt8=section(runtime, "8. 子 Agent 编排"),
        rt9=section(runtime, "9. 持久化与校验"),
        rt10=section(runtime, "10. Dashboard 与下游 Skill"),
        p2=p2,
        p3=p3,
    )
    meta = header.split("# Part I · 高层架构", 1)[0]
    return meta + "# Part I · 高层架构\n\n" + narrative + "\n\n---\n\n# Part II · 源码深潜" + part_ii


def main() -> None:
    builders = {
        "codewhale-architecture": build_codewhale,
        "harness-sdk-architecture": build_harness,
        "sol-pi-architecture": build_sol_pi,
        "understand-anything-architecture": build_ua,
    }
    for folder, fn in builders.items():
        path = DOCS / folder / "ARCHITECTURE.md"
        text = fn()
        path.write_text(text + "\n", encoding="utf-8")
        lines = len(text.splitlines())
        dup = text.count("## §0 一句话心智模型")
        print(f"{folder}: {lines} lines, duplicate §0 count={dup}")


if __name__ == "__main__":
    main()
