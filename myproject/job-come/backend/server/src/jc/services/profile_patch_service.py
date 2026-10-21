"""Confirmation-gated profile patching.

Two operations, deliberately separate rather than one function with an `apply` flag:

- `propose_patch` validates a merge and parks it as a pending confirmation. Nothing
  is written. This is the only thing the agent can reach.
- `apply_confirmed_patch` consumes a confirmation the user accepted in the UI and
  performs the write. The only caller is the confirm endpoint.

Splitting them is what makes the permission boundary readable in the type signature
instead of in a branch: there is no argument the model can pass to `propose_patch`
that writes, because the writing code is not in it. The previous single entry point
took `apply: bool` and relied on the tool dispatcher remembering to strip it.

Concurrency is optimistic. The pending confirmation records `version_before`, and the
write is a compare-and-swap on that version, so a confirmation that was generated
against a profile the user has since changed is rejected rather than silently
clobbering the newer content.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from sqlalchemy import update

from jc.authz import RunScope, require_owned_profile
from jc.db.profile_snapshot_hook import bind_snapshot_source, build_snapshot
from jc.exceptions import ConflictError
from jc.models.profile import Profile
from jc.services.patch_confirm_service import create_pending, load_confirmation
from jc.services.profile_patch_ops import apply_profile_patch
from jc.stores.profile_store import ProfileStore


async def _load_owned_profile(scope: RunScope, profile_id: str | None) -> Profile:
    await require_owned_profile(scope, profile_id)
    pid = profile_id or scope.profile_id
    if not pid:
        raise ValueError("profile_id required")
    profile = await ProfileStore(scope.db).get_by_id(pid)
    if profile is None:
        raise ValueError("Profile not found")
    if not scope.user_id or profile.user_id != scope.user_id:
        raise PermissionError("Not your profile")
    return profile


async def propose_patch(
    scope: RunScope,
    patch: dict[str, Any],
    *,
    profile_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Validate a merge and park it for the user to confirm. Writes nothing."""
    profile = await _load_owned_profile(scope, profile_id)
    if not scope.user_id:
        raise PermissionError("Login required to patch profile")

    apply_profile_patch(profile.payload or {}, patch)

    pending = await create_pending(
        db=scope.db,
        session_id=session_id or scope.session_id or "",
        user_id=scope.user_id,
        profile_id=profile.id,
        patch=patch,
        preview={
            "profile_id": profile.id,
            "version_before": profile.version,
            "patch_keys": list(patch.keys()),
        },
    )
    await scope.db.commit()  # Durable before the tool result / SSE card is published.
    # The model-facing result omits the full merged profile. Confirmation stores
    # only the patch and expected version; merge/validation run again on approval.
    # Echoing a whole resume (easily 15k+ chars) into the tool result pushes it past
    # DeerFlow's
    # `tool_output_budget_middleware` externalization threshold (12k chars,
    # `ToolOutputConfig.externalize_min_chars`): the middleware then persists
    # the raw JSON to disk and replaces the tool message content with a typed
    # text synopsis ("[Full ... output saved to ...]"), which is not valid JSON.
    # `_maybe_emit_confirm` in `deerflow_harness_client.py` does `json.loads`
    # on that content to detect `status == "pending_confirm"` and emit the
    # frontend's `confirm` SSE event; a synopsis fails that parse and is
    # swallowed silently, so the confirm card never renders and the user never
    # gets a chance to approve the edit — the agent reports success but nothing
    # is ever written. Keeping this payload small is what keeps the tool result
    # under the externalization threshold for realistically-sized profiles.
    model_preview = {k: v for k, v in pending.preview.items() if k != "merged"}
    result = {
        "status": "pending_confirm",
        "confirm_id": pending.id,
        "profile_id": profile.id,
        "patch": patch,
        "preview": model_preview,
        "message": "Profile patch requires user confirmation in the UI.",
    }
    # Large rewrites can exceed DeerFlow's tool-output threshold even without
    # the merged profile. Keep the model-facing receipt bounded; the UI loads
    # the exact proposal from the shared DB, never from this compact receipt.
    if len(json.dumps(result)) > 6000:
        result.pop("patch")
        result["preview"] = {
            "profile_id": pending.profile_id,
            "version_before": pending.preview["version_before"],
            "patch_count": len(patch),
        }
    return result


async def apply_confirmed_patch(scope: RunScope, *, confirm_id: str) -> dict[str, Any]:
    """Consume a confirmation the user accepted and write the merged profile."""
    pending = await load_confirmation(scope, confirm_id)
    if pending.status == "applied":
        return {
            "status": "applied",
            "confirm_id": pending.id,
            "id": pending.profile_id,
            "version": pending.applied_version,
            "already_applied": True,
        }
    if pending.status == "superseded":
        raise ConflictError(
            "这条修改已被更新的提议取代，请确认对话里最新一张修改卡片。",
            code="confirmation_superseded",
        )
    if pending.status != "pending":
        raise ConflictError("这条修改已被拒绝，请重新生成修改确认。", code="confirmation_rejected")

    profile = await _load_owned_profile(scope, pending.profile_id)
    if pending.preview.get("version_before") != profile.version:
        raise ConflictError(
            "简历在生成确认后已更新，为避免覆盖，请让舟卡基于最新简历重新生成修改。",
            code="confirmation_stale",
        )

    payload = apply_profile_patch(profile.payload or {}, pending.patch)

    expected_version = int(pending.preview["version_before"])
    # Issued as a bare `UPDATE ... WHERE version = expected_version`, not an
    # ORM attribute assignment + flush: the CAS semantics require the WHERE
    # clause to race against a concurrent writer at the SQL level. That path
    # bypasses the `before_flush` listener in `jc.db.profile_snapshot_hook`
    # (it never touches `Session.dirty`), so the pre-write payload is
    # snapshotted explicitly here instead, inside the same label scope.
    with bind_snapshot_source("agent_patch"):
        result = await scope.db.execute(
            update(Profile)
            .where(
                Profile.id == profile.id,
                Profile.user_id == scope.user_id,
                Profile.version == expected_version,
            )
            .values(
                payload=payload.model_dump(mode="json"),
                contact_name=payload.contact.name,
                summary_text=(payload.summary or "")[:512] or None,
                version=expected_version + 1,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            await scope.db.rollback()
            raise ConflictError(
                "简历在生成确认后已更新，为避免覆盖，请让舟卡基于最新简历重新生成修改。",
                code="confirmation_stale",
            )
        # `profile.payload` is still the pre-write value: the UPDATE above is
        # raw SQL, never an ORM attribute assignment, so nothing reassigned
        # this in-memory object's attribute.
        scope.db.add(
            build_snapshot(
                profile_id=profile.id,
                version_after=expected_version + 1,
                payload=copy.deepcopy(profile.payload or {}),
                actor_user_id=scope.user_id,
            )
        )
        pending.status = "applied"
        pending.applied_version = expected_version + 1
        await scope.db.flush()
    await scope.db.refresh(profile)
    merged = payload.model_dump(mode="json")
    return {
        "status": "applied",
        "confirm_id": confirm_id,
        "id": profile.id,
        "version": profile.version,
        "payload": merged,
    }
