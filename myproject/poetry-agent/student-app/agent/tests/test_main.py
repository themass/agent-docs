from __future__ import annotations

import dataclasses

import httpx
from fastapi.testclient import TestClient
from student_agent.config import Settings
from student_agent.main import API_PREFIX, create_app

S = dataclasses.replace(Settings(), mode_override="script", source="fixture", auth="none")
BODY = {"bundle_hash": "60279d333becba38e65414e58d433ee58235acb08841277ddf7d62a598f91d11", "work_id": "work-chun-wang",
        "step": "arrive", "action": "open_layer", "args": {"layer": "CITY"}}


def test_health_leaks_nothing():
    r = TestClient(create_app(S)).get(f"{API_PREFIX}/health")
    assert r.status_code == 200
    assert set(r.json()) == {"status", "mode", "primary_configured", "source"}


def test_turn_returns_a_scripted_answer_with_no_configuration_at_all():
    r = TestClient(create_app(S)).post(f"{API_PREFIX}/turn", json=BODY)
    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "narrator" and data["source"] == "script" and data["basis"]


def test_invalid_requests_are_422_not_500():
    c = TestClient(create_app(S))
    assert c.post(f"{API_PREFIX}/turn", json={**BODY, "action": "chat"}).status_code == 422
    assert c.post(f"{API_PREFIX}/turn", json={**BODY, "step": "quiz"}).status_code == 422
    assert c.post(f"{API_PREFIX}/turn", json={**BODY, "bundle_hash": "../etc"}).status_code == 422
    assert c.post(f"{API_PREFIX}/turn", json={**BODY, "work_id": "a b"}).status_code == 422


def test_java_auth_mode_rejects_unknown_devices(monkeypatch):
    s = dataclasses.replace(S, auth="java", java_base="http://java.invalid")

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url, headers=None):
            return httpx.Response(200 if headers["Authorization"] == "Bearer good-key-good-key-good" else 401)

    monkeypatch.setattr("student_agent.main.httpx.Client", FakeClient)
    c = TestClient(create_app(s))
    assert c.post(f"{API_PREFIX}/turn", json=BODY).status_code == 401
    assert c.post(f"{API_PREFIX}/turn", json=BODY, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert c.post(f"{API_PREFIX}/turn", json=BODY, headers={"Authorization": "Bearer good-key-good-key-good"}).status_code == 200


def test_java_source_only_asks_for_full_hashes():
    import pytest
    from student_agent.sources import JavaSource, SourceError
    seen = []
    src = JavaSource("http://java.invalid", transport=httpx.MockTransport(lambda r: seen.append(str(r.url)) or httpx.Response(200, json={})))
    with pytest.raises(SourceError):
        src.bundle("../../etc/passwd")
    assert seen == []
