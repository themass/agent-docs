"""Agent session orchestration."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from agentkit.adapters.deerflow.client import AgentRunMetadata
from agentkit.common.ids import new_id
from agentkit.web.auth import UserActor
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from jc.adapters.deerflow_client import get_deerflow_client
from jc.adapters.deerflow_harness_client import _extract_text
from jc.agent.context_usage import build_context_usage_event
from jc.agent.message_content import flatten_message_for_text_agent
from jc.authz import RunScope, require_owned_references
from jc.config import settings
from jc.exceptions import ConflictError, NotFoundError
from jc.models.agent import AgentSession
from jc.models.agent_message import AgentMessage
from jc.models.enums import AgentSessionKind, AgentSessionStatus
from jc.observability.events import log_product_event
from jc.schemas.agent import (
    AgentAttachment,
    AgentConfirmRequest,
    AgentConfirmResponse,
    AgentMessageListResponse,
    AgentMessageRecord,
    AgentSessionCreateRequest,
    AgentSessionListItem,
    AgentSessionListResponse,
    AgentSessionResponse,
    AgentUiContext,
)
from jc.services.agent_attachment_service import (
    offload_for_persistence,
    resign_persisted_attachments,
    validate_inline_attachments,
)
from jc.services.patch_confirm_service import hydrate_confirmation_event, load_confirmation
from jc.services.profile_patch_service import apply_confirmed_patch
from jc.services.profile_service import ProfileService
from jc.stores.agent_message_store import AgentMessageStore
from jc.stores.agent_store import AgentStore
from jc.stores.agent_trace_store import AgentTraceStore

logger = logging.getLogger(__name__)

_PERSIST_EVENT_TYPES = frozenset(
    {
        "thinking",
        "tool_start",
        "tool",
        "tool_result",
        "plan_todos",
        "subagent_start",
        "subagent_done",
        "confirm",
        "usage",
        "error",
    }
)

_TOOL_ACTIVITY_EVENT_TYPES = frozenset(
    {
        "thinking",
        "tool_start",
        "tool",
        "tool_result",
        "plan_todos",
        "subagent_start",
        "subagent_done",
        "confirm",
    }
)

_ASSISTANT_FALLBACK = "处理完成。如需继续，请描述下一步需求。"


def _finalize_assistant_content(assistant_parts: list[str], had_tool_activity: bool) -> str | None:
    text = "".join(assistant_parts).strip()
    if text:
        return "".join(assistant_parts)
    if had_tool_activity:
        return _ASSISTANT_FALLBACK
    return None


def _format_user_message(content: str, attachments: list[AgentAttachment]) -> str:
    """What this turn's own history row shows the user later — not what the model reads.

    The model gets its own flattened view from `build_user_message_content`, with its
    own markers for images/files it can act on. Those markers do not belong here: every
    attachment kind already has a dedicated bubble in `AgentUserBubble` (`VoiceCard`,
    `ZoomableImage`, a file chip) rendered from the structured `attachments` payload, so
    repeating "[Attached image: x.png]" as plain text would show the same attachment
    twice — once as the real thumbnail/player, once as an English label the user never
    typed. This row's text is reserved for one thing only: words the user actually said
    or typed, so a voice turn with no text box input does not read as empty on replay.
    """
    parts: list[str] = []
    if content.strip():
        parts.append(content.strip())
    for att in attachments:
        if att.kind != "audio":
            continue
        # The browser already appended the dictated words into `content`, so adding
        # them again would show the user saying the same sentence twice in their own
        # history. Only backfill when the words are missing from the text -- either
        # nothing was recognized (nothing to backfill, the clip bubble says so on its
        # own), or the user edited the box after dictating (the words would otherwise
        # vanish from history entirely).
        said = (att.transcript or "").strip()
        if said and said not in content:
            parts.append(said)
    return "\n\n".join(parts) if parts else ""


class AgentService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._store = AgentStore(db)
        self._messages = AgentMessageStore(db)
        self._profiles = ProfileService(db)
        self._trace = AgentTraceStore(db)

    async def create_session(
        self,
        *,
        actor: UserActor,
        body: AgentSessionCreateRequest,
        trace_id: str,
    ) -> AgentSessionResponse:
        profile_id = body.profile_id
        if profile_id:
            await self._profiles.get(profile_id, actor=actor)

        extra: dict = {}
        if body.job_id:
            extra["job_id"] = body.job_id

        client = get_deerflow_client(db=self._db)
        metadata = AgentRunMetadata(
            trace_id=trace_id,
            user_id=actor.user_id,
            profile_id=profile_id,
            session_id=None,
            skill_hint=body.skill_hint,
            extra=extra,
        )
        thread_id = await client.start_session(metadata=metadata)

        session = AgentSession(
            id=new_id("agsn"),
            user_id=actor.user_id,
            profile_id=profile_id,
            job_id=body.job_id,
            kind=body.kind or AgentSessionKind.RESUME,
            status=AgentSessionStatus.ACTIVE,
            deerflow_thread_id=thread_id,
            skill_hint=body.skill_hint,
            trace_id=trace_id,
        )
        await self._store.create(session)
        # Load server-side timestamps before commit/response (avoids async lazy-load).
        await self._db.refresh(session)
        await self._db.commit()
        return self._to_response(session)

    async def get_session(self, session_id: str, *, actor: UserActor) -> AgentSessionResponse:
        session = await self._require_session(session_id, actor=actor)
        return self._to_response(session)

    async def list_sessions(
        self,
        *,
        actor: UserActor,
        profile_id: str | None = None,
        kind: str | None = None,
        limit: int = 20,
    ) -> AgentSessionListResponse:
        rows = await self._store.list_for_user(
            actor.user_id,
            profile_id=profile_id,
            kind=kind,
            limit=min(limit, 50),
        )
        session_ids = [s.id for s in rows]
        titles = await self._messages.first_user_titles(session_ids)
        return AgentSessionListResponse(
            sessions=[
                AgentSessionListItem(
                    id=s.id,
                    skill_hint=s.skill_hint,
                    kind=s.kind,
                    status=s.status,
                    profile_id=s.profile_id,
                    title=titles.get(s.id),
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                )
                for s in rows
            ]
        )

    async def list_messages(
        self, session_id: str, *, actor: UserActor
    ) -> AgentMessageListResponse:
        await self._require_session(session_id, actor=actor)
        rows = await self._messages.list_for_session(session_id)
        return AgentMessageListResponse(
            session_id=session_id,
            messages=[self._to_message_record(row) for row in rows],
        )

    async def stream_message(
        self,
        session_id: str,
        *,
        actor: UserActor,
        content: str,
        attachments: list[AgentAttachment] | None = None,
        reply_locale: str = "zh-CN",
        ui_context: AgentUiContext | None = None,
    ) -> AsyncIterator[dict]:
        session = await self._require_session(session_id, actor=actor)
        if ui_context and ui_context.mock_session_id:
            await require_owned_references(
                RunScope(
                    db=self._db,
                    user_id=actor.user_id,
                    profile_id=session.profile_id,
                ),
                job_id=session.job_id,
                mock_session_id=ui_context.mock_session_id,
            )
        attachment_list = attachments or []
        # Checked before anything else costs money or time: a photo that is too big
        # should be refused while the user is still looking at the composer, not after
        # they have waited through a vision call for it.
        validate_inline_attachments(attachment_list)
        user_text = _format_user_message(content, attachment_list)
        message_id = new_id("agm")
        persist_payload: dict[str, Any] | None = None
        if attachment_list or ui_context is not None:
            persist_payload = {}
            if attachment_list:
                # The bytes go to object storage and the row keeps only the key. The
                # payload column is MySQL TEXT (64 KB) and one camera frame is ~400 KB
                # once base64 inflates it, so the inline form never fit.
                persist_payload["attachments"] = await offload_for_persistence(
                    attachment_list,
                    session_id=session.id,
                    message_id=message_id,
                )
            if ui_context is not None:
                persist_payload["ui_context"] = ui_context.model_dump()

        await self._messages.append(
            message_id=message_id,
            session_id=session.id,
            role="user",
            event_type="message",
            content=user_text,
            payload=persist_payload,
        )
        await self._db.commit()

        client = get_deerflow_client(db=self._db)

        flatten_task = asyncio.create_task(
            flatten_message_for_text_agent(content, attachment_list),
        )
        # The API adapter wraps this stream with `with_heartbeat`, so liveness
        # pings stay at the transport boundary while this service awaits prep work.
        agent_message = await flatten_task
        from jc.agent.resume_task import (
            coach_role_family_for,
            coach_shortfall_for,
            coach_skill_for,
            wrap_resume_coach_message,
        )

        skill = session.skill_hint or "resume-coach"
        # The skill this turn actually runs as. It differs from the session's hint only
        # for the interview, and it has to be decided *before* the run metadata is
        # built: the hint is what bounds the turn's tool surface
        # (`SKILL_SCOPE` -> `SKILL_TOOLS`), so leaving it at `resume-coach` while
        # sending interview methodology produced an agent told to interview and holding
        # no way to record an answer — the intake tools were registered and
        # unreachable.
        runtime_skill = skill
        # Role family for this turn, passed to the harness so the middleware can
        # render the matching methodology into the *system* layer. `None` for a
        # non-resume skill or a profile that failed to load, which yields the
        # neutral playbook -- guessing a family wrong coaches against the wrong
        # audience, so no-guess is the correct failure mode.
        role_family: str | None = None
        if skill == "resume-coach" and session.profile_id:
            digest = ""
            interview = False
            shortfall: tuple[str, ...] = ()
            try:
                profile = await self._profiles.get(session.profile_id, actor=actor)
                from jc.domain.profile_context import turn_profile_context

                digest = f"profile_version={profile.version}\n" + turn_profile_context(
                    profile.payload,
                    focus_path=ui_context.focus.path if ui_context and ui_context.focus else None,
                )
                logger.info(
                    "profile_context task=%s profile_id=%s version=%s input_chars=%d",
                    skill, session.profile_id, profile.version, len(digest),
                )
                # Inferred from the profile's own titles rather than a target job:
                # the coach edits the career the user has, and a JD may not be
                # selected at all.
                role_family = coach_role_family_for(profile.payload)
                # A profile that cannot generate yet needs material, not polish.
                # The whole session's framing switches with it, which is why this
                # decides `runtime_skill`: the skill id is what bounds the turn's
                # tool surface *and* what selects the standing block's framing, so
                # interview methodology under a 「简历优化任务」 header -- the
                # contradiction the model used to resolve by inventing resume prose
                # -- is no longer expressible.
                runtime_skill = coach_skill_for(profile.payload)
                interview = runtime_skill != "resume-coach"
                if interview:
                    shortfall = coach_shortfall_for(profile.payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("profile_context unavailable profile_id=%s error_type=%s",
                               session.profile_id, type(exc).__name__)
                digest = ""
            agent_message = wrap_resume_coach_message(
                agent_message,
                profile_id=session.profile_id,
                digest=digest,
                ui_context=ui_context,
                interview=interview,
                # Small live index only; detailed facts are read by tool on demand.
                include_digest=True,
                shortfall=shortfall,
            )
        elif skill in {"coach-mock", "coach-answer"}:
            from jc.agent.coach_task import wrap_coach_mock_message
            from jc.stores.interview_store import InterviewStore

            mock_id = None
            drawn_stems: list[str] = []
            if session.profile_id:
                store = InterviewStore(self._db)
                mock = (await store.get_mock_session(ui_context.mock_session_id)
                        if ui_context and ui_context.mock_session_id else None)
                if mock is not None:
                    mock_id = mock.id
                    draw_n = int(mock.bank_draw_count or 0)
                    for qid in list(mock.question_ids or [])[:draw_n]:
                        q = await store.get_question(qid)
                        if q is not None:
                            drawn_stems.append(q.stem)
            agent_message = wrap_coach_mock_message(
                agent_message,
                profile_id=session.profile_id,
                job_id=session.job_id,
                mock_session_id=mock_id,
                drawn_stems=drawn_stems,
            )
        # The reply-language rule is no longer prepended here. It is the first
        # section of the standing block `JCProductRulesMiddleware` injects as
        # system content, so prepending it too made the model receive the same
        # instruction twice per turn, in two voices, with the weaker copy
        # sitting in front of the user's actual question.

        # `system_prompt` has to land at seq 0, but its text is only knowable
        # from inside the stream loop below (DeerFlow renders it lazily, on
        # the first `stream()` call that actually builds the agent -- see
        # `DeerFlowClient._ensure_agent`). So this turn's `user_message` row
        # is held back as a pending write and flushed by the loop immediately
        # after `system_prompt` lands (or immediately, for a session whose
        # `system_prompt` was already written by an earlier turn).
        trace_needs_system_prompt = not await self._trace.has_system_prompt(session.id)
        trace_user_message_pending = {
            "trace_id_pk": new_id("agtr"),
            "session_id": session.id,
            "event_type": "user_message",
            "role": "user",
            # `agent_message` is what DeerFlow actually receives for this turn
            # (profile digest / methodology / locale instruction already
            # wrapped in) -- the literal model input, not the raw textbox
            # value already captured by `jc_agent_message`.
            "payload": {"text": agent_message},
            "user_id": actor.user_id,
            "profile_id": session.profile_id,
            "job_id": session.job_id,
            "mock_session_id": ui_context.mock_session_id if ui_context else None,
            "trace_id": session.trace_id,
        }
        if not trace_needs_system_prompt:
            await self._trace.append(**trace_user_message_pending)
            trace_user_message_pending = None

        metadata = AgentRunMetadata(
            trace_id=session.trace_id or "",
            user_id=actor.user_id,
            profile_id=session.profile_id,
            session_id=session.id,
            skill_hint=runtime_skill,
            extra={
                **({"job_id": session.job_id} if session.job_id else {}),
                "reply_locale": reply_locale,
                "role_family": role_family,
                "mock_session_id": ui_context.mock_session_id if ui_context else None,
            },
        )

        assistant_parts: list[str] = []
        terminal_done: dict[str, Any] | None = None
        had_tool_activity = False
        had_error = False
        # `agent_message` has already been flattened above, which for an image means
        # the vision model has already been paid for and its text is in the string.
        # Passing the attachments along as well made the harness flatten a second
        # time: every image was OCR'd twice and the transcript appeared twice in the
        # prompt. The harness keeps its own flattening for callers that have not done
        # it; this one has, so it sends text only.
        # Commit trace setup before waiting on the model. InnoDB FK/read locks
        # must not span model latency or block an independent confirm request.
        await self._db.commit()
        async for event in client.stream_message(
            session.deerflow_thread_id,
            agent_message,
            metadata=metadata,
        ):
            event_type = event.get("type")
            if event_type == "done":
                # The UI may drain its follow-up queue immediately on done. Hold
                # that signal until the final assistant/history transaction commits.
                terminal_done = event
                continue
            if event_type == "system_prompt_rendered":
                # Internal-only: `_stream_producer` emits this once per run from
                # the worker thread, never a real DeerFlow event, so it must not
                # reach the SSE client (`continue`, not `yield`). Written at
                # seq 0 only the first time this session sees it; a later turn
                # on the same session still gets this event (the embedded
                # client always renders a prompt), but `has_system_prompt`
                # already answered true for it below so it is dropped there
                # instead of here, keeping the "only once" rule in one place.
                if trace_needs_system_prompt:
                    await self._trace.append(
                        trace_id_pk=new_id("agtr"),
                        session_id=session.id,
                        event_type="system_prompt",
                        role="system",
                        payload={"text": event.get("content") or ""},
                        user_id=actor.user_id,
                        profile_id=session.profile_id,
                        job_id=session.job_id,
                        mock_session_id=ui_context.mock_session_id if ui_context else None,
                        trace_id=session.trace_id,
                    )
                    trace_needs_system_prompt = False
                if trace_user_message_pending is not None:
                    await self._trace.append(**trace_user_message_pending)
                    trace_user_message_pending = None
                await self._db.commit()
                continue
            # The harness attaches `diagnostics` (exception type, stage, full
            # traceback) to a failed run's `error` event so the trace writer
            # below can store it. It is removed from the dict that goes out over
            # SSE: a traceback in a chat bubble is both useless to the user and
            # an information leak, and the frontend sanitizer never reads it.
            # `pop` rather than a copy because `_append_trace_for_stream_event`
            # runs after this and reads the key off the same object -- so the
            # value is lifted into a local here and handed to the trace writer.
            diagnostics = (
                event.pop("diagnostics", None) if event_type == "error" else None
            )
            if event_type == "confirm" and not isinstance(event.get("patch"), dict):
                event = await hydrate_confirmation_event(
                    RunScope(db=self._db, user_id=actor.user_id,
                             profile_id=session.profile_id, session_id=session.id), event,
                )
            if event_type == "error":
                had_error = True
            if event_type == "token":
                assistant_parts.append(_extract_text(event.get("content")))
            elif event_type in _TOOL_ACTIVITY_EVENT_TYPES:
                had_tool_activity = True
            if event_type in _PERSIST_EVENT_TYPES:
                await self._trace.lock_session(session.id)
                await self._persist_stream_event(session.id, event)
                if event_type in {"tool_start", "confirm"}:
                    log_product_event(
                        f"agent_{event_type}",
                        trace_id=session.trace_id,
                        user_id=actor.user_id,
                        profile_id=session.profile_id,
                        session_id=session.id,
                        name=event.get("name"),
                        confirm_id=event.get("confirm_id"),
                    )
            await self._append_trace_for_stream_event(
                session, actor, ui_context, event, diagnostics=diagnostics
            )
            if event_type in _PERSIST_EVENT_TYPES:
                # Persist before publishing: a disconnect must not erase a visible
                # confirmation/error, nor hold a DB transaction until the next token.
                await self._db.commit()
            # Internal full-size audit payloads belong only to jc_agent_trace,
            # not the UI wire projection (nor duplicated in message payload_json).
            yield {k: v for k, v in event.items() if k not in {"full_content", "full_result"}}
            if event_type == "usage":
                yield build_context_usage_event(
                    prompt_tokens=int(event.get("prompt_tokens") or 0),
                    completion_tokens=int(event.get("completion_tokens") or 0),
                    total_tokens=int(event.get("total_tokens") or 0),
                    limit_tokens=settings.resolved_context_token_limit,
                )

        # A run that produced no `system_prompt_rendered` event at all (e.g. it
        # errored before the first raw event, or ran entirely from the model's
        # own cache path) must not leave `user_message` stranded unwritten.
        if trace_user_message_pending is not None:
            await self._trace.append(**trace_user_message_pending)
            trace_user_message_pending = None

        final_content = _finalize_assistant_content(
            assistant_parts, had_tool_activity and not had_error,
        )
        if final_content:
            await self._trace.lock_session(session.id)
            await self._messages.append(
                message_id=new_id("agm"),
                session_id=session.id,
                role="assistant",
                event_type="message",
                content=final_content,
            )
            await self._trace.append(
                trace_id_pk=new_id("agtr"),
                session_id=session.id,
                event_type="assistant_message",
                role="assistant",
                payload={"text": final_content},
                user_id=actor.user_id,
                profile_id=session.profile_id,
                job_id=session.job_id,
                mock_session_id=ui_context.mock_session_id if ui_context else None,
                trace_id=session.trace_id,
            )
        await self._db.commit()
        if terminal_done is not None:
            yield terminal_done

    async def cancel_run(self, session_id: str, *, actor: UserActor) -> dict[str, bool]:
        session = await self._require_session(session_id, actor=actor)
        from jc.adapters.deerflow_harness_client import request_session_cancel

        cancelled = request_session_cancel(session.id)
        return {"cancelled": cancelled}

    async def confirm_patch(
        self,
        session_id: str,
        *,
        actor: UserActor,
        body: AgentConfirmRequest,
    ) -> AgentConfirmResponse:
        session = await self._require_session(session_id, actor=actor)
        scope = RunScope(
            db=self._db, user_id=actor.user_id,
            profile_id=session.profile_id, session_id=session.id,
        )
        if not body.approved:
            pending = await load_confirmation(scope, body.confirm_id)
            if pending.status == "applied":
                raise ConflictError(
                    "这条修改已保存，不能再拒绝；如需撤销请使用版本历史。",
                    code="confirmation_applied",
                )
            if pending.status == "pending":
                pending.status = "rejected"
                await self._messages.append(
                    message_id=new_id("agm"), session_id=session.id, role="user",
                    event_type="confirm_rejected", content=None,
                    payload={"confirm_id": body.confirm_id},
                )
            await self._db.commit()
            return AgentConfirmResponse(status="rejected", confirm_id=body.confirm_id,
                                        profile_id=session.profile_id)

        result = await apply_confirmed_patch(scope, confirm_id=body.confirm_id)
        if not result.pop("already_applied", False):
            await self._messages.append(
                message_id=new_id("agm"),
                session_id=session.id,
                role="assistant",
                event_type="confirm_applied",
                content=f"Profile updated to version {result.get('version')}",
                payload={"confirm_id": body.confirm_id, "profile_id": result.get("id"),
                         "version": result.get("version"), "status": "applied"},
            )
        await self._db.commit()
        return AgentConfirmResponse(
            status="applied",
            confirm_id=body.confirm_id,
            profile_id=result.get("id") or session.profile_id,
            version=result.get("version"),
        )

    async def read_photo_source(
        self, session_id: str, *, message_id: str, attachment_index: int, actor: UserActor,
    ) -> Response:
        from jc.services.agent_photo_service import read_photo_source

        session = await self._require_session(session_id, actor=actor)
        raw, mime = await read_photo_source(
            RunScope(
                db=self._db, user_id=actor.user_id,
                profile_id=session.profile_id, session_id=session.id,
            ),
            message_id=message_id, attachment_index=attachment_index,
        )
        return Response(
            raw, media_type=mime,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    async def _require_session(self, session_id: str, *, actor: UserActor) -> AgentSession:
        session = await self._store.get_by_id(session_id)
        if session is None or session.user_id != actor.user_id:
            raise NotFoundError("会话不存在或已删除。", code="agent_session_not_found")
        return session

    # Which stream events get a `jc_agent_trace` row, and what event_type they
    # map to there. Not every `_PERSIST_EVENT_TYPES` entry needs one: `usage`
    # and `plan_todos`/`subagent_start`/`subagent_done` are UI projections of
    # information already fully present in `tool_call`/`tool_result` rows
    # (`task` tool calls) or in `jc_llm_call` (token counts), so duplicating
    # them here would be a second place that could drift from the first
    # rather than new information.
    _TRACE_EVENT_MAP = {
        "thinking": "reasoning",
        "tool_start": "tool_call",
        "tool_result": "tool_result",
        "error": "error",
    }

    async def _append_trace_for_stream_event(
        self,
        session: AgentSession,
        actor: UserActor,
        ui_context: AgentUiContext | None,
        event: dict[str, Any],
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        event_type = event.get("type")
        trace_event_type = self._TRACE_EVENT_MAP.get(str(event_type))
        if trace_event_type is None:
            return
        if trace_event_type == "reasoning":
            # `full_content` is the untruncated text added alongside the
            # UI-sized `content` in `_map_raw_event` -- see that function's
            # docstring for why the trace table cannot reuse `content`.
            reasoning_text = event.get("full_content") or event.get("content") or ""
            payload: dict[str, Any] = {"text": reasoning_text}
        elif trace_event_type == "tool_call":
            payload = {"name": event.get("name"), "arguments": event.get("args")}
        elif trace_event_type == "tool_result":
            payload = {
                "name": event.get("name"),
                "result": event.get("full_result") or event.get("result") or "",
            }
        else:  # error
            # The traceback is stored under the failure's own keys rather than
            # flattened into `message`, so the admin console can render "what
            # broke" (exception type + stage) separately from "what the user was
            # told" -- and so a future reader can tell a run that died before
            # reaching the model apart from one that died on its final answer.
            payload = {"message": event.get("message") or ""}
            if diagnostics:
                payload.update(
                    {
                        "exception_type": diagnostics.get("exception_type"),
                        "stage": diagnostics.get("stage"),
                        "open_tools": diagnostics.get("open_tools") or [],
                        "traceback": diagnostics.get("traceback") or "",
                    }
                )
        await self._trace.append(
            trace_id_pk=new_id("agtr"),
            session_id=session.id,
            event_type=trace_event_type,
            role="assistant" if trace_event_type != "tool_result" else "tool",
            payload=payload,
            user_id=actor.user_id,
            profile_id=session.profile_id,
            job_id=session.job_id,
            mock_session_id=ui_context.mock_session_id if ui_context else None,
            trace_id=session.trace_id,
        )

    async def _persist_stream_event(self, session_id: str, event: dict[str, Any]) -> None:
        event_type = str(event.get("type") or "event")
        payload = {
            k: v for k, v in event.items()
            if k not in {"type", "content", "full_content", "full_result"}
        }
        content = event.get("content")
        if content is not None and not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        await self._messages.append(
            message_id=new_id("agm"),
            session_id=session_id,
            role="assistant",
            event_type=event_type,
            content=content if isinstance(content, str) else None,
            payload=payload or None,
        )

    @staticmethod
    def _to_message_record(row: AgentMessage) -> AgentMessageRecord:
        payload: dict[str, Any] | None = None
        if row.payload_json:
            # Signed media URLs outlive nothing; a transcript outlives everything. The
            # stored URL is only a cache, so replaying re-signs from `storage_key`.
            payload = resign_persisted_attachments(json.loads(row.payload_json))
        return AgentMessageRecord(
            id=row.id,
            session_id=row.session_id,
            role=row.role,
            event_type=row.event_type,
            content=row.content,
            payload=payload,
            created_at=row.created_at,
        )

    @staticmethod
    def _to_response(session: AgentSession) -> AgentSessionResponse:
        return AgentSessionResponse(
            id=session.id,
            deerflow_thread_id=session.deerflow_thread_id,
            skill_hint=session.skill_hint,
            kind=session.kind,
            status=session.status,
            profile_id=session.profile_id,
            created_at=session.created_at,
        )
