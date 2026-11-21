"""Mandate prompt assembly for DEERFLOW mode. Every byte of snapshot or editor text goes through sanitize."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agent_worker.sanitize import wrap_untrusted_blocks
from agent_worker.snapshot import SnapshotView

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
TASK_TEMPLATE = {
    "GAP_ANALYSIS": "gap_analysis.md", "ANNOTATION_DRAFT": "annotation_draft.md",
    "SCRIPT_DRAFT": "script_draft.md", "COMPILE_TRIAGE": "compile_triage.md",
    "CONTENT_REVIEW": "content_review.md",
}
_PLACEHOLDER = re.compile(r"\{\{([a-z_]+)\}\}")


def idempotency_prefix(run_id: str) -> str:
    return f"agent:{run_id}:"


def render_snapshot(v: SnapshotView) -> str:
    """Compact, line-oriented text. Citation locators are summarised, never quoted."""
    rows: list[str] = [f"作品 {v.work_id} 《{v.title}》 状态 {v.work.get('status')} 起始年 {v.work.get('start_year')}"]
    for ver in v.versions:
        rows.append(f"版本 {ver['id']} | {ver.get('label')} | 状态 {ver.get('status')} | 底本来源 {ver.get('source_id')}")
        for seq in v.line_seqs.get(str(ver["id"]), []):
            rows.append(f"句 line:{ver['id']}#{seq} | {v.line_content.get((str(ver['id']), seq), '')}")
    for c in v.claims:
        cid = str(c["id"])
        state = "可核查" if v.claim_checkable(cid) else "无可核查出处"
        rows.append(f"claim {cid} | 主体 {c.get('subject_id')} | {c.get('property_key')} | {c.get('claim_kind')}/{c.get('certainty')} | {state} | {c.get('value_text')}")
    for b in v.backgrounds:
        links = ",".join(f"{vid}#{seq}" for vid, seq in v.lines_of_background.get(str(b["id"]), []))
        rows.append(f"背景 {b['id']} | {b.get('layer')} | {b.get('audience')} | claim {b.get('claim_id')} | 关联句 {links or '无'} | {b.get('body_text')}")
    for a in v.annotations:
        rows.append(f"注释 {a['id']} | line:{a.get('version_id')}#{a.get('line_seq')} | {a.get('annotation_kind')}/{a.get('audience')} | claim {a.get('claim_id')} | {a.get('content')}")
    for s in v.sources:
        rows.append(f"来源 {s['id']} | {s.get('title')} | {s.get('source_kind')} | 核验状态 {v.source_verification(str(s['id']))}")
    for r in v.coverage_rows:
        rows.append(f"覆盖声明 {r.get('id')} | {r.get('entity_type')} {r.get('from_year')}-{r.get('to_year')} | {r.get('coverage_kind')} | {r.get('status')}")
    for g in v.gap_report.get("gaps") or []:
        rows.append(f"服务端缺口 {g.get('code')} | {g.get('severity')} | {g.get('message')}")
    for entry in v.gap_report.get("audit_non_zero") or []:
        rows.append(f"审计非零 {entry}")
    return "\n".join(rows)


def build_prompt(
    *, run_id: str, mandate_id: str, actor_role: str, work_id: str, task_type: str,
    profile_fingerprint: str, instructions: str, view: SnapshotView,
) -> str:
    values: dict[str, str] = {
        "run_id": run_id, "mandate_id": mandate_id, "actor_role": actor_role, "work_id": work_id,
        "task_type": task_type, "profile_fingerprint": profile_fingerprint,
        "idempotency_prefix": idempotency_prefix(run_id),
        "snapshot_blocks": "\n".join(wrap_untrusted_blocks(render_snapshot(view), f"studio-view:{work_id}")),
        "instruction_blocks": "\n".join(wrap_untrusted_blocks(instructions, "editor-instructions")),
        "task_prompt": (PROMPT_DIR / TASK_TEMPLATE[task_type]).read_text(encoding="utf-8"),
    }
    template = (PROMPT_DIR / "common.md").read_text(encoding="utf-8")

    def sub(match: re.Match[str]) -> str:  # single pass: substituted text is never re-scanned
        key = match.group(1)
        if key not in values:
            raise KeyError(f"unknown prompt placeholder {key}")
        return values[key]

    return _PLACEHOLDER.sub(sub, template)


def mandate_body(prompt: str, *, run_id: str, mandate_id: str, work_id: str, task_type: str,
                 profile_fingerprint: str, max_turns: int) -> dict[str, Any]:
    return {
        "assistant_id": None,  # filled by the runtime from config
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "metadata": {"poetry_run_id": run_id, "poetry_mandate_id": mandate_id, "poetry_work_id": work_id,
                     "poetry_task_type": task_type, "poetry_profile_fingerprint": profile_fingerprint},
        "config": {"recursion_limit": max(10, max_turns * 2 + 2)},
        "multitask_strategy": "reject",
    }
