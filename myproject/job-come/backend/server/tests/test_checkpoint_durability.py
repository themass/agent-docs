"""The checkpoint write cadence is a latency contract, not an implementation detail.

Measured on production before this existed: one turn made 85 checkpointer
round-trips, 55 of them writes at 360-550 ms each, against a database 169 ms
away. That is ~25 s of database latency per turn — more than the model call —
and it is what "the agent is slow" actually meant. These tests pin the setting
that removes it, and pin the precondition that makes it safe.
"""

from __future__ import annotations

from jc.adapters import deerflow_harness_client
from jc.config import settings


def test_runs_do_not_checkpoint_after_every_step():
    """`async` is LangGraph's default and the expensive one; JC must not use it."""
    assert settings.jc_deerflow_checkpoint_durability == "exit"


def test_the_cadence_reaches_the_runnable_config():
    """LangGraph reads the cadence from the runnable config, not `stream()`.

    A value set anywhere else — a stream argument, the graph constructor — is
    silently ignored, so this asserts the one path that actually works.
    """
    overrides = deerflow_harness_client.jc_configurable_overrides()
    assert overrides[deerflow_harness_client.CONFIG_KEY_DURABILITY] == "exit"


def test_runs_are_marked_non_interactive():
    """The other override in the same block; a run must never block on input."""
    assert deerflow_harness_client.jc_configurable_overrides()["non_interactive"] is True


def test_no_hitl_approval_middleware_is_enabled():
    """Why `exit` is safe: nothing needs step-level durability.

    `exit` persists once, when the graph exits. A run that pauses at
    LangGraph's `interrupt()` would lose that paused state, because it only
    exists mid-run. DeerFlow installs the HITL approval middleware only when
    `hitl_approval.enabled` is true, which defaults to false and is never set
    in JC's config.yaml. If this ever fails, the cadence must go back to
    "async" in the same change.
    """
    from deerflow.config.app_config import AppConfig

    field = AppConfig.model_fields.get("hitl_approval")
    if field is None:
        # The installed DeerFlow predates the HITL middleware entirely, which
        # makes `exit` unambiguously safe: there is nothing to pause.
        return
    assert field.default_factory().enabled is False
