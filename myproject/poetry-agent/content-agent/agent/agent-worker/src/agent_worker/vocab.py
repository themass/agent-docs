"""Shared vocabulary. Values mirror Java ``Vocabulary.java`` and ``pipeline/contracts/proposal.schema.json``."""
from __future__ import annotations

SCHEMA_ID = "agent-output/1"

TASK_TYPES = ("GAP_ANALYSIS", "ANNOTATION_DRAFT", "SCRIPT_DRAFT", "COMPILE_TRIAGE", "CONTENT_REVIEW")
ITEM_KINDS = ("GAP", "ANNOTATION", "BACKGROUND_NOTE", "SCRIPT_BEAT", "SOURCE_REQUEST", "TRIAGE_ITEM",
              # CONTENT_REVIEW 专用：审核意见本身，不是内容。三挡对应"可发布/需修正/有硬伤"。
              "REVIEW_FINDING")
EPISTEMICS = ("FACT_REQUEST", "INTERPRETATION", "DRAMATIZATION", "DRAFT_TEXT", "UNKNOWN")
SEVERITIES = ("HIGH", "MEDIUM", "LOW")

# Java Vocabulary.java
AUDIENCES = ("PRIMARY", "JUNIOR", "SENIOR")
CERTAINTIES_JAVA = ("KNOWN", "LIKELY", "DISPUTED", "UNKNOWN")
# An agent may never claim KNOWN (contract section 6, rule 4).
CERTAINTIES_AGENT = ("LIKELY", "DISPUTED", "UNKNOWN")
ANNOTATION_KINDS = ("WORD", "PHRASE", "ALLUSION", "IMAGE", "RHYME", "OTHER")
CLAIM_KINDS = ("FACT", "INTERPRETATION", "DRAMATIZATION")
LAYERS = ("SCENE", "CITY", "WORLD", "PERSON")
SOURCE_KINDS = (
    "OFFICIAL_HISTORY", "YEAR_BOOK", "ANTHOLOGY", "TEXTBOOK",
    "MODERN_STUDY", "DIGITIZED_TEXT", "ONLINE_ENTRY", "OTHER",
)

# v1 proposal (proposal.schema.json)
CHANGE_TYPES = ("GAP_REPORT", "ANNOTATION", "BACKGROUND", "CLAIM", "SCRIPT")
CLASSIFICATIONS = ("DRAFT", "INTERPRETATION", "UNKNOWN")

# Dispatch roles (BFF) and the subset the control bridge / MCP accepts.
DISPATCH_ROLES = ("CONTENT_EDITOR", "HISTORICAL_REVIEWER", "RELEASE_MANAGER", "PLATFORM_ADMIN")
CONTROL_ROLES = ("CONTENT_EDITOR", "HISTORICAL_REVIEWER")

# The five scene steps, in order (rules.mjs STEPS).
STEPS = ("read", "arrive", "meet", "return", "recite")

FORBIDDEN_CAPABILITIES = (
    "publish", "retract", "verify_source", "set_verified", "delete_content", "execute_sql",
)

# Limits (contract sections 5 and 6)
MAX_ITEMS = 50
MAX_UNKNOWNS = 50
MAX_SUMMARY = 1500
MAX_BODY = 7000
MAX_ANNOTATION_CONTENT = 8000
MAX_EVIDENCE_REFS = 20
