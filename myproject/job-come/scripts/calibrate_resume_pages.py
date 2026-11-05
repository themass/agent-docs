"""Re-measure the page budget used by jc.services.resume_diagnostics.

Renders our own templates at increasing length and reports the character count at which
Chromium actually breaks to a new page. Run this after changing template typography,
margins or font size, then update `_PAGE_BUDGET` in `resume_diagnostics.py`.

    python scripts/calibrate_resume_pages.py

Requires Playwright's Chromium, so it cannot run inside a restricted sandbox.
"""
import re

from lib.bootstrap import ensure_project_env

ensure_project_env()

import pymupdf  # noqa: E402
from jc.services.resume_render_engine import ResumeRenderEngine  # noqa: E402


def norm(t): return re.sub(r"[\s\u3000]+", "", t)

ZH_B = "主导订单服务拆分与容量治理，P99 从 420ms 降到 90ms，支撑日均 1200 万单稳定运行"
EN_B = ("Led the decomposition of the order service and its capacity governance, cutting "
        "P99 latency from 420ms to 90ms while supporting 12M daily orders.")

def make(n_bullets, *, zh):
    """Spread bullets across roles, 4 per role, like a real career."""
    b = ZH_B if zh else EN_B
    blocks = []
    remaining = n_bullets
    i = 0
    while remaining > 0:
        take = min(4, remaining)
        blocks.append({
            "company": f"公司{i}" if zh else f"Company {i}",
            "title": "后端工程师" if zh else "Backend Engineer",
            "date_range": "2020-01 – 2022-12" if zh else "Jan 2020 – Dec 2022",
            "bullets": [b] * take,
        })
        remaining -= take
        i += 1
    return {
        "locale": "zh-CN" if zh else "en-US",
        "header": {"name": "张三" if zh else "San Zhang",
                   "headline": "后端工程师" if zh else "Backend Engineer",
                   "contact_line": "a@b.com · 13800000000"},
        "summary": "十年后端经验，长期负责交易链路的稳定性与容量治理。" if zh
                   else "Ten years of backend experience owning transaction reliability.",
        "experience_blocks": blocks,
        "education_blocks": [],
        "skills_block": {"title": "技能" if zh else "Skills",
                         "content": "Go、MySQL、Redis、Kubernetes"},
        "section_order": ["summary", "experience", "projects", "skills", "education"],
    }

def measure(sections, tpl):
    e = ResumeRenderEngine()
    html = e.render_html(sections, template_id=tpl)
    doc = pymupdf.open(stream=e.render_pdf(html), filetype="pdf")
    parts = list(sections["header"].values()) + [sections["summary"]]
    for blk in sections["experience_blocks"]:
        parts += [blk["company"], blk["title"], blk["date_range"]] + blk["bullets"]
    parts.append(sections["skills_block"]["content"])
    return len(norm("\n".join(parts))), doc.page_count

for zh, tpl in ((True, "zh-one-page"), (False, "en-two-page")):
    print("===", "zh" if zh else "en", tpl)
    prev = 0
    for n in range(2, 80, 1):
        chars, pages = measure(make(n, zh=zh), tpl)
        if pages != prev:
            print(f"  first n reaching {pages} pages: n={n} chars={chars}")
            prev = pages
        if pages >= 4:
            break
