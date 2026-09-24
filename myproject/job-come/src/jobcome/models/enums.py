"""Domain enumerations — stored as VARCHAR in MySQL."""

from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    DELETED = "deleted"


class ProfileStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"


class OwnerKind(StrEnum):
    GUEST = "guest"
    USER = "user"


class ConfidenceLevel(StrEnum):
    CONFIRMED = "confirmed"
    NEEDS_REVIEW = "needs_review"
    INFERRED = "inferred"


class ElevationLevel(StrEnum):
    CONSERVATIVE = "conservative"
    STANDARD = "standard"
    ELEVATED = "elevated"


class ReviewerStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class ExportJobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class ExportFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


class JobTag(StrEnum):
    WARMUP = "warmup"
    TARGET = "target"
    WATCH = "watch"


class JobStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class FitRecommendation(StrEnum):
    GO = "go"
    CAUTION = "caution"
    NO = "no"


class CampaignPhase(StrEnum):
    WARMUP = "warmup"
    TARGET = "target"


class InterviewRound(StrEnum):
    FIRST = "first"
    SECOND = "second"
    TECHNICAL = "technical"
    HR = "hr"
    FINAL = "final"


class InterviewType(StrEnum):
    WARMUP = "warmup"
    TARGET = "target"


class InterviewResult(StrEnum):
    NEXT_ROUND = "next_round"
    REJECTED = "rejected"
    OFFER = "offer"
    PENDING = "pending"


class QuestionType(StrEnum):
    PROJECT_DEEP = "project_deep"
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    SYSTEM_DESIGN = "system_design"
    CASE = "case"
    REVERSE = "reverse"
    OTHER = "other"


class QuestionSource(StrEnum):
    REAL = "real"
    MOCK = "mock"
    COMMUNITY = "community"


class MockSessionMode(StrEnum):
    WARMUP = "warmup"
    TARGET = "target"


class MockSessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OfferStage(StrEnum):
    PREPARING = "preparing"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    SIGNED = "signed"
    REJECTED = "rejected"


class AgentSessionKind(StrEnum):
    RESUME = "resume"
    COACH = "coach"


class AgentSessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class ParseStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
