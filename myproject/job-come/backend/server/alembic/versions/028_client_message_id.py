"""`client_message_id` on the ledger: the row's own record of the client's id.

R2 (2026-11-18) opened two defects on the same field:

* G1 — the id was accepted on the request and used for interview-answer
  dedup, but never stored, so `GET .../messages` could never echo it back and
  the optimistic UI had nothing to merge its bubble onto after a reload.
* G2 — resending the same id appended a second user row, silently ("静默
  双写"). On a weak network the retry button and a page-reopen both reach
  this path, so duplicate bubbles were a predictable user-visible state.

Both fixes need the id ON the row, and G2's fix additionally needs the
database, not the service, to forbid a second row with the same
`(session_id, client_message_id)`: two resends racing past any
read-then-write check is exactly the interleaving a service cannot close.

The index is partial — only rows that carry an id are constrained. Every
older row, every non-user row, and every user turn sent without an id (which
deliberately does not dedup: the same words under a new id are a new message)
stay NULL and unconstrained, so there is nothing to backfill and nothing to
rewrite.

Idempotent on the same rule `026_agent_ledger` established: a deploy runs
against whatever state the database is in, and a step that assumes a clean
starting point turns a half-applied release into a stuck one.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "028_client_message_id"
down_revision: str | None = "027_media_upload"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(bind) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns("jc_agent_trace")}


def _indexes(bind) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes("jc_agent_trace")}


def upgrade() -> None:
    bind = op.get_bind()

    if "client_message_id" not in _columns(bind):
        op.add_column(
            "jc_agent_trace",
            sa.Column("client_message_id", sa.String(64), nullable=True),
        )

    if "uq_jc_agent_trace_session_client_id" not in _indexes(bind):
        # The WHERE clause is what makes this partial, i.e. free for the rows
        # that never carry an id. Both engines the code speaks to support it;
        # the dialect kwargs (not a raw string) keep it off exec()-style SQL
        # so a typo fails at import rather than at deploy.
        op.create_index(
            "uq_jc_agent_trace_session_client_id",
            "jc_agent_trace",
            ["session_id", "client_message_id"],
            unique=True,
            postgresql_where=sa.text("client_message_id IS NOT NULL"),
            sqlite_where=sa.text("client_message_id IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "uq_jc_agent_trace_session_client_id" in _indexes(bind):
        op.drop_index("uq_jc_agent_trace_session_client_id", table_name="jc_agent_trace")
    if "client_message_id" in _columns(bind):
        op.drop_column("jc_agent_trace", "client_message_id")
