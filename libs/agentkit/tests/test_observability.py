"""The metrics kit: endpoint shape, no-op degradation, and label hygiene.

The failure mode this guards against is a metrics layer that seems to work and
quietly does not: a label that explodes cardinality, or a recorder that raises
into the request it was only meant to observe.
"""

from __future__ import annotations

import pytest

from agentkit.observability import (
    OWNED_PREFIXES,
    configure,
    inflight_turn,
    method_metrics,
    metrics_enabled,
    record_agent_phase,
    record_llm_metrics,
    render_metrics,
    snapshot,
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




# --- snapshot(): the JSON shape a dashboard consumes -----------------------


def test_snapshot_names_the_service_and_its_environment():
    """A multi-service dashboard has to label every line with where it came from."""
    record_agent_phase(phase="snap-probe", duration=1.5)
    snap = snapshot()
    assert snap["service"] == "test-app"
    assert snap["environment"] == "test"
    assert snap["enabled"] is True


def test_snapshot_is_json_serializable():
    """It crosses an HTTP boundary; collector objects would not survive that."""
    import json

    record_agent_phase(phase="json-probe", duration=0.5)
    json.dumps(snapshot())


def test_snapshot_only_exports_this_kits_families():
    """prometheus_client's own GC/process collectors are not ours to chart.

    Depending on them would make the dashboard break on a prometheus_client
    upgrade that renames an internal metric.
    """
    record_agent_phase(phase="scope-probe", duration=0.2)
    names = set(snapshot()["families"])
    assert names, "nothing exported at all"
    for name in names:
        assert name.startswith(OWNED_PREFIXES), name


def test_snapshot_keeps_histogram_suffixes_apart():
    """Bucket lines and the count line are different series, not duplicates."""
    record_agent_phase(phase="hist-probe", duration=3.0)
    family = snapshot()["families"]["agent_phase_duration_seconds"]
    suffixes = {s["suffix"] for s in family["series"]}
    assert "bucket" in suffixes
    assert "count" in suffixes
    assert "sum" in suffixes


def test_snapshot_reports_disabled_rather_than_lying():
    configure(application="test-app", environment="test", enabled=False)
    snap = snapshot()
    assert snap["enabled"] is False
    assert snap["families"] == {}


# --- worker-process sharing ------------------------------------------------
#
# The switch is an environment variable read at import time, not a function call.
# That is prometheus_client's design (`values.py`:
# `ValueClass = get_value_class()` runs on import), and the first version of this
# kit got it wrong: `enable_multiprocess(dir)` returned True, wrote no files, and
# exported per-worker counters. These tests live in a subprocess because the
# decision happens once, at import — the only way to observe both modes is to
# start python twice.


def _run(code: str, *, multiproc_dir: str | None = None) -> str:
    """Run `code` in a fresh interpreter, optionally with the env var set."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = {**os.environ}
    env.pop("PROMETHEUS_MULTIPROC_DIR", None)
    if multiproc_dir is not None:
        env["PROMETHEUS_MULTIPROC_DIR"] = multiproc_dir
    # Resolve the package source rather than relying on an installed copy, so the
    # test exercises what is in this checkout.
    src = Path(__file__).resolve().parents[1] / "src"
    env["PYTHONPATH"] = str(src) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=120
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_without_the_env_var_counters_are_per_process(tmp_path):
    out = _run(
        "from agentkit.observability import MULTIPROCESS_MODE, sharing_across_processes;"
        "print(MULTIPROCESS_MODE, sharing_across_processes())"
    )
    assert out.split() == ["False", "False"]


def test_the_env_var_switches_on_sharing_and_actually_writes(tmp_path):
    """The assertion that would have caught the original bug.

    Reporting `MULTIPROCESS_MODE=True` is not enough — the previous version did
    that while writing nothing. A shared-mode counter must produce an mmap file,
    because that file *is* the mechanism.
    """
    d = str(tmp_path)
    out = _run(
        "import os;"
        "from agentkit.observability import MULTIPROCESS_MODE, configure, record_llm_metrics;"
        "configure(application='probe', environment='test');"
        "record_llm_metrics(scenario='coach', model='m', duration=1.0, prompt_tokens=5);"
        "print(MULTIPROCESS_MODE, sorted(os.listdir(os.environ['PROMETHEUS_MULTIPROC_DIR'])))",
        multiproc_dir=d,
    )
    mode, files = out.split(" ", 1)
    assert mode == "True"
    assert "counter_" in files and ".db" in files, out


def test_a_snapshot_reads_the_merged_view_not_one_worker(tmp_path):
    """Reading a worker's own registry would show only that worker's values."""
    d = str(tmp_path)
    out = _run(
        "import os;"
        "from agentkit.observability import configure, record_llm_metrics, snapshot;"
        "configure(application='probe', environment='test');"
        "record_llm_metrics(scenario='coach', model='m', duration=1.0, prompt_tokens=5);"
        "s = snapshot();"
        "print('llm_calls' in s['families'], s['service'])",
        multiproc_dir=d,
    )
    assert out.split() == ["True", "probe"]


def test_metric_definitions_are_lazy():
    """Metrics must not bind a registry at import; that is what lets the mode work."""
    from agentkit.observability import metrics as m

    m._reset_metrics()
    assert m._built == {}



def test_two_worker_processes_merge_to_five(tmp_path):
    """Process A +3 and process B +2 must scrape as 5 — not 3, not 2.

    One process cannot prove sharing; that was the original silent failure mode.
    """
    d = str(tmp_path)
    _run(
        "from agentkit.observability import configure, record_agent_phase\n"
        "configure(application='merge', environment='test')\n"
        "record_agent_phase(phase='merge-probe', duration=0.1)\n"
        "record_agent_phase(phase='merge-probe', duration=0.1)\n"
        "record_agent_phase(phase='merge-probe', duration=0.1)\n"
        "print('A')\n",
        multiproc_dir=d,
    )
    _run(
        "from agentkit.observability import configure, record_agent_phase\n"
        "configure(application='merge', environment='test')\n"
        "record_agent_phase(phase='merge-probe', duration=0.1)\n"
        "record_agent_phase(phase='merge-probe', duration=0.1)\n"
        "print('B')\n",
        multiproc_dir=d,
    )
    out = _run(
        "from agentkit.observability import configure, snapshot\n"
        "configure(application='merge', environment='test')\n"
        "fam = snapshot()['families']['agent_phase_duration_seconds']\n"
        "count = 0.0\n"
        "for series in fam['series']:\n"
        "    if series.get('suffix') == 'count' and series['labels'].get('phase') == 'merge-probe':\n"
        "        count = float(series['value'])\n"
        "print(count)\n",
        multiproc_dir=d,
    )
    assert float(out.strip()) == 5.0, out


def test_without_env_var_no_mmap_files_are_written(tmp_path):
    d = str(tmp_path)
    out = _run(
        "import os\n"
        "from agentkit.observability import MULTIPROCESS_MODE, configure, record_agent_phase\n"
        "configure(application='solo', environment='test')\n"
        "record_agent_phase(phase='solo-probe', duration=0.1)\n"
        f"print(MULTIPROCESS_MODE, len(os.listdir({d!r})))\n",
        multiproc_dir=None,
    )
    mode, nfiles = out.split()
    assert mode == "False"
    assert nfiles == "0"


def test_mark_worker_exit_does_not_drop_histogram_samples(tmp_path):
    """BUG WITNESS (do not 'fix' by weakening): mark_process_dead only deletes gauges.

    prometheus_client.multiprocess.mark_process_dead removes `gauge_*_{pid}.db`
    only. Our phase metric is a histogram, so mark_worker_exit() leaves the dead
    worker's samples in the merged scrape. backend.sh wiping the mmap dir on
    start is currently the only real backstop for histograms/counters.
    """
    d = str(tmp_path)
    _run(
        "from agentkit.observability import configure, record_agent_phase\n"
        "configure(application='exit', environment='test')\n"
        "record_agent_phase(phase='exit-probe', duration=0.1)\n"
        "record_agent_phase(phase='exit-probe', duration=0.1)\n"
        "print('live')\n",
        multiproc_dir=d,
    )
    _run(
        "from agentkit.observability import configure, record_agent_phase, mark_worker_exit\n"
        "configure(application='exit', environment='test')\n"
        "for _ in range(7):\n"
        "    record_agent_phase(phase='exit-probe', duration=0.1)\n"
        "mark_worker_exit()\n"
        "print('dead')\n",
        multiproc_dir=d,
    )
    out = _run(
        "from agentkit.observability import configure, snapshot\n"
        "configure(application='exit', environment='test')\n"
        "fam = snapshot()['families']['agent_phase_duration_seconds']\n"
        "count = 0.0\n"
        "for series in fam['series']:\n"
        "    if series.get('suffix') == 'count' and series['labels'].get('phase') == 'exit-probe':\n"
        "        count = float(series['value'])\n"
        "print(count)\n",
        multiproc_dir=d,
    )
    # 2 (live) + 7 (dead, still counted) = 9 — the hole this test pins.
    assert float(out.strip()) == 9.0, out


def test_mark_worker_exit_does_clear_the_inflight_gauge(tmp_path):
    """The one metric that MUST reset when a worker dies.

    `agent_turns_in_flight` answers "is a turn stuck right now". If a worker exits
    while turns are in flight, its value must stop contributing — otherwise the
    gauge reports a phantom stuck turn forever, which is the exact alarm it exists
    to raise.

    That only happens with `multiprocess_mode="livesum"`: prometheus_client's
    `mark_process_dead` deletes `gauge_live*_{pid}.db` and nothing else, so the
    default `all` mode leaves the dead worker's file in every future scrape.

    The witness of that difference is the second process below calling
    `mark_worker_exit()` before it exits: with `all` the total stays 3, with
    `livesum` it drops to 1.
    """
    d = str(tmp_path)

    # Worker A: three turns in flight, then it exits without decrementing (the
    # crash case) but does call mark_worker_exit on its way out.
    _run(
        "from agentkit.observability import configure, inflight_turn, mark_worker_exit\n"
        "configure(application='exit', environment='test')\n"
        "for _ in range(3):\n"
        "    s = inflight_turn(); s.__enter__()\n"
        "mark_worker_exit()\n"
        "print('A done')\n",
        multiproc_dir=d,
    )
    # Worker B: one turn in flight, still alive.
    _run(
        "from agentkit.observability import configure, inflight_turn\n"
        "configure(application='exit', environment='test')\n"
        "s = inflight_turn(); s.__enter__()\n"
        "print('B done')\n",
        multiproc_dir=d,
    )
    out = _run(
        "from agentkit.observability import configure, snapshot\n"
        "configure(application='exit', environment='test')\n"
        "fam = snapshot()['families']['agent_turns_in_flight']\n"
        "print(sum(float(s['value'] or 0) for s in fam['series']))\n",
        multiproc_dir=d,
    )
    # 1, not 4: A's file was removed because the gauge is livesum.
    assert float(out.strip()) == 1.0, out


def test_stale_mmap_files_from_sigkill_still_contribute(tmp_path):
    """Document current behaviour: a killed worker's files inflate the sum until cleaned.

    backend.sh emptying the directory on start is the intentional backstop.
    """
    d = str(tmp_path)
    _run(
        "from agentkit.observability import configure, record_agent_phase\n"
        "configure(application='stale', environment='test')\n"
        "record_agent_phase(phase='stale-probe', duration=0.1)\n"
        "print('w1')\n",
        multiproc_dir=d,
    )
    _run(
        "from agentkit.observability import configure, record_agent_phase\n"
        "configure(application='stale', environment='test')\n"
        "record_agent_phase(phase='stale-probe', duration=0.1)\n"
        "record_agent_phase(phase='stale-probe', duration=0.1)\n"
        "print('killed')\n",
        multiproc_dir=d,
    )
    out = _run(
        "from agentkit.observability import configure, snapshot\n"
        "configure(application='stale', environment='test')\n"
        "fam = snapshot()['families']['agent_phase_duration_seconds']\n"
        "count = 0.0\n"
        "for series in fam['series']:\n"
        "    if series.get('suffix') == 'count' and series['labels'].get('phase') == 'stale-probe':\n"
        "        count = float(series['value'])\n"
        "print(count)\n",
        multiproc_dir=d,
    )
    assert float(out.strip()) == 3.0, out
