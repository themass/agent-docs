#!/usr/bin/env python3
"""Real-browser check of resume studio steps 3 and 4, with mocked API responses.

Why a second UI script
----------------------
`verify_ui.py` proves every screen hydrates. It never enters the resume workflow, so the
panels that carry the actual product promise -- writing options, evidence questions,
coverage audit, pre-send diagnostics and the export gate -- were only ever verified by
reading the code. Those panels share one vertical column, and the failure mode is not an
error: it is a step that silently grows too long to use.

So this script drives steps 3 and 4 against fixtures chosen to light up every conditional
branch at once (dropped highlights, a thin document, missing keywords, a warning-level
reviewer issue), asserts the user-visible copy, and records the full-page height of each
step so "this screen is too long" becomes a number instead of an opinion.

Usage (frontend must already serve a production build):
    python scripts/verify_resume_steps.py --base http://127.0.0.1:3000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from lib.bootstrap import ensure_project_env

ensure_project_env()

from playwright.async_api import async_playwright, expect  # noqa: E402

PROFILE_ID = "profile_fixture"

_EXPERIENCE = {
    "id": "exp_1",
    "company": "某互联网公司",
    "title": "后端技术专家",
    "start_date": "2020-01",
    "end_date": None,
    "highlights": [
        "主导订单服务从单体拆分为 6 个微服务，发布耗时从 40 分钟降到 6 分钟",
        "搭建统一配置中心，覆盖 120 多个服务",
        "参与大促容量保障，支撑日均 1200 万单",
    ],
}

PROFILE = {
    "id": PROFILE_ID,
    "status": "confirmed",
    "version": 4,
    "locale": "zh-CN",
    "sources": [],
    "payload": {
        "contact": {"name": "示例用户", "email": "demo@example.com"},
        "summary": "后端技术专家",
        "experiences": [_EXPERIENCE],
        "education": [],
        "skills": ["Go", "Kubernetes"],
        "projects": [],
        "preferences": {"role_family": "backend", "framing_emphases": ["ownership"]},
        "evidence_answers": [],
        "meta": {},
    },
}

WRITING_OPTIONS = {
    "role_family": "backend",
    "role_label": "后端 / 服务端研发",
    "role_family_explicit": True,
    "quantification_optional": False,
    "framing_emphases": ["ownership"],
    "framing_explicit": True,
    "max_emphases": 2,
    "families": [
        {"id": "backend", "label": "后端 / 服务端研发"},
        {"id": "pm", "label": "产品经理"},
        {"id": "legal", "label": "法务 / 合规"},
    ],
    "presets": [
        {"id": "scope", "label": "强调规模与影响面", "hint": "突出覆盖面。",
         "recommended": True},
        {"id": "ownership", "label": "强调主导与决策权", "hint": "突出你定方案。",
         "recommended": True},
        {"id": "outcome", "label": "强调结果与指标", "hint": "把成果前置。",
         "recommended": False},
        {"id": "depth", "label": "强调专业深度", "hint": "突出难点取舍。",
         "recommended": False},
        {"id": "collaboration", "label": "强调跨团队推动", "hint": "突出协同。",
         "recommended": False},
        {"id": "jd_fit", "label": "对齐目标岗位用词", "hint": "换用 JD 说法。",
         "recommended": False},
    ],
}

EVIDENCE_GAPS = {
    "role_family": "backend",
    "role_label": "后端 / 服务端研发",
    "quantification_optional": False,
    "answered_count": 0,
    "families": WRITING_OPTIONS["families"],
    "gaps": [
        {
            "field_path": "experiences[0].highlights[2]",
            "kind": "weak_ownership",
            "source_text": "参与大促容量保障，支撑日均 1200 万单",
            "question": "你在这件事里承担到什么程度？",
            "examples": ["独立负责容量模型", "牵头三个团队的压测"],
            "weight": 8,
            "answer": None,
            # Deliberately empty: this question asks for a sentence about ownership, so
            # offering metric skeletons here would ask for the wrong kind of answer.
            "metrics": [],
        },
        {
            "field_path": "experiences[0].highlights[0]",
            "kind": "missing_outcome",
            "source_text": "主导订单服务拆分",
            "question": "这件事带来的变化能用一个数字说明吗？",
            "examples": ["P99/P95 延迟", "QPS/TPS", "可用性 SLA"],
            "weight": 6,
            "answer": None,
            # Dimension + unit + a sentence with the figures left blank. A candidate
            # carrying an actual number would be us fabricating the user's history.
            "metrics": [
                {
                    "dimension": "P99 延迟",
                    "unit": "ms / s",
                    "direction": "down",
                    "skeleton": "P99 延迟从 ___ 降到 ___",
                },
                {
                    "dimension": "QPS",
                    "unit": "QPS",
                    "direction": "up",
                    "skeleton": "QPS 从 ___ 提升到 ___",
                },
            ],
        },
    ],
}

# One source highlight deliberately has no counterpart in the draft, so the coverage
# panel must name it. The draft is also short enough to trip the thin-document note.
DRAFT_SECTIONS = {
    "header": {"name": "示例用户", "headline": "后端技术专家", "contact_line": "demo@example.com"},
    "summary": "后端技术专家，主导订单链路微服务化。",
    "experience_blocks": [
        {
            "company": "某互联网公司",
            "title": "后端技术专家",
            "date_range": "2020-01 – 至今",
            "location": None,
            "scope_line": "带 8 人后端团队，负责订单与结算两条主链路",
            "bullets": [
                "主导订单服务从单体拆分为 6 个微服务，把发布耗时从 40 分钟压缩到 6 分钟",
                "参与大促容量保障，支撑日均 1200 万单的订单主链路",
            ],
        }
    ],
    "education_blocks": [],
    "skills_block": {"title": "技能", "content": "Go, Kubernetes"},
    "project_blocks": [
        {
            "name": "统一配置中心",
            "role": "技术负责人",
            "date_range": "2022",
            "description": None,
            "scope_line": "覆盖 120 多个服务的配置下发",
            "bullets": ["把配置变更导致的线上事故降到 0"],
        }
    ],
    "section_order": ["summary", "experience", "projects", "education", "skills"],
}

# The document-level pass: a section reorder with a stated reason, and a promoted
# bullet. These are exactly the changes a per-bullet diff cannot show, and the panel
# that shows them is what answers "只是逐条优化文字".
STRUCTURE = {
    "section_order": ["summary", "experience", "projects", "education", "skills"],
    "section_order_changed": False,
    "section_order_reason": None,
    "moves": [
        {
            "field_path": "experience_blocks[0].bullets[0]",
            "where": "某互联网公司 · 后端技术专家",
            "text": "主导订单服务从单体拆分为 6 个微服务，把发布耗时从 40 分钟压缩到 6 分钟",
            "from_index": 1,
            "to_index": 0,
            "reason": "带量化，分量最高",
        }
    ],
    "scope_lines": 2,
    "blocks_total": 2,
    "summary_shape": {
        "present": True,
        "positioning": True,
        "evidence": True,
        "direction": False,
        "conclusion_first": True,
    },
    "issues": [],
}

# One requirement unmet on purpose: the checklist has to name what is wrong and how to
# fix it, not just report a score.
BLUEPRINT = {
    "blueprint": {
        "family": "backend",
        "label": "后端 / 服务端研发",
        "section_order": ["summary", "experience", "projects", "education", "skills"],
        "summary_formula": [
            "你是谁（年限 + 后端 / 服务端研发定位）", "一个最硬的结果", "下一步要做什么",
        ],
        "scope_dimensions": ["团队规模", "负责的系统与链路", "量级"],
        "evidence_ladder": ["QPS / 数据量", "可用性", "耗时下降"],
        "anti_patterns": ["只写技术栈，不写这套系统支撑了多大的业务"],
        "must_haves": [],
        "lead_bullets": 4,
        "tail_bullets": 2,
        "outcome_ratio": 0.6,
        "quantification_optional": False,
    },
    "findings": [
        {
            "id": "summary_conclusion_first",
            "label": "摘要结论先行",
            "why": "招聘方读前三行决定要不要继续。",
            "fix": "按公式重写摘要。",
            "met": True,
            "detail": "已结论先行",
            "field_path": None,
        },
        {
            "id": "scope_lines",
            "label": "每段先说范围",
            "why": "后端 / 服务端研发的读者先判断量级：团队规模、负责的系统与链路、量级。",
            "fix": "在「补充信息」里写清这段经历你负责的范围与量级。",
            "met": True,
            "detail": "2/2 段有范围句",
            "field_path": None,
        },
        {
            "id": "document_depth",
            "label": "分量达标",
            "why": "面试官看的是过往做过什么。最近这段至少 4 条，少于这个数会被读成经历单薄。",
            "fix": "把源材料里本来可分的工作拆成一条一件事，再补上缺的结果。",
            "met": False,
            "detail": "最近一段 2 条（需要 4 条）",
            "field_path": "experience_blocks",
        },
    ],
    "met": 2,
    "total": 3,
}

# Conversational intake, for the profile that has no resume to upload.
INTAKE_PLAN = {
    "mode": "skeleton",
    "role_family": "backend",
    "role_label": "后端 / 服务端研发",
    "questions": [
        {
            "id": "role.0.highlight.2",
            "stage": "achievements",
            "target_path": "experiences[0].highlights[2]",
            "label": "某互联网公司 · 后端技术专家 · 第 3 条成果",
            "question": "在「某互联网公司 · 后端技术专家」，还有第三件事吗？",
            "rationale": "这是简历里真正被读的部分。先讲事实，措辞我们来处理。",
            "input_kind": "long_text",
            "examples": [],
            # Clickable sentence shapes rather than an 「例如：」 line of metric nouns. The
            # blanks are the user's to fill; a shape that arrived carrying a number would
            # be a fabricated fact they would accept and then have to defend.
            "metrics": [
                {
                    "dimension": "P99 延迟",
                    "unit": "ms",
                    "direction": "down",
                    "skeleton": "P99 延迟从 ___ 降到 ___",
                },
                {
                    "dimension": "QPS",
                    "unit": "QPS",
                    "direction": "up",
                    "skeleton": "QPS 从 ___ 提升到 ___",
                },
            ],
            "required": True,
        }
    ],
    # Already answered, so the interview can be reviewed and corrected rather than
    # being write-once.
    "answered": [
        {
            "question_id": "role.0.scope",
            "target_path": "experiences[0].scope",
            "label": "某互联网公司 · 后端技术专家 · 负责范围",
            "question": "在「某互联网公司 · 后端技术专家」，你具体负责什么、管多大的范围？",
            "answer": "带 8 人后端团队，负责订单与结算两条主链路",
        }
    ],
    "stages": [
        {"id": "identity", "label": "基本信息", "remaining": 0, "done": True},
        {"id": "current_role", "label": "最近一份工作", "remaining": 0, "done": True},
        {"id": "achievements", "label": "关键成果", "remaining": 1, "done": False},
        {"id": "history", "label": "更早的经历", "remaining": 0, "done": True},
        {"id": "direction", "label": "目标与方向", "remaining": 0, "done": True},
    ],
    "answered_count": 2,
    "can_generate": False,
    "blocking": ["经历要点太少（当前 2 条，至少需要 3 条）"],
    "version": 4,
}

COVERAGE = {
    "source_highlights": 3,
    "covered": 2,
    "draft_bullets": 2,
    "ratio": 0.67,
    "projects_missing": False,
    "dropped": [
        {
            "where": "某互联网公司",
            "text": "搭建统一配置中心，覆盖 120 多个服务",
            "origin": "experience",
            "best_match": 0.11,
        }
    ],
    "notes": [],
}

DIAGNOSTICS = {
    "estimated_pages": 0.4,
    "total_chars": 480,
    "bullet_count": 2,
    "longest_bullet_chars": 44,
    "keyword_coverage": {
        "total": 3,
        "present": 2,
        "missing": ["可观测性"],
        "skills_only": ["Kubernetes"],
    },
    "notes": ["篇幅约 0.4 页，偏薄。对照左侧待补充项把成果写进要点，比留白更能说明你做过什么。"],
}

DRAFT = {
    "id": "rdft_fixture",
    "profile_id": PROFILE_ID,
    "profile_version": 4,
    "elevation_level": "elevated",
    "locale": "zh-CN",
    "template_id": "zh-one-page",
    "sections": DRAFT_SECTIONS,
    "elevation_map": [
        {
            "field_path": "experiences[0].highlights[0]",
            "before": "负责订单服务拆分",
            "after": "主导订单服务从单体拆分为 6 个微服务，把发布耗时从 40 分钟压缩到 6 分钟",
            "techniques": ["ownership", "outcome"],
        }
    ],
    "reviewer_status": "passed",
    "created_at": "2026-10-16T02:00:00Z",
}

REVIEW = {
    "draft_id": "rdft_fixture",
    "status": "passed",
    "notes": "可以导出",
    # A warning must not block: an early build failed export on any issue at all.
    "issues": [
        {
            "severity": "warning",
            "field": "experiences[0]",
            "message": "档案里有一条要点没有出现在稿件中",
            "code": "dropped_source_content",
        },
        # The deterministic invariant audit appends findings the reviewer missed. They
        # arrive as warnings by design, so this fixture also pins that a finding from a
        # *non-model* source still renders in the advisory list and still leaves export
        # open -- a deterministic blocker here would lock users out of their own file.
        {
            "severity": "warning",
            "field": "experience_blocks[0].bullets[0]",
            "message": (
                "数字 `70%` 在档案任何位置都找不到依据。"
                "如果确实发生过，把它补进档案再重新生成。"
            ),
            "code": "invariant_unsupported_number",
        },
    ],
    "reviewed": True,
    "blocking_issue_count": 0,
    "can_export": True,
    "diagnostics": DIAGNOSTICS,
    "coverage": COVERAGE,
}


def _route_payload(url: str, method: str) -> object | None:
    """Fixture for one API path, or None to signal 'not handled'."""
    if url.endswith("/auth/context"):
        return {
            "actor": "user",
            "user": {
                "id": "fixture",
                "email": "demo@example.com",
                "email_verified": True,
                "display_name": "示例用户",
            },
            # Step 4 is capability-gated; without this the export step stays locked.
            "capabilities": ["export"],
            "active_profile_id": PROFILE_ID,
            "merge_conflict": None,
        }
    if url.endswith("/notifications"):
        return {"items": [], "unread_count": 0}
    if url.endswith("/profiles"):
        return {"profiles": [PROFILE], "active_profile_id": PROFILE_ID}
    if "/agent/sessions" in url:
        return {"sessions": []}
    if "/writing-options" in url:
        return WRITING_OPTIONS
    if "/evidence-gaps" in url:
        return EVIDENCE_GAPS
    if "/evidence-answers" in url:
        return {"profile_id": PROFILE_ID, "version": 5, "stored": 1, "role_family": "backend"}
    if "/elevate/preview" in url:
        return {
            "draft": DRAFT,
            "html": "<html><body><h1>示例用户</h1></body></html>",
            "coverage": COVERAGE,
            "diagnostics": DIAGNOSTICS,
            "structure": STRUCTURE,
            "blueprint": BLUEPRINT,
        }
    if "/intake-split" in url:
        # One dictated paragraph, broken into the points it holds. Slots are consecutive
        # from the one the question named, so no existing bullet is displaced.
        return {
            "question_id": "role.0.highlight.2",
            "split": True,
            "segments": [
                {
                    "question_id": "role.0.highlight.2",
                    "text": "我带了 4 个人把订单中心从单体拆成了 6 个服务。",
                    "target_path": "experiences[0].highlights[2]",
                    "label": "某互联网公司 · 后端技术专家 · 第 3 条成果",
                },
                {
                    "question_id": "role.0.highlight.3",
                    "text": "P99 从 800ms 降到了 120ms。",
                    "target_path": "experiences[0].highlights[3]",
                    "label": "某互联网公司 · 后端技术专家 · 第 4 条成果",
                },
            ],
        }
    if "/intake-answers" in url:
        return {
            "profile_id": PROFILE_ID,
            "version": 5,
            "stored": 1,
            "applied_paths": ["experiences[0].highlights[2]"],
            # Labels and stored text, not just paths: the point of surfacing a profile
            # write is that the user can check it.
            "applied": [
                {
                    "path": "experiences[0].highlights[2]",
                    "label": "某互联网公司 · 后端技术专家 · 第 3 条成果",
                    "value": "牵头灰度发布机制，把配置变更事故降到 0",
                }
            ],
            "plan": INTAKE_PLAN,
        }
    if "/intake" in url:
        return INTAKE_PLAN
    if "/export/review" in url:
        return REVIEW
    if "/resume-tracks" in url:
        return {
            "source_locale": "zh-CN",
            "tracks": {
                "zh-CN": {"status": "ready"},
                "en-US": {"status": "missing"},
                "zh-en": {"status": "blocked"},
            },
        }
    if "/campaign/profiles/" in url:
        return {
            "profile_id": PROFILE_ID,
            "phase": "warmup",
            "progress": {},
            "warmup_job_ids": [],
            "target_job_ids": [],
            "fit_calibration": {"sample_size": 0, "bands": {}},
        }
    if f"/profiles/{PROFILE_ID}" in url and "/jobs/" not in url and "/coach/" not in url:
        return PROFILE
    return []


async def _column_overflow(page) -> dict[str, int]:
    """How far the studio column scrolls past its own viewport.

    `document.body.scrollHeight` is useless here: the studio scrolls inside a flex
    container, so the body is always exactly the viewport height. The number that
    matters is the inner scroller's content height versus its visible height --
    that is the "how much is hidden below the fold" the user was complaining about.
    """
    return await page.evaluate(
        """() => {
            const els = Array.from(document.querySelectorAll('.scroll-area'));
            const el = els
                .map((e) => ({ e, over: e.scrollHeight - e.clientHeight }))
                .sort((a, b) => b.over - a.over)[0];
            if (!el) return { content: 0, visible: 0, hidden: 0 };
            return {
                content: el.e.scrollHeight,
                visible: el.e.clientHeight,
                hidden: Math.max(el.e.scrollHeight - el.e.clientHeight, 0),
            };
        }"""
    )

_COLUMN_PROBE = """() => {
    const tabs = Array.from(document.querySelectorAll('button'))
        .find((b) => b.textContent.trim() === 'HTML 预览');
    const inner = document.querySelector('.studio-columns-inner');
    const doc = document.querySelector('.studio-doc');
    const rail = document.querySelector('.studio-rail');
    if (!tabs || !inner || !doc || !rail) return null;
    const scrolls = (e) => e.scrollHeight > e.clientHeight + 4;
    // Every ancestor above the grid: in two-column mode none of them may be the
    // scroller, or one gesture moves both columns again.
    const ancestorScrollers = [];
    let n = inner.parentElement;
    while (n && n !== document.documentElement) {
        const cs = getComputedStyle(n);
        if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && scrolls(n)) {
            ancestorScrollers.push((n.className || '').toString().slice(0, 60));
        }
        n = n.parentElement;
    }
    const sb = doc.getBoundingClientRect();
    const tb = tabs.getBoundingClientRect();
    return {
        columns: getComputedStyle(inner).display === 'grid',
        docWidth: Math.round(sb.width),
        docScrolls: scrolls(doc),
        railScrolls: scrolls(rail),
        innerScrolls: scrolls(inner),
        ancestorScrollers,
        // With independent columns the tabs sit at the top of their own column, which is
        // the number that now means "reachable".
        offset: Math.round(tb.top - sb.top + doc.scrollTop),
        docFirst: sb.top <= rail.getBoundingClientRect().top,
        railHeight: Math.round(rail.getBoundingClientRect().height),
        docHeight: Math.round(sb.height),
    };
}"""


async def _measure_columns(page) -> dict:
    """The step 3 column structure, with every scroller reset first.

    Earlier assertions scroll elements into view, so the reset has to cover *every*
    `.scroll-area`: the step shell, the grid and the two columns are nested, and a
    leftover scroll position on any of them lands in the offset.
    """
    await page.evaluate(
        "() => document.querySelectorAll('.scroll-area')"
        ".forEach((e) => { e.scrollTop = 0; })"
    )
    layout = await page.evaluate(_COLUMN_PROBE)
    assert layout, "could not locate the step 3 columns"
    return layout


def _assert_columns(layout: dict) -> None:
    """Does each column own its own scrollbar?

    The earlier arrangement made the document `position: sticky` inside the step's single
    scroller. Measured, that was an 818px document and a 2724px rail sharing one 860px
    scroller: a single scrollbar moved both columns, and scrolling to the bottom of the
    rail pushed the resume out of its own column entirely. Sticky could not prevent it --
    a sticky element only holds while its containing block is in view, and the containing
    block was the whole 2724px grid.

    So this is structural rather than a distance. A pixel offset passed for the broken
    layout too, which is how it survived a previous round.
    """
    assert layout["offset"] >= 0, (
        f"layout measurement is broken: offset came back {layout['offset']}px, "
        "which cannot happen for a reset scroller"
    )
    assert layout["docWidth"] >= 600, (
        f"the document column is only {layout['docWidth']}px wide; an A4 preview "
        "is not legible below ~600px"
    )
    if layout["columns"]:
        # Bounded to the same height, so neither column can push the other off screen
        # however long its content gets.
        assert abs(layout["railHeight"] - layout["docHeight"]) <= 2, (
            f"the columns are {layout['railHeight']}px and {layout['docHeight']}px tall; "
            "one is sizing to its content and will scroll an ancestor instead of itself"
        )
        assert not layout["ancestorScrollers"], (
            "an ancestor of the two columns is scrolling, so one gesture moves both of "
            f"them: {layout['ancestorScrollers']}"
        )
        assert not layout["innerScrolls"], (
            "the column grid itself is scrolling rather than its children"
        )
        # The rail holds the taller content, so it is the one that must scroll. The
        # document only scrolls when the resume is longer than the pane, which depends on
        # the fixture, so it is not asserted.
        assert layout["railScrolls"], (
            "the rail does not scroll, so its lower panels are unreachable"
        )
        assert layout["offset"] < 120, (
            f"the preview tabs sit {layout['offset']}px into their own column"
        )
    else:
        # Stacked: one scrollbar is correct -- two stacked vertically would be a trap --
        # and the document must come first, or the panels are back on top of it and the
        # original complaint returns.
        assert layout["docFirst"], (
            "stacked on a narrow pane, the document must render above the control "
            "panels, not below them"
        )
        assert layout["offset"] < 400, (
            f"the document starts {layout['offset']}px into the step while stacked"
        )


_RAIL_TYPE_PROBE = """() => {
  const rail = document.querySelector('.studio-rail');
  if (!rail) return null;
  const sizes = {};
  const outliers = [];
  rail.querySelectorAll('p, li, span, label, button, textarea, input').forEach((el) => {
    if (!(el.textContent || '').trim() && el.tagName !== 'TEXTAREA'
        && el.tagName !== 'INPUT') return;
    const px = Math.round(parseFloat(getComputedStyle(el).fontSize) * 100) / 100;
    sizes[px] = (sizes[px] || 0) + 1;
    if (px > 13.6) {
      outliers.push({
        px,
        cls: (el.className || '').toString().slice(0, 60),
        text: (el.textContent || '').trim().slice(0, 30),
      });
    }
  });
  // Same class, two sizes, means something upstream is resolving to `inherit`.
  const perClass = {};
  rail.querySelectorAll('.badge, .label-meta, .text-micro').forEach((el) => {
    const key = el.classList.contains('badge') ? 'badge'
      : el.classList.contains('label-meta') ? 'label-meta' : 'text-micro';
    const px = Math.round(parseFloat(getComputedStyle(el).fontSize) * 100) / 100;
    (perClass[key] = perClass[key] || []).push(px);
  });
  const inconsistent = Object.entries(perClass)
    .map(([k, v]) => [k, Array.from(new Set(v)).sort()])
    .filter(([, v]) => v.length > 1);
  return { sizes, outliers, inconsistent, steps: Object.keys(sizes).map(Number).sort() };
}"""


def _assert_rail_type(type_scale: dict) -> None:
    """Is every line in the rail on a size somebody chose?

    This exists because of a failure mode that is invisible in the stylesheet source.
    `.badge` and `.label-meta` are built with `@apply text-micro`, and Tailwind resolves
    `@apply` by cloning every rule that mentions the applied class into the applying one.
    A rule written as `.studio-rail .text-micro { font-size: inherit }` was therefore
    re-emitted by the compiler as `.studio-rail .badge { font-size: inherit }`. Measured,
    the same badge component rendered at 16px inside a `div` and 12.5px inside an `li` --
    its size came from its wrapper rather than from the type scale.

    `tsc` does not look at CSS and the source file reads as correct, so the only place
    this is visible is the computed style in a browser. Hence a measurement, not a review.
    """
    assert type_scale, "could not locate the rail to measure its type"
    assert not type_scale["outliers"], (
        "rail text is rendering above the 13.5px ceiling, which means it is inheriting "
        f"a size rather than taking one from the scale: {type_scale['outliers']}"
    )
    assert not type_scale["inconsistent"], (
        "one component class is rendering at more than one size depending on what wraps "
        f"it, so its font-size is resolving to `inherit`: {type_scale['inconsistent']}"
    )
    # Three deliberate steps: micro (badges/counters), prose, typed text. A fourth is
    # not automatically wrong, but it is not something to acquire by accident.
    assert len(type_scale["steps"]) <= 3, (
        f"the rail is using {len(type_scale['steps'])} type sizes "
        f"({type_scale['steps']}); the density rule defines three"
    )


async def verify(base: str, output: Path) -> int:
    errors: list[str] = []
    seen: list[dict[str, object]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=2,
                service_workers="block",
            )

            async def route_api(route):
                req = route.request
                seen.append({"path": req.url.split("/api/v1")[-1], "method": req.method})
                payload = _route_payload(req.url, req.method)
                if "/elevate/preview/stream" in req.url or "/export/review/stream" in req.url:
                    await route.fulfill(content_type="text/event-stream", body=(
                        f"data: {json.dumps({'type': 'result', 'data': payload}, ensure_ascii=False)}\n\n"
                    ))
                else:
                    await route.fulfill(json=payload)

            await context.route("**/api/v1/**", route_api)

            async def block_external(route):
                if "/health/" in route.request.url:
                    await route.fulfill(
                        json={
                            "llm_enabled": True,
                            "llm_api_key_set": True,
                            "llm_vision_api_key_set": True,
                            "routing_path": "fixture",
                        }
                    )
                elif route.request.url.startswith(base):
                    await route.fallback()
                else:
                    await route.abort()

            await context.route("**/*", block_external)
            page = await context.new_page()
            page.on("pageerror", lambda e: errors.append(f"{e}\n{e.stack}"))

            output.mkdir(parents=True, exist_ok=True)
            await page.goto(base + "/resume-agent")
            await page.wait_for_load_state("networkidle")
            assert not errors, errors

            # --- step 1: conversational intake ----------------------------------------
            # The review step has to offer a way forward for a profile a file upload
            # cannot fix: no resume, or one too stale to be worth uploading. The panel
            # must say what is still blocking generation, by stage, and the write it
            # performs must be named rather than silent.
            await expect(page.get_by_role("heading", name="把这份档案填实")).to_be_visible()
            await expect(
                page.get_by_text("经历要点太少（当前 2 条，至少需要 3 条）", exact=False)
            ).to_be_visible()
            await page.get_by_role("button", name="把这份档案填实").click()
            await expect(page.get_by_text("还有第三件事吗", exact=False).first).to_be_visible()

            # A metric shape must be clickable, land in the textarea, and arrive with the
            # blank selected. A row of metric nouns left the user to invent the sentence
            # and guess the unit, which is the work they came here to have done. The
            # caret placement is the part that silently regresses: on a controlled
            # textarea it has to happen after React commits, so it is asserted rather
            # than assumed.
            answer_box = page.get_by_label(
                "在「某互联网公司 · 后端技术专家」，还有第三件事吗？"
            )
            await page.get_by_role("button", name="QPS", exact=False).first.click()
            await expect(answer_box).to_have_value("QPS 从 ___ 提升到 ___")
            selection = await answer_box.evaluate(
                "el => [el.selectionStart, el.selectionEnd, el.value.slice("
                "el.selectionStart, el.selectionEnd)]"
            )
            assert selection[2] == "___", (
                f"clicking a shape must select its blank, got {selection!r}"
            )
            # No shape may arrive carrying a value.
            assert "800" not in await answer_box.input_value()

            # A dictated answer holding several achievements must be splittable. Before
            # this the whole paragraph became one 300-character bullet with the strongest
            # items buried inside it. The split is a preview: it names the slot each point
            # lands in, and nothing is written until the user confirms.
            await answer_box.fill(
                "我带了 4 个人把订单中心从单体拆成了 6 个服务。P99 从 800ms 降到了 120ms。"
            )
            await page.get_by_role("button", name="帮我拆开").click()
            await expect(page.get_by_text("拆成了 2 条", exact=False)).to_be_visible()
            await expect(
                page.get_by_text("某互联网公司 · 后端技术专家 · 第 4 条成果").first
            ).to_be_visible()
            # Each segment is editable, because where a boundary falls is the user's call.
            second = page.get_by_label("某互联网公司 · 后端技术专家 · 第 4 条成果")
            await expect(second).to_have_value("P99 从 800ms 降到了 120ms。")
            await expect(page.get_by_role("button", name="保存这 2 条")).to_be_enabled()
            # Backing out must leave the original answer intact, not clear the box.
            await page.get_by_role("button", name="还是当一条").click()
            assert "P99 从 800ms" in await answer_box.input_value(), (
                "cancelling a split must not discard what the user wrote"
            )

            await answer_box.fill("牵头灰度发布机制，把配置变更事故降到 0")
            # The question must say where the answer lands in words the user knows, not
            # as a dotted path.
            await expect(
                page.get_by_text("写入：某互联网公司 · 后端技术专家 · 第 3 条成果").first
            ).to_be_visible()
            assert await page.get_by_text("experiences[0].highlights[2]").count() == 0, (
                "a dotted profile path leaked into the intake UI"
            )

            await page.get_by_role("button", name="保存 1 条回答").click()
            # The confirmation has to be checkable: the field in the user's words *and*
            # the text we stored. A path alone tells them nothing about what we recorded.
            await expect(page.get_by_text("已写入档案 1 处", exact=False)).to_be_visible()
            await expect(
                page.get_by_text("某互联网公司 · 后端技术专家 · 第 3 条成果").first
            ).to_be_visible()
            await expect(
                page.get_by_text("牵头灰度发布机制，把配置变更事故降到 0").first
            ).to_be_visible()

            # An answered question must remain reachable and editable. Losing it is what
            # made the interview one-way: the user could see a write had happened and had
            # no way to read it back or fix a typo.
            await page.get_by_role("button", name="已回答的 1 条，可以回看或修改").click()
            await expect(
                page.get_by_text("带 8 人后端团队，负责订单与结算两条主链路").first
            ).to_be_visible()
            # exact=True: the toolbar's 「退回修改」 also contains 「修改」, and matching it
            # here would navigate out of the step instead of opening the editor.
            await page.get_by_role("button", name="修改", exact=True).click()
            revise = page.get_by_label(
                "修改回答：在「某互联网公司 · 后端技术专家」，你具体负责什么、管多大的范围？"
            )
            await expect(revise).to_be_visible()
            # Unchanged text must not be submittable: a no-op write would bump the
            # profile version and claim something happened.
            save_revision = page.get_by_role("button", name="保存修改")
            assert await save_revision.is_disabled(), (
                "an unchanged answer must not be saveable"
            )
            await revise.fill("带 12 人后端团队，负责订单、结算、履约三条主链路")
            assert not await save_revision.is_disabled()
            await page.get_by_role("button", name="取消").click()

            await page.get_by_role("button", name="把这份档案填实").click()

            # --- step 3 ---------------------------------------------------------------
            await page.get_by_role("button", name="优化预览").first.click()
            await page.wait_for_load_state("networkidle")

            # Writing options start collapsed: step 3 already carries three panels, and
            # the resolved setting is one line of information, not a form.
            await expect(page.get_by_role("heading", name="按什么角度包装")).to_be_visible()
            await expect(page.get_by_text("后端 / 服务端研发").first).to_be_visible()
            await expect(page.get_by_text("强调主导与决策权").first).to_be_visible()

            # Evidence questions are collapsed by default; the count must still say what
            # is waiting so opening it is an informed choice.
            await expect(page.get_by_text("有 2 条要点缺少可写的成果", exact=False)).to_be_visible()
            await page.get_by_role("button", name="回答 2 个问题").click()
            # .first: the question also appears as the textarea's sr-only label.
            await expect(
                page.get_by_text("你在这件事里承担到什么程度？").first
            ).to_be_visible()

            # Metric candidates: "给出一些选项或者示例可以让用户直接选择". A row of metric
            # nouns left the user in front of an empty box still having to invent the
            # sentence; a chip inserts the sentence with the figures left blank.
            metric_chip = page.get_by_role("button", name="P99 延迟", exact=False)
            await expect(metric_chip.first).to_be_visible()
            answer_box = page.get_by_label("这件事带来的变化能用一个数字说明吗？")
            await metric_chip.first.click()
            filled = await answer_box.input_value()
            # The shape is ours, the numbers are the user's. A chip that arrived with a
            # plausible figure already in it would be us fabricating their history --
            # accepted because it looks right, and theirs to defend in the interview.
            assert "___" in filled, f"the skeleton lost its blanks: {filled!r}"
            assert not any(ch.isdigit() for ch in filled.replace("P99", "")), (
                f"a metric chip pre-filled a value: {filled!r}"
            )
            # The caret has to land on the blank, or finding it is the work the chip was
            # supposed to remove.
            selection = await answer_box.evaluate(
                "(el) => el.value.slice(el.selectionStart, el.selectionEnd)"
            )
            assert selection == "___", f"the caret did not select the blank: {selection!r}"

            # A question asking for a sentence must not offer metric skeletons: it would
            # tell the user we want a number when we want a description of ownership.
            assert await page.get_by_role("button", name="QPS", exact=False).count() == 1, (
                "metric chips leaked onto a question whose answer is not a figure"
            )

            # Focusing a question scrolls the document column to that bullet. The two
            # columns hold different content and cannot be made to line up, so this link
            # is what the side-by-side layout actually promises.
            await answer_box.focus()
            await page.wait_for_timeout(400)
            focused_bullet = await page.evaluate(
                """() => {
                    const el = document.querySelector(
                        '.studio-doc [data-path="experiences[0].highlights[0]"]'
                    );
                    if (!el) return null;
                    const col = document.querySelector('.studio-doc');
                    const eb = el.getBoundingClientRect();
                    const cb = col.getBoundingClientRect();
                    return {
                        inView: eb.bottom > cb.top && eb.top < cb.bottom,
                        highlighted: el.className.includes('bg-brand-50'),
                    };
                }"""
            )
            assert focused_bullet, "the focused bullet is not in the document column"
            assert focused_bullet["inView"], (
                "focusing a question did not bring its bullet into the document column"
            )
            assert focused_bullet["highlighted"], (
                "the bullet scrolled into view with nothing marking which one it is"
            )

            await page.get_by_role("button", name="收起").first.click()

            # The dropped content must be named in the user's terms. The old wording led
            # with 「档案里有 3 条经历要点，这份稿只写进了 2 条」 -- our bookkeeping, which
            # tells the user a number and no action -- and cut each quotation at a fixed
            # character count, mid-word.
            await expect(page.get_by_text("有 1 段经历没写进这份简历")).to_be_visible()
            await expect(page.get_by_text("搭建统一配置中心", exact=False).first).to_be_visible()
            # Both branches of the decision, because dropping a duplicate is legitimate
            # and a user who cannot tell the two apart regenerates forever.
            await expect(page.get_by_text("同一件事", exact=False).first).to_be_visible()
            assert await page.get_by_text("条经历要点，这份稿只写进了", exact=False).count() == 0, (
                "the coverage notice is still leading with internal counts"
            )
            await expect(page.get_by_text("估算篇幅约", exact=False)).to_be_visible()
            await expect(page.get_by_text("偏薄", exact=False).first).to_be_visible()

            # The document-level checklist: the answer to "不同岗位有不同的方法论" and to
            # "只是逐条优化文字". Collapsed it must still state the score and that the
            # document was restructured; expanded it must name the unmet requirement and
            # the fix, plus the section order and the promoted bullet.
            await expect(
                page.get_by_role("heading", name="按「后端 / 服务端研发」的简历标准检查")
            ).to_be_visible()
            await expect(page.get_by_text("2/3 达标")).to_be_visible()
            await expect(page.get_by_text("还差 1 项：分量达标", exact=False)).to_be_visible()
            await expect(
                page.get_by_text("把 1 条最有分量的要点提到了段首", exact=False)
            ).to_be_visible()

            await page.get_by_role("button", name="按「后端 / 服务端研发」的简历标准检查").click()
            await expect(page.get_by_text("团队规模、负责的系统与链路、量级")).to_be_visible()
            await expect(page.get_by_text("QPS / 数据量 > 可用性 > 耗时下降")).to_be_visible()
            await expect(
                page.get_by_text("最近一段 2 条（需要 4 条）", exact=False)
            ).to_be_visible()
            await expect(page.get_by_text("怎么改：", exact=False).first).to_be_visible()
            await expect(page.get_by_text("范围句覆盖：2/2 段", exact=False)).to_be_visible()
            # The blueprint's fix routes into the panel that supplies the material, and
            # that panel is not the one holding the button.
            await page.get_by_role("button", name="去补充证据").click()
            await expect(
                page.get_by_text("你在这件事里承担到什么程度？").first
            ).to_be_visible()
            await page.get_by_role("button", name="按「后端 / 服务端研发」的简历标准检查").click()

            # The 先总后分 layer has to be visible in the structured view, and projects
            # have to render at all -- the preview used to drop them entirely, so a
            # promoted project section was invisible here while present in the export.
            await expect(
                page.get_by_text("带 8 人后端团队，负责订单与结算两条主链路")
            ).to_be_visible()
            await expect(page.get_by_role("heading", name="项目经历")).to_be_visible()
            await expect(page.get_by_text("覆盖 120 多个服务的配置下发")).to_be_visible()

            # Does each column own its own scrollbar?
            #
            # The earlier arrangement made the document `position: sticky` inside the
            # step's single scroller. Measured, that was an 818px document and a 2724px
            # rail sharing one 860px scroller: a single scrollbar moved both columns, and
            # scrolling to the bottom of the rail pushed the resume out of its own column
            # entirely. Sticky could not prevent it -- a sticky element only holds while
            # its containing block is in view, and the containing block was the whole
            # 2724px grid.
            #
            # So the assertion is structural rather than a distance: in two-column mode
            # the columns scroll and no ancestor does. A pixel offset would have passed
            # for the broken layout too, which is how it survived a previous round.
            layout = await _measure_columns(page)
            _assert_columns(layout)

            # Measured, not reviewed: see `_assert_rail_type`.
            _assert_rail_type(await page.evaluate(_RAIL_TYPE_PROBE))

            # Both column modes, in one pass.
            #
            # At 1440x900 the studio pane is 930px -- below the 60rem container-query
            # threshold -- so a single run only ever exercised the stacked branch, and the
            # two-column rules this step exists for went unasserted. The threshold is on
            # the *container*, so the only way to reach the other branch is to widen the
            # window.
            await page.set_viewport_size({"width": 1760, "height": 1000})
            await page.wait_for_timeout(400)
            wide_layout = await _measure_columns(page)
            assert wide_layout["columns"], (
                "a 1760px window still did not produce two columns; the container query "
                "threshold or the pane split has changed"
            )
            _assert_columns(wide_layout)
            # The two-column branch is where the rail is narrow and the density rule
            # matters, so it gets measured in both modes.
            _assert_rail_type(await page.evaluate(_RAIL_TYPE_PROBE))
            await page.set_viewport_size({"width": 1440, "height": 900})
            await page.wait_for_timeout(300)

            chrome_px = layout["offset"]

            # The toolbar shortcut and the in-page hand-off must not share a label.
            assert await page.get_by_role("button", name="下一步：导出").count() == 1
            assert await page.get_by_role("button", name="内容定稿，去导出").count() == 1

            collapsed = await _column_overflow(page)
            await page.screenshot(path=str(output / "step3-collapsed.png"), full_page=True)

            await page.get_by_role("button", name="调整").first.click()
            await expect(page.get_by_text("对齐目标岗位用词")).to_be_visible()
            expanded = await _column_overflow(page)
            await page.screenshot(path=str(output / "step3-expanded.png"), full_page=True)

            # The role-family picker must exist exactly once. It used to be duplicated in
            # the evidence panel, where two controls wrote the same field.
            pickers = await page.get_by_label("按哪类岗位评判").count()
            assert pickers == 1, f"expected one role-family picker, found {pickers}"

            await page.get_by_role("button", name="收起").first.click()

            # --- step 4 ---------------------------------------------------------------
            # Use the real hand-off button rather than the progress rail: this is the
            # path a user takes, and step 4 unlocks only once a draft exists. The
            # toolbar shortcut is labelled differently on purpose, so this resolves to
            # exactly one element -- two identically named buttons reads as a bug.
            await page.get_by_role("button", name="内容定稿，去导出").click()
            await page.wait_for_load_state("networkidle")
            await expect(page.get_by_role("heading", name="投递前体检")).to_be_visible()
            await expect(page.get_by_role("heading", name="经历覆盖度")).to_be_visible()
            await expect(page.get_by_role("heading", name="导出前质检")).to_be_visible()
            # A warning-level issue must leave export open.
            await expect(page.get_by_text("质检通过，可以导出")).to_be_visible()
            # Both warning sources land in the same advisory list, reviewer and
            # deterministic audit alike, and neither is presented as a blocker.
            await expect(page.get_by_text("建议优化（2）· 不影响导出")).to_be_visible()
            await expect(
                page.get_by_text("在档案任何位置都找不到依据", exact=False).first
            ).to_be_visible()
            assert await page.get_by_text("建议先确认（", exact=False).count() == 0, (
                "a warning-level invariant finding must not render as a blocking error"
            )
            # The whole point of step 4 is handing over the file. Reaching it with a
            # clean review and finding the buttons disabled is the defect this asserts
            # against; `verify_export_gate.py` covers the failing and unavailable cases.
            assert await page.get_by_role("button", name="生成 PDF").is_enabled(), (
                "a passed review left the download disabled"
            )
            export_m = await _column_overflow(page)
            await page.screenshot(path=str(output / "step4.png"), full_page=True)

            assert not errors, errors

            # Answering a question must not carry a role family: that write path was
            # removed so an inferred guess cannot be frozen into an explicit choice.
            answer_calls = [r for r in seen if r["path"].endswith("/evidence-answers")]
            report = {
                "status": "passed",
                "scope": "real Chromium + built frontend; mocked API",
                "column_scroll": {
                    "step3_collapsed": collapsed,
                    "step3_expanded": expanded,
                    "step4": export_m,
                },
                "preview_offset_px": chrome_px,
                "step3_layout": layout,
                "evidence_answer_calls": len(answer_calls),
                "page_errors": errors,
                "requests": seen,
            }
            (output / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print("PASS: resume steps 3/4 render with no page errors")
            for name, m in (
                ("step3 collapsed", collapsed),
                ("step3 expanded", expanded),
                ("step4", export_m),
            ):
                screens = m["content"] / m["visible"] if m["visible"] else 0
                print(
                    f"  {name}: content={m['content']}px visible={m['visible']}px "
                    f"hidden={m['hidden']}px ({screens:.1f} screens)"
                )
            print(f"  preview tabs sit {chrome_px}px below the top of step 3")
            print(f"  screenshots in {output}")
            return 0
        finally:
            await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:3000")
    parser.add_argument("--output", type=Path, default=Path("/tmp/jc-steps-evidence"))
    args = parser.parse_args()
    sys.exit(asyncio.run(verify(args.base, args.output)))
