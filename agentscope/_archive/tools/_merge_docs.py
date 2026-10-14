#!/usr/bin/env python3
"""Merge merged-sources into _archive/AGENTSCOPE_MERGED.md (full text, archival only)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "_archive" / "merged-sources"
OUT = ROOT / "_archive" / "AGENTSCOPE_MERGED.md"

# Order matters. Each entry: (filename under SRC_DIR, part title, anchor slug)
PARTS: list[tuple[str, str, str]] = [
    ("AgentScopev2.md", "导读与运维", "guide"),
    ("ARCHITECTURE.md", "库内核架构", "kernel"),
    ("MEMORY_SYSTEM.md", "记忆与 AgentState", "memory"),
    ("APP_ARCHITECTURE.md", "App 服务层", "app"),
    ("PIPELINE_AND_GOALS.md", "GoalPipeline", "pipeline"),
    ("WORKSPACE_AND_SANDBOX.md", "Workspace 与沙箱", "workspace"),
    ("MIDDLEWARE_CATALOG.md", "中间件目录", "middleware"),
    ("RAG_AND_KNOWLEDGE.md", "RAG 与知识库", "rag"),
    ("AGENT_AND_LTM_ANALYSIS.md", "Agent 与 LTM 分析", "ltm-analysis"),
    ("REALTIME_AGENT_ARCHITECTURE.md", "Realtime 语音", "realtime"),
    ("ARCHITECTURE_FULL.md", "实现参考与 v0.x 归档", "reference-archive"),
    ("AgentScopev2.v2-brief.md", "一页速查", "quick-ref"),
    ("RESTORE_AgentScopev2.md", "历史长文恢复说明", "restore-longform"),
    ("changelog.md", "Changelog", "changelog"),
    ("roadmap.md", "Roadmap", "roadmap"),
    ("NEWS.md", "News (EN)", "news-en"),
    ("NEWS_zh.md", "News (ZH)", "news-zh"),
]


def demote_md_headings(text: str, levels: int = 1) -> str:
    out: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^(#+)(\s+.*)$", line)
        if m and len(m.group(1)) + levels <= 6:
            line = "#" * (len(m.group(1)) + levels) + m.group(2)
        out.append(line)
    return "\n".join(out)


def strip_leading_h1(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        return "\n".join(lines[1:]).lstrip("\n")
    return text


LINK_REWRITES: list[tuple[str, str]] = [
    ("./AgentScopev2.md", "#part-guide"),
    ("./ARCHITECTURE.md", "#part-kernel"),
    ("./MEMORY_SYSTEM.md", "#part-memory"),
    ("./APP_ARCHITECTURE.md", "#part-app"),
    ("./PIPELINE_AND_GOALS.md", "#part-pipeline"),
    ("./WORKSPACE_AND_SANDBOX.md", "#part-workspace"),
    ("./MIDDLEWARE_CATALOG.md", "#part-middleware"),
    ("./RAG_AND_KNOWLEDGE.md", "#part-rag"),
    ("./AGENT_AND_LTM_ANALYSIS.md", "#part-ltm-analysis"),
    ("./REALTIME_AGENT_ARCHITECTURE.md", "#part-realtime"),
    ("./ARCHITECTURE_FULL.md", "#part-reference-archive"),
    ("./_archive/ARCHITECTURE.md", "#part-reference-archive"),
    ("./README.md", "./README.md"),
    ("./REME_ARCHITECTURE.md", "./REME_ARCHITECTURE.md"),
]


def rewrite_links(text: str) -> str:
    """Rewrite markdown link targets only (avoid mangling filenames like RESTORE_AgentScopev2.md)."""
    for old, new in LINK_REWRITES:
        bare = old.removeprefix("./")
        for prefix in (old, bare):
            text = re.sub(
                rf"\]\(({re.escape(prefix)})(#[^)]+)?\)",
                lambda m: f"]({new}{m.group(2) or ''})",
                text,
            )
            text = re.sub(
                rf"\(({re.escape(prefix)})(#[^)]+)?\)",
                lambda m: f"({new}{m.group(2) or ''})",
                text,
            )
    return text


def main() -> None:
    toc_lines = [
        "# AgentScope 架构与设计（合并版）",
        "",
        "> **源码**: `agentscope/src/agentscope/` · **生成**: `_merge_docs.py` · 专题原文已并入本文，勿再维护散落副本。",
        "> **ReMe**（独立项目）: [REME_ARCHITECTURE.md](./REME_ARCHITECTURE.md)",
        "",
        "## 目录",
        "",
    ]
    for _path, title, slug in PARTS:
        toc_lines.append(f"- [Part · {title}](#part-{slug})")

    body: list[str] = []
    for rel, title, slug in PARTS:
        src = SRC_DIR / rel
        if not src.is_file():
            raise SystemExit(f"Missing: {src}")
        raw = src.read_text(encoding="utf-8")
        raw = strip_leading_h1(raw)
        raw = demote_md_headings(raw, 1)
        raw = rewrite_links(raw)
        body.append(f"---\n\n## Part · {title} {{#part-{slug}}}\n\n")
        body.append(raw.rstrip())
        body.append("\n")

    OUT.write_text("\n".join(toc_lines) + "\n\n---\n\n" + "\n".join(body).rstrip() + "\n", encoding="utf-8")
    n = len(OUT.read_text(encoding="utf-8").splitlines())
    print(f"Wrote {OUT} ({n} lines)")


if __name__ == "__main__":
    main()
