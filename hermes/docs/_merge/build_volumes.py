#!/usr/bin/env python3
"""Merge Hermes docs into chapter-based volumes; preserve all mermaid/tables."""
from __future__ import annotations

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent
SOURCES = DOCS / "archive" / "legacy"
OUT = DOCS / "volumes"
# Optional dev snapshot (synced from legacy when newer root copies existed)
SOURCES_SNAPSHOT = Path(__file__).resolve().parent / "sources"

# Paths relative to SOURCES (populated by snapshot_sources())
VOLUMES: list[tuple[str, str, list[tuple[str, str]]]] = [
    (
        "01-platform-and-architecture.md",
        "卷一 · 平台与架构总览",
        [
            ("架构全景", "ARCHITECTURE.md"),
            ("Workspace 与 WebUI", "WORKSPACE_VS_WEBUI.md"),
            ("Hermes Atlas / Trending", "HERMES_ATLAS_TRENDING.md"),
        ],
    ),
    (
        "02-surface-and-presentation.md",
        "卷二 · 多 Surface 呈现与连接",
        [
            ("多 Surface 架构与流式推理", "SURFACE_ARCHITECTURE.md"),
        ],
    ),
    (
        "03-runtime-session-and-loop.md",
        "卷三 · 运行时内核与会话存储",
        [
            ("Agent Loop / AIAgent 引擎", "AGENT_LOOP_ARCHITECTURE.md"),
            ("SessionDB 与 Auxiliary 子系统", "STATE_AND_AUXILIARY.md"),
            ("执行流程考古（Historical）", "EXECUTION_FLOW_ANALYSIS.md"),
        ],
    ),
    (
        "04-prompt-and-context.md",
        "卷四 · Prompt 与上下文拼装",
        [
            ("Prompt 系统架构", "PROMPT_SYSTEM_ARCHITECTURE.md"),
            ("子 Agent 运行时 Prompt 样例", "SUBAGENT_RUNTIME_PROMPT_EXAMPLE.md"),
        ],
    ),
    (
        "05-capabilities-extensions.md",
        "卷五 · 能力扩展（Memory / Tools / Skills / MCP / Plugins）",
        [
            ("Memory 系统", "MEMORY_SYSTEM.md"),
            ("Tools 系统", "TOOLS_SYSTEM.md"),
            ("Skills 系统", "SKILLS_SYSTEM.md"),
            ("MCP 集成", "MCP_INTEGRATION.md"),
            ("Plugins 系统", "PLUGINS_SYSTEM.md"),
        ],
    ),
    (
        "06-gateways-channels-and-hitl.md",
        "卷六 · CLI、Gateway、HITL 与 Telegram",
        [
            ("CLI 与 Gateway 系统", "CLI_GATEWAY_SYSTEM.md"),
            ("HITL 审批流程", "HITL_APPROVAL_FLOW.md"),
            ("Telegram 多会话与 Topics", "TELEGRAM_MULTISSESSION_TOPICS.md"),
            ("附录 · GatewayRunner 教学走读", "GATEWAY_RUNNER_WALKTHROUGH.md"),
        ],
    ),
    (
        "07-multi-agent-and-kanban.md",
        "卷七 · 多 Agent 与 Kanban",
        [
            ("多 Agent 架构", "MULTI_AGENT_ARCHITECTURE.md"),
            ("Kanban 多 Agent 深潜", "KANBAN_MULTIAGENT_DEEP_ANALYSIS.md"),
        ],
    ),
    (
        "08-security-and-governance.md",
        "卷八 · 安全扫描与后台治理",
        [
            ("安全扫描与 Background Review", "SECURITY_SCAN_DEEP_ANALYSIS.md"),
        ],
    ),
    (
        "09-reference-history-and-versions.md",
        "卷九 · 版本、维护与参考专题",
        [
            ("版本演进", "VERSION_HISTORY.md"),
            ("文档维护基准", "DOC_MAINTENANCE.md"),
            ("LangGraph 设计原则对照", "LANGGRAPH_DESIGN_PRINCIPLES.md"),
            ("Video 项目分析", "VIDEO_PROJECTS_ANALYSIS.md"),
        ],
    ),
]

def snapshot_sources() -> None:
    """Ensure archive/legacy has EXECUTION full text; sync _merge/sources if present."""
    SOURCES.mkdir(parents=True, exist_ok=True)
    arch = DOCS / "archive" / "EXECUTION_FLOW_ANALYSIS.md"
    legacy_exec = SOURCES / "EXECUTION_FLOW_ANALYSIS.md"
    if arch.is_file():
        if not legacy_exec.exists() or legacy_exec.stat().st_size < arch.stat().st_size:
            legacy_exec.write_text(arch.read_text(encoding="utf-8"), encoding="utf-8")
    if SOURCES_SNAPSHOT.is_dir():
        for snap in SOURCES_SNAPSHOT.glob("*.md"):
            dest = SOURCES / snap.name
            if not dest.exists() or dest.stat().st_mtime < snap.stat().st_mtime:
                dest.write_text(snap.read_text(encoding="utf-8"), encoding="utf-8")

CHAPTER_ANCHOR = re.compile(r"[^a-z0-9\u4e00-\u9fff]+", re.I)


def slug(text: str, index: int) -> str:
    s = CHAPTER_ANCHOR.sub("-", text.strip().lower()).strip("-")
    return f"ch-{index:02d}-{s[:48]}" or f"ch-{index:02d}"


def strip_leading_doc_banner(text: str) -> str:
    """Remove repeated top-level # title only; keep blockquotes and body."""
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    if i < len(lines) and lines[i].startswith("# "):
        i += 1
        while i < len(lines) and (
            lines[i].strip() == ""
            or lines[i].startswith(">")
            or lines[i].strip() == "---"
        ):
            if lines[i].strip() == "---":
                i += 1
                break
            i += 1
    out.extend(lines[i:])
    return "\n".join(out).strip() + "\n"


def demote_headings(text: str, levels: int = 1) -> str:
    if levels <= 0:
        return text
    prefix = "#" * levels
    out_lines = []
    for line in text.splitlines():
        if line.startswith("#"):
            m = re.match(r"^(#+)\s", line)
            if m:
                out_lines.append(prefix + line)
            else:
                out_lines.append(line)
        else:
            out_lines.append(line)
    return "\n".join(out_lines) + "\n"


def count_mermaid(text: str) -> int:
    return text.count("```mermaid")


def count_table_rows(text: str) -> int:
    return sum(1 for ln in text.splitlines() if ln.strip().startswith("|"))


def resolve_source(name: str) -> Path:
    p = SOURCES / name
    if not p.is_file():
        raise FileNotFoundError(f"missing source snapshot: {p}")
    return p


def build_volume(filename: str, volume_title: str, chapters: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    toc: list[str] = []
    stats: list[str] = []

    parts.append(f"# {volume_title}\n")
    parts.append(
        "> **合并规则**：各章保留原文 **全部 Mermaid、表格与代码块**；"
        "仅去掉章首重复的一级标题与文首元数据分隔线。"
        "章节间叙述若重叠，以卷内靠前章节为现行描述，靠后章节仍保留独有图表。\n"
    )
    parts.append(f"> **输出文件**：`volumes/{filename}`\n")
    parts.append("\n---\n\n## 本卷目录\n\n")

    for idx, (ch_title, name) in enumerate(chapters, start=1):
        path = resolve_source(name)
        raw = path.read_text(encoding="utf-8")
        body = strip_leading_doc_banner(raw)
        body = demote_headings(body, 1)
        anchor = slug(ch_title, idx)
        mm = count_mermaid(raw)
        tr = count_table_rows(raw)
        stats.append(f"| 第 {idx} 章 | {ch_title} | `{name}` | {mm} | {tr} |")
        toc.append(
            f"- [第 {idx} 章 · {ch_title}](#{anchor})（`{name}` · mermaid×{mm} · 表格行×{tr}）"
        )

    parts.append("\n".join(toc))
    parts.append("\n\n### 图表统计（合并后应完整保留）\n\n")
    parts.append("| 章 | 标题 | 原文件 | Mermaid 块 | 表格行 |\n")
    parts.append("|----|------|--------|------------|--------|\n")
    parts.append("\n".join(stats))
    parts.append("\n\n---\n\n")

    for idx, (ch_title, name) in enumerate(chapters, start=1):
        path = resolve_source(name)
        raw = path.read_text(encoding="utf-8")
        body = strip_leading_doc_banner(raw)
        body = demote_headings(body, 1)
        anchor = slug(ch_title, idx)
        parts.append(f"## 第 {idx} 章 · {ch_title} {{#{anchor}}}\n\n")
        parts.append(f"> **原文件（归档）**：`archive/legacy/{name}`\n\n")
        if "EXECUTION_FLOW" in name or "Historical" in ch_title:
            parts.append(
                "> **去重说明**：本章为历史考古，与第 1 章 Agent Loop 部分段落重复；"
                "**下图表与代码路径仍全文保留**，勿删。\n\n"
            )
        if "Kanban" in ch_title:
            parts.append(
                "> **去重说明**：与第 1 章多 Agent 及卷六 Gateway §Kanban 有交叉；"
                "本章保留 **Kanban 状态机、API、审计** 全部图表。\n\n"
            )
        parts.append(body)
        parts.append("\n\n---\n\n")

    return "".join(parts)


def main() -> None:
    import os
    import sys
    if os.environ.get("HERMES_REBUILD_VOLUMES") != "1":
        sys.exit(
            "volumes/ 已改成手写的设计章（架构流程、核心类图、关键流程）。"
            "再跑本脚本会用归档长文覆盖它们。确认要覆盖时设置 HERMES_REBUILD_VOLUMES=1。"
        )
    snapshot_sources()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: list[str] = []
    for filename, vol_title, chapters in VOLUMES:
        content = build_volume(filename, vol_title, chapters)
        out_path = OUT / filename
        out_path.write_text(content, encoding="utf-8")
        mm = count_mermaid(content)
        tr = count_table_rows(content)
        manifest.append(f"| [{filename}](volumes/{filename}) | {vol_title} | {mm} | {tr} | {len(chapters)} |")

    (OUT / "MANIFEST.md").write_text(
        "# 合订本清单\n\n"
        "| 文件 | 卷名 | Mermaid | 表格行 | 章数 |\n"
        "|------|------|---------|--------|------|\n"
        + "\n".join(manifest)
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(VOLUMES)} volumes to {OUT}")
    for line in manifest:
        print(line)


if __name__ == "__main__":
    main()
