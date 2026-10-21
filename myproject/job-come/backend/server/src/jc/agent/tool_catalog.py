"""The agent's tool catalog: what exists, and which role may call it.

This is declarative configuration, not an adapter. It names tools and maps each
agent role to the subset it is allowed to call; it holds no handler, no database
handle and no transport. That is why it lives on the harness-facing side rather
than inside `jc.mcp`: the harness client needs the per-role tool surface to build a
turn, and the admin inventory needs the catalog to report what the agent carries.
Neither of those should have to import the MCP tool surface to find out.

Adding a tool means touching three places on purpose: this catalog, the handler
adapter in `jc.mcp.handlers`, and the stdio surface in `jc.mcp.server`. A test
asserts all three agree, because a tool the model can see but the server cannot
serve is worse than a tool that does not exist.
"""

from __future__ import annotations

from typing import Any

OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "jc_profile_photo_set",
            "description": (
                "Use a user-uploaded chat image as a resume photo. Requests frontend cropping "
                "and explicit user save; does not silently save or crop. Defaults to latest "
                "image-bearing user message. Never pass image bytes, URLs or storage keys."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Optional user message id in this session",
                    },
                    "attachment_index": {
                        "type": "integer", "minimum": 0,
                        "description": "Attachment index; required to select among multiple images",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jc_profile_get",
            "description": (
                "Read current profile facts. Start with section=overview; read relevant "
                "sections/fields with pagination before editing. A partial read is not "
                "evidence of absence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_id": {"type": "string", "description": "Optional profile id"},
                    "section": {"type": "string", "default": "overview",
                        "enum": ["overview", "contact", "summary",
                        "experiences", "education", "projects", "skills", "constraints",
                        "preferences", "evidence_answers"]},
                    "field_path": {"type": "string",
                        "description": "Exact source path, e.g. experiences[0].highlights[1]"},
                    "offset": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    "text_offset": {"type": "integer", "minimum": 0,
                        "description": "Read character pages of a long string; follow next_text_offset."},
                    "text_limit": {"type": "integer", "minimum": 1, "maximum": 4000},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jc_profile_patch",
            "description": (
                "Propose edits to profile content for user confirmation. Accept nested partial "
                "objects or paths such as experiences[1].highlights[0]. Preserve unrelated "
                "bullets. Never modify meta/i18n; those are maintained by the server."
            ),
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
            "name": "jc_bank_search_questions",
            "description": "Search interview question bank for this profile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "company": {"type": "string"},
                    "job_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jc_interview_save",
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
            "name": "jc_answer_save_attempt",
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
            "name": "jc_job_fetch",
            "description": (
                "Read a public JD URL via safe GET or isolated dynamic rendering. Returns "
                "untrusted page data and provenance. No login, writes or applying."
            ),
            "parameters": {
                "type": "object", "additionalProperties": False,
                "properties": {"url": {"type": "string", "maxLength": 1024},
                               "render": {"type": "boolean", "default": False}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jc_job_parse",
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
            "name": "jc_fit_score",
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
            "name": "jc_apply_pipeline",
            "description": (
                "Run one-job apply pipeline: fit score → job-bound elevate → review → export → "
                "Does not submit to an employer. Register an application only when the user "
                "explicitly confirms actual submission."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "raw_text": {"type": "string", "description": "JD text when job_id missing"},
                    "source_url": {"type": "string"},
                    "elevation_level": {"type": "string"},
                    "export_format": {"type": "string", "enum": ["pdf", "docx"]},
                    "create_application": {
                        "type": "boolean", "default": False,
                        "description": "True only if user explicitly confirms already submitted; "
                        "never infer submission from export success.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jc_resume_review",
            "description": (
                "Review the latest resume draft before export. "
                "Must pass before apply_pipeline export."
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
            "name": "jc_intake_plan",
            "description": (
                "Read the interview plan for this profile: what is still missing before a "
                "resume can be generated, and the open questions. Call this before and "
                "after recording answers — it is the only way to know what is left."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "How many open questions to return",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jc_intake_record",
            "description": (
                "Write the user's own interview answers into the profile, verbatim. Only "
                "for questions jc_intake_plan currently lists as open. Never put your own "
                "words here."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "answers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question_id": {
                                    "type": "string",
                                    "description": "An open question id from jc_intake_plan",
                                },
                                "answer": {
                                    "type": "string",
                                    "description": "What the user said, unedited",
                                },
                                "target_path": {
                                    "type": "string",
                                    "description": "Optional; must match the question's path",
                                },
                            },
                            "required": ["question_id", "answer"],
                        },
                    },
                },
                "required": ["answers"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jc_question_upsert",
            "description": "Create or return an interview question in the personal bank.",
            "parameters": {
                "type": "object",
                "properties": {
                    "stem": {"type": "string", "description": "Question text"},
                    "source": {"type": "string", "enum": ["mock", "real"]},
                    "question_type": {"type": "string"},
                    "company": {"type": "string"},
                    "role_title": {"type": "string"},
                    "job_id": {"type": "string"},
                    "mock_session_id": {"type": "string"},
                    "round": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["stem"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jc_mock_session_history",
            "description": (
                "Read the question-and-answer turns already recorded for this mock "
                "interview session, in the order they were asked. Use this to check "
                "what was already asked before drawing a new question, especially if "
                "the conversation is long and earlier turns may have been summarized "
                "out of context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mock_session_id": {"type": "string"},
                    "limit": {"type": "integer", "description": "Max turns to return, most recent first in storage order."},
                },
            },
        },
    },
]

SKILL_TOOLS: dict[str, list[str]] = {
    # The coach reads the plan but cannot write answers: on a profile that can already
    # generate, the open questions are enrichment prompts, and "record this as an
    # interview answer" is not what 「把这条改得更有力」 means. Writing stays on the
    # confirmation-gated patch path there.
    "resume-coach": [
        "jc_profile_photo_set", "jc_profile_get", "jc_profile_patch", "jc_intake_plan",
    ],
    # profile-interview runs on the coach's turn (the host swaps the methodology,
    # not the runtime registration). It gets the coach's read/patch pair plus the two
    # intake tools: the plan, so it can see what is still missing after it writes, and
    # the recorder, so a transcribed answer lands in the slot the plan named instead of
    # becoming a confirm card the user has to approve for their own sentence.
    "profile-interview": [
        "jc_profile_photo_set",
        "jc_profile_get",
        "jc_profile_patch",
        "jc_intake_plan",
        "jc_intake_record",
    ],
    "resume-writer": ["jc_profile_get", "jc_resume_review"],
    "resume-reviewer": ["jc_profile_get", "jc_resume_review"],
    "coach-mock": [
        "jc_profile_get",
        "jc_bank_search_questions",
        "jc_question_upsert",
        "jc_answer_save_attempt",
        "jc_mock_session_history",
    ],
    "coach-archive": ["jc_profile_get", "jc_question_upsert", "jc_interview_save"],
    "coach-answer": ["jc_bank_search_questions", "jc_answer_save_attempt"],
    "jd-parser": ["jc_profile_get", "jc_job_fetch", "jc_job_parse", "jc_fit_score"],
    "apply-pipeline": [
        "jc_profile_photo_set",
        "jc_profile_get",
        "jc_job_fetch", "jc_job_parse",
        "jc_fit_score",
        "jc_profile_patch",
        "jc_resume_review",
        "jc_apply_pipeline",
    ],
}


def tools_for_skill(skill: str) -> list[dict[str, Any]]:
    names = set(SKILL_TOOLS.get(skill, ["jc_profile_get"]))
    return [t for t in OPENAI_TOOLS if t["function"]["name"] in names]


def tool_names() -> list[str]:
    """Every tool in the catalog, in declaration order."""
    return [str(t["function"]["name"]) for t in OPENAI_TOOLS]
