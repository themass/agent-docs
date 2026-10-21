"""SQLAlchemy ORM models — import all for Alembic metadata."""

# Registers the `before_flush` listener that snapshots `Profile.payload`
# before every write (see that module's docstring). Imported here, not
# only from the service modules that happen to use `bind_snapshot_source`,
# so the listener is guaranteed registered the moment any model in this
# package is imported -- the same guarantee this file already gives
# Alembic for table metadata.
import jc.db.profile_snapshot_hook  # noqa: F401,I001

from jc.models.agent import AgentSession
from jc.models.agent_message import AgentMessage
from jc.models.agent_trace import AgentTrace
from jc.models.feedback import FeedbackMessage, FeedbackThread
from jc.models.guest import GuestSession, PasswordResetToken
from jc.models.interview import (
    AnswerAttempt,
    Application,
    InterviewQuestion,
    InterviewRecord,
    MockSession,
    OfferTrack,
)
from jc.models.job import Campaign, Job
from jc.models.llm_call import LlmCall, LlmCallAttempt
from jc.models.profile import Profile, ProfileSource
from jc.models.profile_patch_confirm import ProfilePatchConfirm
from jc.models.profile_snapshot import ProfileSnapshot
from jc.models.resume import ExportJob, ResumeDraft
from jc.models.user import User, UserMeta

__all__ = [
    "AgentMessage",
    "AgentSession",
    "AgentTrace",
    "AnswerAttempt",
    "Application",
    "Campaign",
    "ExportJob",
    "FeedbackMessage",
    "FeedbackThread",
    "GuestSession",
    "InterviewQuestion",
    "InterviewRecord",
    "Job",
    "LlmCall",
    "LlmCallAttempt",
    "MockSession",
    "OfferTrack",
    "PasswordResetToken",
    "Profile",
    "ProfilePatchConfirm",
    "ProfileSnapshot",
    "ProfileSource",
    "ResumeDraft",
    "User",
    "UserMeta",
]
