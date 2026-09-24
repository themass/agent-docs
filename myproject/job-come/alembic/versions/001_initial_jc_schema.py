"""Initial jc_* schema for JobCome M1."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGTEXT

revision: str = "001_initial_jc"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jc_user",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("uq_jc_user_email", "jc_user", ["email"], unique=True, mysql_length=191)

    op.create_table(
        "jc_user_meta",
        sa.Column("user_id", sa.String(32), sa.ForeignKey("jc_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("locale", sa.String(16), nullable=False, server_default="zh-CN"),
        sa.Column("default_elevation_level", sa.String(16), nullable=False, server_default="elevated"),
        sa.Column("notify_email_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "jc_guest_session",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_by_user_id", sa.String(32), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_jc_guest_session_expires", "jc_guest_session", ["expires_at"])

    op.create_table(
        "jc_password_reset",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "jc_profile",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("jc_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("guest_session_id", sa.String(32), sa.ForeignKey("jc_guest_session.id", ondelete="SET NULL"), nullable=True),
        sa.Column("owner_kind", sa.String(8), nullable=False, server_default="guest"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("locale", sa.String(16), nullable=False, server_default="zh-CN"),
        sa.Column("payload", LONGTEXT, nullable=False),
        sa.Column("summary_text", sa.String(512), nullable=True),
        sa.Column("contact_name", sa.String(128), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "jc_profile_source",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("profile_id", sa.String(32), sa.ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("parse_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("parse_error", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "jc_job",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("profile_id", sa.String(32), sa.ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=False),
        sa.Column("role_category", sa.String(64), nullable=True),
        sa.Column("tag", sa.String(16), nullable=False, server_default="warmup"),
        sa.Column("fit_score", sa.Integer(), nullable=True),
        sa.Column("fit_recommendation", sa.String(16), nullable=True),
        sa.Column("fit_gaps", sa.Text(), nullable=False),
        sa.Column("fit_blockers", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "jc_resume_draft",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("profile_id", sa.String(32), sa.ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(32), sa.ForeignKey("jc_job.id", ondelete="SET NULL"), nullable=True),
        sa.Column("elevation_level", sa.String(16), nullable=False, server_default="elevated"),
        sa.Column("locale", sa.String(16), nullable=False, server_default="zh-CN"),
        sa.Column("template_id", sa.String(64), nullable=False),
        sa.Column("sections", sa.Text(), nullable=False),
        sa.Column("elevation_map", sa.Text(), nullable=False),
        sa.Column("reviewer_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("reviewer_notes", sa.String(1024), nullable=True),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "jc_export_job",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("profile_id", sa.String(32), nullable=False),
        sa.Column("resume_draft_id", sa.String(32), nullable=True),
        sa.Column("format", sa.String(8), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False, server_default="zh-CN"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("error_message", sa.String(512), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "jc_campaign",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("profile_id", sa.String(32), sa.ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("phase", sa.String(16), nullable=False, server_default="warmup"),
        sa.Column("warmup_job_ids", sa.Text(), nullable=False),
        sa.Column("target_job_ids", sa.Text(), nullable=False),
        sa.Column("progress", sa.Text(), nullable=False),
        sa.Column("target_unlocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "jc_interview_record",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("profile_id", sa.String(32), sa.ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("role_title", sa.String(255), nullable=False),
        sa.Column("job_id", sa.String(32), nullable=True),
        sa.Column("round", sa.String(16), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("interview_date", sa.Date(), nullable=False),
        sa.Column("result", sa.String(16), nullable=True),
        sa.Column("failure_tags", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("question_ids", sa.Text(), nullable=False),
        sa.Column("resume_variant_id", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "jc_interview_question",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("profile_id", sa.String(32), sa.ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(32), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default="real"),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("role_title", sa.String(255), nullable=True),
        sa.Column("role_category", sa.String(64), nullable=True),
        sa.Column("round", sa.String(16), nullable=True),
        sa.Column("interview_record_id", sa.String(32), sa.ForeignKey("jc_interview_record.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", sa.String(32), nullable=True),
        sa.Column("tags", sa.Text(), nullable=False),
        sa.Column("best_attempt_id", sa.String(32), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "jc_answer_attempt",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("question_id", sa.String(32), sa.ForeignKey("jc_interview_question.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.String(32), nullable=False),
        sa.Column("mock_session_id", sa.String(32), nullable=True),
        sa.Column("user_answer", sa.Text(), nullable=False),
        sa.Column("coach_feedback", sa.Text(), nullable=False),
        sa.Column("reference_answer", sa.Text(), nullable=True),
        sa.Column("is_best", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "jc_mock_session",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("profile_id", sa.String(32), sa.ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("job_id", sa.String(32), nullable=True),
        sa.Column("resume_variant_id", sa.String(32), nullable=True),
        sa.Column("round", sa.String(16), nullable=True),
        sa.Column("question_ids", sa.Text(), nullable=False),
        sa.Column("bank_draw_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deerflow_thread_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "jc_application",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("profile_id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("resume_variant_id", sa.String(32), nullable=True),
        sa.Column("applied_at", sa.Date(), nullable=True),
        sa.Column("user_marked", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("note", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "jc_offer_track",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("profile_id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "jc_agent_session",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("jc_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.String(32), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False, server_default="resume"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("deerflow_thread_id", sa.String(128), nullable=False),
        sa.Column("skill_hint", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    for t in reversed([
        "jc_agent_session",
        "jc_offer_track",
        "jc_application",
        "jc_mock_session",
        "jc_answer_attempt",
        "jc_interview_question",
        "jc_interview_record",
        "jc_campaign",
        "jc_export_job",
        "jc_resume_draft",
        "jc_job",
        "jc_profile_source",
        "jc_profile",
        "jc_password_reset",
        "jc_guest_session",
        "jc_user_meta",
        "jc_user",
    ]):
        op.drop_table(t)
