"""HTTP surface (contract section 8): token check, idempotent dispatch, cancel, health."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from agent_worker.app import create_app
from agent_worker.control import ControlClient
from agent_worker.deerflow.client import DeerFlowClient, DeerFlowConfig
from fastapi.testclient import TestClient
from helpers import (
    MANDATE_ID,
    RUN_ID,
    TASK_ID,
    WORK_ID,
    WORKER_TOKEN,
    FakeBridge,
    FakeDeerFlow,
    HoldExecutor,
    make_runner,
    make_settings,
)

AUTH = {"X-Poetry-Worker-Token": WORKER_TOKEN}


def body(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "run_id": RUN_ID, "task_id": TASK_ID, "mandate_id": MANDATE_ID, "work_id": WORK_ID, "task_type": "GAP_ANALYSIS",
        "instructions": "请看看缺口", "runtime": "STUB", "profile_fingerprint": "f" * 64, "actor_role": "CONTENT_EDITOR",
    }
    base.update(over)
    return base


def make_client(bridge: FakeBridge | None = None, *, df: FakeDeerFlow | None = None, executor: object = None,
                **settings: object) -> tuple[TestClient, FakeBridge]:
    bridge = bridge or FakeBridge()
    cfg = make_settings(**settings)
    runner = make_runner(bridge, df, executor=executor, **settings)
    control = ControlClient("http://bridge", "control-test-token", transport=bridge.transport(), sleep=lambda s: None)
    df_client = DeerFlowClient(DeerFlowConfig("http://df"), transport=df.transport()) if df else None
    return TestClient(create_app(cfg, runner, control, df_client)), bridge


def test_token_is_required_and_compared_exactly() -> None:
    client, bridge = make_client()
    assert client.post("/internal/dispatch", json=body()).status_code == 401
    assert client.post("/internal/dispatch", json=body(), headers={"X-Poetry-Worker-Token": "wrong"}).status_code == 401
    assert client.post("/internal/dispatch", json=body(), headers={"X-Poetry-Worker-Token": ""}).status_code == 401
    assert client.post(f"/internal/runs/{RUN_ID}/cancel").status_code == 401
    assert bridge.requests == []                                     # nothing happened


def test_an_unconfigured_worker_token_fails_closed() -> None:
    client, bridge = make_client(worker_token="")
    for headers in ({}, AUTH, {"X-Poetry-Worker-Token": ""}):
        assert client.post("/internal/dispatch", json=body(), headers=headers).status_code == 503
    assert bridge.requests == []


def test_dispatch_is_accepted_then_a_repeat_is_a_duplicate() -> None:
    client, bridge = make_client()
    first = client.post("/internal/dispatch", json=body(), headers=AUTH)
    assert (first.status_code, first.json()) == (202, {"accepted": True})
    assert bridge.states[-1][0] == "AWAITING_REVIEW" and len(bridge.proposals) == 1
    second = client.post("/internal/dispatch", json=body(), headers=AUTH)
    assert (second.status_code, second.json()) == (200, {"accepted": True, "duplicate": True})
    assert bridge.proposal_posts == 1


@pytest.mark.parametrize("bad", [
    {"run_id": "run_../x"}, {"run_id": "x"}, {"mandate_id": "m"}, {"work_id": "Work Chun"}, {"work_id": "../w"},
    {"task_type": "PUBLISH"}, {"runtime": "OPENAI"}, {"actor_role": "ROOT"}, {"instructions": "x" * 8001},
    {"surprise": 1},
])
def test_invalid_dispatch_bodies_are_rejected_before_any_work(bad: dict[str, object]) -> None:
    client, bridge = make_client()
    assert client.post("/internal/dispatch", json=body(**bad), headers=AUTH).status_code == 422
    assert bridge.requests == []


def test_all_four_actor_roles_are_accepted() -> None:
    for role in ("CONTENT_EDITOR", "HISTORICAL_REVIEWER", "RELEASE_MANAGER", "PLATFORM_ADMIN"):
        client, _ = make_client()
        assert client.post("/internal/dispatch", json=body(actor_role=role), headers=AUTH).status_code == 202


def test_a_full_worker_answers_429() -> None:
    client, _ = make_client(executor=HoldExecutor(), max_concurrent_runs=1, queue_limit=0)
    assert client.post("/internal/dispatch", json=body(), headers=AUTH).status_code == 202
    other = body(run_id="run_" + "b" * 32)
    assert client.post("/internal/dispatch", json=other, headers=AUTH).status_code == 429


def test_cancel_validates_the_id_and_reports_the_outcome() -> None:
    client, bridge = make_client(executor=HoldExecutor())
    assert client.post("/internal/runs/not-a-run/cancel", headers=AUTH).status_code == 422
    client.post("/internal/dispatch", json=body(), headers=AUTH)
    ok = client.post(f"/internal/runs/{RUN_ID}/cancel", headers=AUTH)
    assert ok.status_code == 200 and ok.json() == {"run_id": RUN_ID, "cancelled": True, "state": "CANCELLED"}
    assert bridge.event_types() == ["RUN_CANCELLED"]


def test_liveness_needs_no_token_and_exposes_nothing() -> None:
    client, _ = make_client()
    response = client.get("/health/live")
    assert response.status_code == 200 and response.json() == {"status": "ok", "service": "agent-worker"}


def test_readiness_reports_the_bridge_deerflow_and_active_runs_without_secrets() -> None:
    df = FakeDeerFlow()
    client, _ = make_client(df=df)
    data = client.get("/health/ready").json()
    assert data["status"] == "ready" and data["active_runs"] == 0
    assert data["control_bridge"] == {"configured": True, "reachable": True}
    assert data["deerflow"] == {"enabled": True, "reachable": True, "circuit": "closed"}
    text = json.dumps(data)
    for secret in (WORKER_TOKEN, "control-test-token"):
        assert secret not in text
    assert not any("llm" in key.lower() or "model" in key.lower() for key in data)    # the worker reports no LLM config
    df.health_status = 503
    assert client.get("/health/ready").json()["deerflow"]["reachable"] is False


def test_readiness_when_deerflow_is_disabled_and_when_the_bridge_is_down() -> None:
    client, _ = make_client(deerflow_enabled=False)
    data = client.get("/health/ready").json()
    assert data["deerflow"] == {"enabled": False, "reachable": False, "circuit": "n/a"} and data["status"] == "ready"
    bridge = FakeBridge()
    bridge.fail_next("GET", r"/internal/works$", [503, 503])
    bridge.studio_view_404 = False
    client, _ = make_client(bridge)
    data = client.get("/health/ready").json()
    assert data["status"] == "not_ready" and data["control_bridge"] == {"configured": True, "reachable": False}


def test_readiness_when_the_bridge_is_not_configured() -> None:
    cfg = make_settings(control_url="", control_token="")
    runner = make_runner(FakeBridge())
    control = ControlClient("", "")
    data = TestClient(create_app(cfg, runner, control, None)).get("/health/ready").json()
    assert data["control_bridge"] == {"configured": False, "reachable": False} and data["status"] == "not_ready"


def test_the_app_module_is_the_entrypoint() -> None:
    import agent_worker.app as module
    from agent_worker import health

    assert callable(module.run) and callable(health.main)
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert 'if __name__ == "__main__"' in source and "uvicorn.run" in source
