"""One ledger: `jc_agent_message` folds into `jc_agent_trace`.

Both tables were written from the same stream loop — the UI projection in one, the
audit ledger in the other — so every tool call, every tool result and every
reasoning block was stored twice. The UI row also had no stable order (it sorted on
`created_at`, which ties within one turn). One table with two faces fixes both: a row
is ordered by `seq` and carries `ui_event` (whether/how the chat draws it) beside
`payload` (the full detail audit needs).

`jc_agent_message` is dropped, not kept in sync. Nothing reads it after this
release: chat history, the session title, the confirm recovery path and the admin
timeline all read the ledger. There is no data to migrate — this ships before the
first user — so the drop cannot lose a transcript.

`attachments` goes too: it was declared on the trace model but no writer ever set
it. Attachment pointers live in the user turn's `payload.attachments`, next to the
message they belong to.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "026_agent_ledger"
down_revision: str | None = "025_agent_cancel_request"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(bind, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    """Idempotent on purpose.

    A deploy runs this against whatever state the database happens to be in, and
    a migration that assumes a clean starting point turns a half-applied release
    into a stuck one. The live incident that made this a rule: the schema had
    already been brought to this revision by hand while the deploy host still had
    the previous code, so `add_column` failed on a column that was already there
    and every later step was skipped. Every step below therefore checks first.
    """
    bind = op.get_bind()

    # 1. Drop the duplicate projection table, if this database still has it.
    if sa.inspect(bind).has_table("jc_agent_message"):
        op.drop_table("jc_agent_message")

    # 2. The two columns that turn a ledger row into a chat row.
    columns = _columns(bind, "jc_agent_trace")
    if "ui_event" not in columns:
        op.add_column("jc_agent_trace", sa.Column("ui_event", sa.String(32), nullable=True))
    if "content" not in columns:
        op.add_column("jc_agent_trace", sa.Column("content", sa.Text(), nullable=True))
    # Declared on the model, never written by any code path: attachment pointers
    # have always lived in the user turn's payload, next to the message.
    if "attachments" in columns:
        op.drop_column("jc_agent_trace", "attachments")

    # 3. The chat reads one session's UI rows in order; the retention sweep walks
    #    created_at. Both are ordinary index work at this table's size.
    indexes = _indexes(bind, "jc_agent_trace")
    if "ix_jc_agent_trace_session_ui" not in indexes:
        op.create_index(
            "ix_jc_agent_trace_session_ui",
            "jc_agent_trace",
            ["session_id", "ui_event"],
        )
    if "ix_jc_agent_trace_created" not in indexes:
        op.create_index("ix_jc_agent_trace_created", "jc_agent_trace", ["created_at"])


def downgrade() -> None:
    """Recreate the empty projection table.

    Data is not restored: that table had no other owner, and the two
    representations were never kept in sync in reverse.
    """
    op.drop_index("ix_jc_agent_trace_created", table_name="jc_agent_trace")
    op.drop_index("ix_jc_agent_trace_session_ui", table_name="jc_agent_trace")
    op.drop_column("jc_agent_trace", "content")
    op.drop_column("jc_agent_trace", "ui_event")
    op.add_column("jc_agent_trace", sa.Column("attachments", sa.Text(), nullable=True))

    op.create_table(
        "jc_agent_message",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(32),
            sa.ForeignKey("jc_agent_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False, server_default="message"),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_jc_agent_message_session", "jc_agent_message", ["session_id"])
