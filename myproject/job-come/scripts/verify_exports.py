#!/usr/bin/env python3
"""Generate deidentified PDF/DOCX artifacts and validate content for visual QA."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jobcome.services.export_quality import validate_export
from jobcome.services.resume_render_engine import ResumeRenderEngine

SECTIONS = {
    "header": {
        "name": "张明",
        "headline": "产品经理 · 数据驱动增长",
        "contact_line": "example@example.com · 上海",
    },
    "summary": "五年互联网产品经验，负责用户研究、产品规划与跨团队协作。",
    "experience_blocks": [
        {
            "company": "示例互联网公司",
            "title": "产品经理",
            "date_range": "2021 – 2026",
            "location": "上海",
            "bullets": [
                "设计转化漏斗与实验指标，推动业务增长 30%。",
                "协调研发、设计、运营完成三个版本迭代。",
            ],
        }
    ],
    "education_blocks": [
        {"school": "示例大学", "degree_line": "经济学 · 本科", "date_range": "2015 – 2019"}
    ],
    "skills_block": {"title": "技能", "content": "SQL · 用户研究 · 数据分析 · 产品规划"},
    "project_blocks": [
        {
            "name": "增长分析项目",
            "date_range": "2025",
            "description": "建立统一指标体系。",
            "bullets": ["沉淀实验复盘与产品迭代机制。"],
        }
    ],
}


def main(output):
    import fitz

    output.mkdir(parents=True, exist_ok=True)
    renderer = ResumeRenderEngine()
    reports = []
    for template in ["zh-one-page", "en-two-page", "zh-en-bilingual"]:
        sections = (
            SECTIONS
            if template != "zh-en-bilingual"
            else {"track": "bilingual", "zh_sections": SECTIONS, "en_sections": SECTIONS}
        )
        for format in ["pdf", "docx"]:
            content = (
                renderer.render_pdf(renderer.render_html(sections, template_id=template))
                if format == "pdf"
                else renderer.render_docx(sections)
            )
            report = validate_export(content, format, sections)
            report["template"] = template
            (output / f"{template}.{format}").write_bytes(content)
            reports.append(report)
            if format == "pdf":
                with fitz.open(stream=content, filetype="pdf") as doc:
                    for i, page in enumerate(doc):
                        page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(
                            str(output / f"{template}-{i + 1}.png")
                        )
    (output / "report.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n")
    print("PASS: 6 exports generated; PDF screenshots ready for visual inspection")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/tmp/jobcome-export-evidence"))
    main(parser.parse_args().output)
