"""Coach mock follow-up templates and industry question bank."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_STAR_PATH = Path(__file__).resolve().parents[3] / "prompts" / "coach" / "star_followup_templates.md"
_INDUSTRY_PATH = Path(__file__).resolve().parents[3] / "prompts" / "coach" / "industry_followups.yaml"


def load_star_followup_markdown() -> str:
    if _STAR_PATH.is_file():
        return _STAR_PATH.read_text(encoding="utf-8")
    return "STAR follow-up templates."


def load_industry_followups() -> dict[str, list[str]]:
    if not _INDUSTRY_PATH.is_file():
        return {}
    data = yaml.safe_load(_INDUSTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    out: dict[str, list[str]] = {}
    for key, value in data.items():
        if isinstance(value, list):
            out[str(key)] = [str(v) for v in value]
    return out


def followups_for_role(role_title: str | None = None, *, limit: int = 3) -> list[str]:
    bank = load_industry_followups()
    if not bank:
        return []
    title = (role_title or "").lower()
    keys: list[str] = []
    if any(k in title for k in ("后端", "backend", "java", "go", "python")):
        keys.append("backend")
    if any(k in title for k in ("前端", "frontend", "react", "ios", "android")):
        keys.append("frontend" if "ios" not in title and "android" not in title else "ios")
    if any(k in title for k in ("产品", "product", "pm")):
        keys.append("pm")
    if any(k in title for k in ("数据", "data", "算法", "analytics")):
        keys.append("data")
    if any(k in title for k in ("运维", "devops", "sre")):
        keys.append("devops")
    if not keys:
        keys = ["general"]
    picked: list[str] = []
    for key in keys:
        picked.extend(bank.get(key, []))
    if not picked:
        picked = list(bank.get("general", []))
    return picked[:limit]


def load_coach_followup_markdown(role_title: str | None = None) -> str:
    parts = ["## STAR follow-up templates", load_star_followup_markdown()]
    samples = followups_for_role(role_title)
    if samples:
        parts.append("## Suggested industry follow-ups (pick one)")
        parts.extend(f"- {q}" for q in samples)
    return "\n\n".join(parts)


def industry_followups_payload() -> dict[str, Any]:
    return {"industries": load_industry_followups()}
