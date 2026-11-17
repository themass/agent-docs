#!/usr/bin/env python3
"""Render one thumbnail per resume template, for `/resume-template`.

Why this exists
---------------
`/resume-template` is the page that answers "简历模板" — a high-volume, high-intent
query — and it cannot rank on prose alone. A template page without pictures of the
templates is a page that tells instead of shows, and search engines index what a page
demonstrates.

How it stays honest
--------------------
The images are produced by the **same renderer the product exports with**
(`ResumeRenderEngine.render_html`), from a sample profile that lives in this repo. There
is no second styling path that could drift: if a template changes, re-running this
script changes the picture. That is the property magic-resume's approach has, and the
reason to borrow the pattern rather than hand-draw mockups.

Output
------
`frontend/web/public/templates/<template-id>.png`, committed. Committed because the
deploy machine has no browser build step and no reason to run one — the images change
only when a template changes, which is a deliberate, reviewable act. Re-run and commit
whenever a template's layout changes.

Playwright is the `export` extra and is optional on a dev machine, so the script prints
what to install instead of failing with an ImportError. `--check` reports readiness
without rendering.

Usage
-----
    cd backend/server
    ../../venv/bin/python ../../scripts/render-template-previews.py --check
    ../../venv/bin/python ../../scripts/render-template-previews.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
JOB_COME_ROOT = SCRIPT_DIR.parent
SERVER_ROOT = JOB_COME_ROOT / "backend" / "server"
OUTPUT_DIR = JOB_COME_ROOT / "frontend" / "web" / "public" / "templates"

sys.path.insert(0, str(SERVER_ROOT / "src"))

#: Rendered at A4 aspect and 2x for retina displays. A thumbnail only has to show layout
#: and density, so this is deliberately smaller than a print render — the page shows
#: three of them side by side.
VIEWPORT = {"width": 794, "height": 1123}  # A4 at 96 dpi
SCALE = 2

TEMPLATES = (
    ("zh-one-page", "中文单页"),
    ("en-two-page", "英文两页"),
    ("zh-en-bilingual", "中英双语"),
)

_INSTALL_HINT = (
    "playwright is not installed — it is the `export` extra, optional on a dev machine.\n"
    f"  cd {SERVER_ROOT}\n"
    "  ./.venv/bin/pip install -e '.[export]'\n"
    "  ./.venv/bin/python -m playwright install chromium"
)


def sample_sections(locale: str) -> dict:
    """A profile that exercises every section the templates can show.

    Deliberately a *realistic senior* profile rather than lorem ipsum: the thumbnail's job
    is to show how much text fits and how the sections stack, and a one-line placeholder
    would make every template look equally empty. All facts here are fictional and live
    only in this script — nothing is ever written to a user's account.
    """
    if locale == "en":
        return {
            "header": {
                "name": "Alex Chen",
                "headline": "Senior Backend Engineer",
                "contact_line": "Shanghai · alex.chen@example.com · +86 138 0000 0000",
            },
            "summary": (
                "Six years building high-traffic payment and order systems. Led the migration "
                "of a monolithic order service to event-driven services, cutting P99 latency "
                "from 820ms to 140ms while peak traffic tripled."
            ),
            "experience_blocks": [
                {
                    "company": "Example Technology",
                    "title": "Senior Backend Engineer",
                    "date_range": "Mar 2021 – Present",
                    "location": "Shanghai",
                    "scope_line": "Owns the order domain · 6 engineers",
                    "bullets": [
                        "Led the order service migration from a PHP monolith to Go services, reducing P99 latency from 820ms to 140ms while peak traffic grew 3x.",
                        "Designed the idempotency and reconciliation layer for payments, eliminating duplicate-charge incidents across four business lines.",
                        "Introduced request-scoped tracing across 12 services, cutting mean time to diagnose production issues from hours to minutes.",
                        "Mentored four engineers; two were promoted within eighteen months.",
                    ],
                },
                {
                    "company": "Example Commerce",
                    "title": "Backend Engineer",
                    "date_range": "Jul 2018 – Feb 2021",
                    "location": "Hangzhou",
                    "bullets": [
                        "Built the inventory reservation service used by all flash-sale traffic, holding oversell below 0.01% during peak campaigns.",
                        "Reduced nightly batch runtime from 4 hours to 25 minutes by restructuring the job graph and adding incremental computation.",
                    ],
                },
            ],
            "project_blocks": [
                {
                    "name": "Internal Observability Platform",
                    "role": "Creator",
                    "date_range": "2022",
                    "bullets": [
                        "Built a self-service dashboard adopted by 8 teams, replacing ad-hoc SQL queries with structured metrics.",
                    ],
                }
            ],
            "education_blocks": [
                {
                    "school": "Example University",
                    "degree_line": "B.Eng. Computer Science",
                    "date_range": "2014 – 2018",
                }
            ],
            "skills_block": {
                "title": "Skills",
                "content": "Go, Python, MySQL, Redis, Kafka, Kubernetes, Distributed Systems",
            },
        }
    return {
        "header": {
            "name": "陈示例",
            "headline": "高级后端工程师",
            "contact_line": "上海 · chen@example.com · 138 0000 0000",
        },
        "summary": (
            "6 年高并发交易与订单系统开发经验，主导订单服务从单体迁移到事件驱动架构，"
            "P99 延迟由 820ms 降至 140ms，同时支撑起 3 倍峰值流量。"
        ),
        "experience_blocks": [
            {
                "company": "示例科技",
                "title": "高级后端工程师",
                "date_range": "2021-03 – 至今",
                "location": "上海",
                "scope_line": "负责订单域 · 带 6 人团队",
                "bullets": [
                    "主导订单服务从 PHP 单体迁移至 Go 微服务，P99 延迟由 820ms 降至 140ms，同期峰值流量增长 3 倍。",
                    "设计支付幂等与对账链路，消除四条业务线重复扣费问题。",
                    "推动 12 个服务接入请求级链路追踪，线上问题平均定位时间由小时级缩短至分钟级。",
                    "带 4 名工程师，其中 2 人在 18 个月内晋升。",
                ],
            },
            {
                "company": "示例电商",
                "title": "后端工程师",
                "date_range": "2018-07 – 2021-02",
                "location": "杭州",
                "bullets": [
                    "搭建全站秒杀流量共用的库存预占服务，大促期间超卖率维持在 0.01% 以下。",
                    "重构夜间批处理任务图并引入增量计算，运行时长由 4 小时降至 25 分钟。",
                ],
            },
        ],
        "project_blocks": [
            {
                "name": "内部可观测平台",
                "role": "从 0 到 1 建设",
                "date_range": "2022",
                "bullets": [
                    "建设自助看板并被 8 个团队采用，替代原先散落的临时 SQL 查询。",
                ],
            }
        ],
        "education_blocks": [
            {
                "school": "示例大学",
                "degree_line": "计算机科学与技术 · 本科",
                "date_range": "2014 – 2018",
            }
        ],
        "skills_block": {
            "title": "技能",
            "content": "Go、Python、MySQL、Redis、Kafka、Kubernetes、分布式系统",
        },
    }


def bilingual_sections() -> dict:
    """The bilingual template takes `zh_sections` / `en_sections`, not one tree."""
    return {"zh_sections": sample_sections("zh"), "en_sections": sample_sections("en")}


def check() -> int:
    try:
        import playwright  # noqa: F401
    except ImportError:
        print(_INSTALL_HINT, file=sys.stderr)
        return 2
    from jc.services.resume_render_engine import ResumeRenderEngine  # noqa: F401

    print("ready: playwright + ResumeRenderEngine available")
    print(f"would write {len(TEMPLATES)} images to {OUTPUT_DIR}")
    return 0


def render() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(_INSTALL_HINT, file=sys.stderr)
        return 2

    from jc.services.resume_render_engine import ResumeRenderEngine

    engine = ResumeRenderEngine()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for template_id, label in TEMPLATES:
                sections = (
                    bilingual_sections()
                    if template_id == "zh-en-bilingual"
                    else sample_sections("en" if template_id.startswith("en") else "zh")
                )
                html = engine.render_html(sections, template_id=template_id)
                page = browser.new_page(viewport=VIEWPORT, device_scale_factor=SCALE)
                try:
                    # Templates are self-contained by contract (`validate_export` rejects any
                    # external <link>/<script>), so blocking requests cannot change what we
                    # capture — it only guarantees a slow network cannot.
                    page.route("**/*", lambda route: route.abort())
                    page.set_content(html, wait_until="load")
                    out = OUTPUT_DIR / f"{template_id}.png"
                    # Clip to the first page: a thumbnail shows the top of the document,
                    # which is what a reader scanning templates actually compares.
                    page.screenshot(path=str(out), clip={"x": 0, "y": 0, **VIEWPORT})
                    print(f"  {template_id:<18} {label:<8} -> {out}")
                finally:
                    page.close()
        finally:
            browser.close()
    print(f"done: {len(TEMPLATES)} images written")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Render resume template thumbnails.")
    parser.add_argument("--check", action="store_true", help="report readiness without rendering")
    args = parser.parse_args()
    return check() if args.check else render()


if __name__ == "__main__":
    raise SystemExit(main())
