#!/usr/bin/env python3
"""Build single canonical AGENTSCOPE.md from topic files."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "_archive" / "merged-sources"
OUT = ROOT / "AGENTSCOPE.md"

PARTS: list[tuple[str, str, str, str]] = [
    # (filename under SRC, Part title, anchor slug, one-line role)
    ("ARCHITECTURE.md", "库内核与模块", "kernel", "定位、包结构、ReAct、Model、Tool、Permission、构造与 AgentEvent"),
    ("MEMORY_SYSTEM.md", "Session · Message · Memory", "memory", "AgentState、压缩、截断、Offloader、持久化"),
    ("MIDDLEWARE_CATALOG.md", "Middleware（Hook）", "middleware", "七钩子与库/App 中间件目录"),
    ("APP_ARCHITECTURE.md", "App · Channel · 生产运行时", "app", "ChatService、Storage、Bus、SSE、Channel、Team、Scheduler"),
    ("WORKSPACE_AND_SANDBOX.md", "Workspace 与沙箱", "workspace", "WorkspaceManager、Backend 谱系"),
    ("RAG_AND_KNOWLEDGE.md", "RAG 与知识库", "rag", "KnowledgeBase、RAGMiddleware、KB Manager"),
    ("PIPELINE_AND_GOALS.md", "GoalPipeline 编排", "pipeline", "executor + verifier"),
    ("AGENT_AND_LTM_ANALYSIS.md", "Agent 边界与长期记忆", "ltm", "子 Agent、LTM、Team 对照"),
]

LINK_MAP = [
    ("./ARCHITECTURE.md", "#part-kernel"),
    ("./MEMORY_SYSTEM.md", "#part-memory"),
    ("./APP_ARCHITECTURE.md", "#part-app"),
    ("./MIDDLEWARE_CATALOG.md", "#part-middleware"),
    ("./WORKSPACE_AND_SANDBOX.md", "#part-workspace"),
    ("./RAG_AND_KNOWLEDGE.md", "#part-rag"),
    ("./PIPELINE_AND_GOALS.md", "#part-pipeline"),
    ("./AGENT_AND_LTM_ANALYSIS.md", "#part-ltm"),
    ("./REALTIME_AGENT_ARCHITECTURE.md", "#附录-realtime"),
    ("./REME_ARCHITECTURE.md", "./REME_ARCHITECTURE.md"),
    ("./AGENTSCOPE.md", "#"),
    ("./README.md", "./README.md"),
    ("./_archive/ARCHITECTURE.md", "#附录-reference-full"),
    ("./_archive/ARCHITECTURE_FULL.md", "#附录-reference-full"),
]


def demote_md(text: str, levels: int = 1) -> str:
    out: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^(#+)(\s+.*)$", line)
        if m and len(m.group(1)) + levels <= 6:
            line = "#" * (len(m.group(1)) + levels) + m.group(2)
        out.append(line)
    return "\n".join(out)


def strip_doc_header(text: str) -> str:
    lines = text.splitlines()
    i = 0
    if lines and lines[0].startswith("# "):
        i = 1
    while i < len(lines) and (lines[i].strip() == "" or lines[i].startswith(">")):
        i += 1
    while i < len(lines) and lines[i].strip() == "---":
        i += 1
        while i < len(lines) and lines[i].strip() != "---" and lines[i].strip() != "":
            i += 1
        if i < len(lines) and lines[i].strip() == "---":
            i += 1
    return "\n".join(lines[i:]).lstrip("\n")


def rewrite_links(text: str) -> str:
    for old, new in LINK_MAP:
        bare = old.removeprefix("./")
        for prefix in (old, bare):
            text = re.sub(
                rf"\]\(({re.escape(prefix)})(#[^)]+)?\)",
                lambda m: f"]({new}{m.group(2) or ''})",
                text,
            )
    return text


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    return re.sub(r"[-\s]+", "-", s)


def main() -> None:
    lines: list[str] = [
        "# AgentScope 架构与设计（完整版）",
        "",
        "| 项 | 说明 |",
        "|----|------|",
        "| **文档类型** | 单一 canonical 设计规格（本文） |",
        "| **源码** | `agentscope/src/agentscope/` |",
        "| **版本** | AgentScope v2 `main` |",
        "| **生成** | `_build_agentscope_single.py`（改专题后请重新运行） |",
        "| **ReMe** | 独立记忆产品 → [REME_ARCHITECTURE.md](./REME_ARCHITECTURE.md) |",
        "",
        "---",
        "",
        "## 如何使用本文",
        "",
        "本文由 `_archive/merged-sources/` 专题 **合并为一**，保留原章节与算法细节。",
        "维护：改 `merged-sources/*.md` 后执行 `python3 _build_agentscope_single.py`；或只改本文（勿再跑脚本）。",
        "",
        "## 总目录",
        "",
    ]

    for _f, title, slug, role in PARTS:
        lines.append(f"- [Part · {title}（{role}）](#part-{slug})")

    lines.extend(
        [
            "- [Part · 总览（分层与数据平面）](#part-overview)",
            "- [附录 · Realtime](./REALTIME_AGENT_ARCHITECTURE.md)（分支，未并入正文）",
            "- [附录 · 实现参考全文](#附录-reference-full)",
            "",
            "---",
            "",
            "## Part · 总览 {#part-overview}",
            "",
            "### 分层",
            "",
            "| 层 | 包 | 职责 |",
            "|----|-----|------|",
            "| **库** | `agentscope/`（无 `app`） | 单 `Agent` ReAct、`AgentState`、Tool、Permission、Middleware |",
            "| **App** | `agentscope.app/` | `ChatService.run`、Storage、MessageBus、Channel、Team |",
            "| **应用** | 你的产品代码 | GoalPipeline、RAG 策略、ReMe 集成 |",
            "",
            "### 三条数据平面",
            "",
            "| 平面 | 载体 | 真源？ |",
            "|------|------|--------|",
            "| 推理 | `context` + `summary` + system | turn 内内存；turn 末写入 `SessionRecord.state` |",
            "| 持久 | Storage 消息 + state | 断点续聊、历史列表 |",
            "| 观测 | MessageBus → SSE | 仅进度；可丢 |",
            "",
            "### 本文内阅读路径",
            "",
            "| 你要设计… | 读 Part |",
            "|-----------|---------|",
            "| 整体 + Loop + 模块 | kernel |",
            "| Session / Message / Memory / 压缩 | memory |",
            "| Hook | middleware |",
            "| HITL | kernel §6 + memory §7 + app §4 |",
            "| App / Channel / SSE | app |",
            "| 沙箱 / RAG / 验收环 | workspace · rag · pipeline |",
            "",
            "---",
            "",
        ]
    )

    for fname, title, slug, role in PARTS:
        path = SRC / fname
        if not path.is_file():
            raise SystemExit(f"Missing {path}")
        body = strip_doc_header(path.read_text(encoding="utf-8"))
        body = demote_md(body, 1)
        body = rewrite_links(body)
        lines.append(f"## Part · {title} {{#part-{slug}}}")
        lines.append("")
        lines.append(f"> {role}")
        lines.append("")
        lines.append(body.rstrip())
        lines.append("")
        lines.append("---")
        lines.append("")

    ref = ROOT / "_archive" / "ARCHITECTURE_FULL.md"
    if ref.is_file():
        lines.append("## 附录 · 实现参考全文 {#附录-reference-full}")
        lines.append("")
        lines.append(
            "> 类图、v0.x 章节、路径检索。日常设计以上文 Part 为准；此处约 3150 行，仅检索用。"
        )
        lines.append("")
        lines.append(
            f"完整文件：[`_archive/ARCHITECTURE_FULL.md`](./_archive/ARCHITECTURE_FULL.md)"
        )
        lines.append("")

    OUT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    n = len(OUT.read_text(encoding="utf-8").splitlines())
    print(f"Wrote {OUT} ({n} lines)")


if __name__ == "__main__":
    main()
