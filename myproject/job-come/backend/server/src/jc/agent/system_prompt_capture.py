"""Per-run capture of the system prompt the model actually received.

`jc_agent_trace` promises a replayable transcript, and seq 0 is supposed to be
the run's `system_prompt`. The adapter used to read it off the DeerFlow client
(`getattr(client, "rendered_system_prompt", None)`), but no such attribute
exists on the vendored upstream — so the getattr was permanently `None`, the
`system_prompt_rendered` event never fired, and every session's ledger began at
`user_message`. Patching the vendor tree to add the attribute would work until
the next upstream sync silently removed it again.

This takes the prompt from the one place that cannot drift: LangChain's
`wrap_model_call` middleware hook, whose `request.system_message` *is* the
system message about to go to the provider. That is strictly more accurate than
a client attribute would have been, because it is the text after every
middleware in the chain has had its say, not the template's first render.

The handoff is a registry rather than a return value because the capture
happens deep inside LangGraph's model call while the reader is the adapter's
stream loop several frames up and (for the async path) on a different task.
Keyed by `session_id` and popped on read: one in-flight stream per session is
already an invariant of this system (`AgentTraceStore.next_seq` documents the
same one), so a key can hold at most one live run's prompt.
"""

from __future__ import annotations

import threading

#: Bounds the registry so a crashed run that never got read cannot leak
#: unboundedly. Far above the number of genuinely concurrent sessions one
#: process serves; reaching it means runs are failing before `take`, which is
#: a bug to fix rather than a size to grow.
_MAX_PENDING = 512

_lock = threading.Lock()
_pending: dict[str, str] = {}


def record(session_id: str | None, text: str | None) -> None:
    """Remember this run's system prompt. First write per session wins.

    First-write-wins because a run makes several model calls (one per tool
    round trip) and they all carry the same system message; letting a later
    call overwrite would be harmless but pointless, while the ordering
    guarantee here keeps "seq 0 is the prompt this run started with" literally
    true even if a future middleware starts rewriting the prompt mid-run.
    """
    if not session_id or not text:
        return
    with _lock:
        if session_id in _pending:
            return
        if len(_pending) >= _MAX_PENDING:
            return
        _pending[session_id] = text


def take(session_id: str | None) -> str | None:
    """Pop this run's captured prompt, or `None` if nothing was captured."""
    if not session_id:
        return None
    with _lock:
        return _pending.pop(session_id, None)


def discard(session_id: str | None) -> None:
    """Drop any capture for this session without reading it.

    Called from the adapter's `finally`, so a run that errored before the
    stream loop could read the prompt does not leave the entry behind for the
    session's next run to pick up and mislabel as its own.
    """
    if not session_id:
        return
    with _lock:
        _pending.pop(session_id, None)
