"""The metrics kit: endpoint shape, no-op degradation, and label hygiene.

The failure mode this guards against is a metrics layer that seems to work and
quietly does not: a label that explodes cardinality, or a recorder that raises
into the request it was only meant to observe.
"""

from __future__ import annotations

import pytest

from agentkit.observability import (
    configure,
    inflight_turn,
    method_metrics,
    metrics_enabled,
    record_agent_phase,
    record_llm_metrics,
    render_metrics,
)


@pytest.fixture(autouse=True)
def _fresh_config():
    configure(application="test-app", environment="test", enabled=True)
    yield
    configure(application="agent", environment="dev", enabled=True)


def _scrape() -> str:
    return render_metrics().decode()


def test_a_model_call_shows_up_with_its_labels():
    record_llm_metrics(
        scenario="coach", model="gpt-6-luna", duration=4.2,
        status="success", prompt_tokens=1200, completion_tokens=30, attempts=1,
    )
    out = _scrape()
    assert 'llm_call_duration_seconds_count{' in out
    assert 'scenario="coach"' in out
    assert 'model="gpt-6-luna"' in out
    assert 'llm_tokens_total{' in out and 'direction="input"' in out


def test_a_failure_is_counted_with_its_error_class():
    record_llm_metrics(scenario="flash", model="glm", duration=9.0,
                       status="error", error_type="ServiceUnavailableError")
    assert 'error_type="ServiceUnavailableError"' in _scrape()


def test_error_text_is_not_a_label():
    """An exception message is unbounded and can carry user data.

    Only a class name may enter a label; a long message would both explode the
    series count and leak prompt content into the metrics store.
    """
    record_llm_metrics(scenario="coach", model="m", status="error",
                       error_type="x" * 500)
    out = _scrape()
    assert "x" * 60 not in out


def test_phases_are_separable():
    """The whole point: one slow turn must resolve into named phases."""
    record_agent_phase(phase="ttft", duration=9.0)
    record_agent_phase(phase="generate", duration=5.0)
    out = _scrape()
    assert 'phase="ttft"' in out
    assert 'phase="generate"' in out


def test_method_metrics_times_sync_and_async_calls():
    @method_metrics()
    def slow_sync():
        return 1

    @method_metrics()
    async def slow_async():
        return 2

    import asyncio
    slow_sync()
    asyncio.run(slow_async())
    out = _scrape()
    assert 'method_duration_seconds_count{' in out


def test_method_metrics_re_raises_unchanged():
    @method_metrics()
    def boom():
        raise ValueError("original")

    with pytest.raises(ValueError, match="original"):
        boom()
    assert 'error_type="ValueError"' in _scrape()


def test_disabled_means_no_output_but_no_crash():
    """The registry is process-global, so the probe needs a name nothing else used."""
    configure(application="test-app", environment="test", enabled=False)
    assert metrics_enabled() is False
    record_llm_metrics(scenario="disabled-probe", model="m", duration=1.0)
    record_agent_phase(phase="disabled-probe", duration=1.0)
    out = _scrape()
    assert "disabled-probe" not in out


def test_the_inflight_gauge_returns_to_zero():
    with inflight_turn():
        pass
    out = _scrape()
    for line in out.splitlines():
        if line.startswith("agent_turns_in_flight{"):
            assert line.endswith(" 0.0"), line


def test_every_series_carries_the_application_and_env_labels():
    """A deployment scraped next to another must be distinguishable.

    Scoped to this test's own phase name: the Prometheus registry is
    process-global, so another test in the same run leaves series behind under
    its own labels, and an unscoped scan would assert on those.
    """
    record_agent_phase(phase="label-probe", duration=1.0)
    lines = [
        line for line in _scrape().splitlines()
        if line.startswith("agent_phase_duration_seconds_count{") and 'phase="label-probe"' in line
    ]
    assert lines, "the probe series was not exported"
    for line in lines:
        assert 'application="test-app"' in line
        assert 'env="test"' in line


def test_the_app_exposes_a_metrics_endpoint():
    from jc.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/metrics" in paths
