"""OpenAI-style tool definitions for agent runtime."""

from __future__ import annotations

from typing import Any

OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "jobcome_profile_get",
            "description": "Read the user's profile JSON (contact, experiences, education, skills).",
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_id": {"type": "string", "description": "Optional profile id"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jobcome_profile_patch",
            "description": "Patch profile fields (partial JSON merge into payload).",
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_id": {"type": "string"},
                    "patch": {"type": "object", "description": "Partial profile payload"},
                },
                "required": ["patch"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jobcome_bank_search_questions",
            "description": "Search interview question bank for this profile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "company": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jobcome_interview_save",
            "description": "Archive a real interview record with company, role, date, notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "record": {
                        "type": "object",
                        "properties": {
                            "company": {"type": "string"},
                            "role_title": {"type": "string"},
                            "interview_date": {"type": "string", "format": "date"},
                            "round": {"type": "string"},
                            "type": {"type": "string"},
                            "notes": {"type": "string"},
                            "question_ids": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["company", "role_title", "interview_date"],
                    }
                },
                "required": ["record"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jobcome_answer_save_attempt",
            "description": "Save a practice answer attempt with optional coach feedback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string"},
                    "question_stem": {
                        "type": "string",
                        "description": "When question_id missing, upsert by stem first",
                    },
                    "user_answer": {"type": "string"},
                    "coach_feedback": {"type": "object"},
                    "reference_answer": {"type": "string"},
                    "mock_session_id": {"type": "string"},
                    "company": {"type": "string"},
                    "job_id": {"type": "string"},
                },
                "required": ["user_answer"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jobcome_job_parse",
            "description": "Parse a pasted job description and optionally save to jc_job.",
            "parameters": {
                "type": "object",
                "properties": {
                    "raw_text": {"type": "string"},
                    "source_url": {"type": "string"},
                    "save": {"type": "boolean"},
                },
                "required": ["raw_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jobcome_fit_score",
            "description": "Score profile fit against a job (by job_id or inline JD text).",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "raw_jd": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jobcome_apply_pipeline",
            "description": (
                "Run one-job apply pipeline: fit score → job-bound elevate → review → export → "
                "optional application archive."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "raw_text": {"type": "string", "description": "JD text when job_id missing"},
                    "source_url": {"type": "string"},
                    "elevation_level": {"type": "string"},
                    "export_format": {"type": "string", "enum": ["pdf", "docx"]},
                    "create_application": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jobcome_resume_review",
            "description": (
                "Review the latest resume draft before export. Must pass before apply_pipeline export."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string"},
                    "elevation_level": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jobcome_question_upsert",
            "description": "Create or return an interview question in the personal bank.",
            "parameters": {
                "type": "object",
                "properties": {
                    "stem": {"type": "string", "description": "Question text"},
                    "question_type": {"type": "string"},
                    "company": {"type": "string"},
                    "role_title": {"type": "string"},
                    "job_id": {"type": "string"},
                    "mock_session_id": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["stem"],
            },
        },
    },
]

SKILL_TOOLS: dict[str, list[str]] = {
    "resume-coach": ["jobcome_profile_get", "jobcome_profile_patch"],
    "resume-writer": ["jobcome_profile_get", "jobcome_resume_review"],
    "resume-reviewer": ["jobcome_profile_get", "jobcome_resume_review"],
    "coach-mock": [
        "jobcome_profile_get",
        "jobcome_bank_search_questions",
        "jobcome_question_upsert",
        "jobcome_answer_save_attempt",
    ],
    "coach-archive": ["jobcome_profile_get", "jobcome_interview_save"],
    "coach-answer": ["jobcome_bank_search_questions", "jobcome_answer_save_attempt"],
    "jd-parser": ["jobcome_profile_get", "jobcome_job_parse", "jobcome_fit_score"],
    "apply-pipeline": [
        "jobcome_profile_get",
        "jobcome_job_parse",
        "jobcome_fit_score",
        "jobcome_profile_patch",
        "jobcome_resume_review",
        "jobcome_apply_pipeline",
    ],
}


def tools_for_skill(skill: str) -> list[dict[str, Any]]:
    names = set(SKILL_TOOLS.get(skill, ["jobcome_profile_get"]))
    return [t for t in OPENAI_TOOLS if t["function"]["name"] in names]
