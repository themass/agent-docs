"""agent-bff forwards task/run/proposal ids from the browser into URLs on the domain-control bridge.

Ids are always minted by this service as "<prefix>_<uuid4 hex>". Anything else must be rejected at
the route (422) before any outbound call is made. The domain-control client is replaced by a stub
that fails the test if it is ever reached for an invalid id.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from agent_bff import main
from agent_bff.domain_control import DomainControlError
from fastapi.testclient import TestClient

P = main.API_PREFIX


class Unreachable:
    """Any attribute access means the route let an invalid id through to the bridge."""

    def __getattr__(self, name):
        raise AssertionError(f"domain_control.{name} was called for an invalid id")


class NotFound:
    def get_task(self, task_id):
        raise DomainControlError("task not found")

    def get_run(self, run_id):
        raise DomainControlError("run not found")

    def get_proposal(self, proposal_id):
        raise DomainControlError("proposal not found")


# POST /runs/{id}/proposals no longer exists: proposals are written only by agent-worker through the
# control bridge, so an unauthenticated browser-reachable ingress would be an injection path.
ROUTES = [
    ("GET", "/tasks/{id}", "task"),
    ("GET", "/tasks/{id}/runs", "task"),
    ("POST", "/tasks/{id}/run", "task"),
    ("GET", "/runs/{id}", "run"),
    ("GET", "/runs/{id}/events", "run"),
    ("GET", "/runs/{id}/budget", "run"),
    ("POST", "/runs/{id}/cancel", "run"),
    ("GET", "/proposals/{id}", "proposal"),
    ("GET", "/proposals/{id}/diff", "proposal"),
    ("POST", "/proposals/{id}/review", "proposal"),
    ("POST", "/proposals/{id}/apply", "proposal"),
]

# Percent-encoded so the client cannot normalise them away; the server sees "?", " ", ".." etc.
BAD_SUFFIXES = ["x%3Fadmin%3D1", "x%20y", "..", "", "x%23frag", "x%0Ay"]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "domain_control", Unreachable())
    return TestClient(main.app)


@pytest.mark.parametrize("method,template,kind", ROUTES)
@pytest.mark.parametrize("suffix", BAD_SUFFIXES)
def test_malformed_ids_are_rejected_before_reaching_the_bridge(client, method, template, kind, suffix):
    path = P + template.format(id=f"{kind}_{suffix}")
    response = client.request(method, path, json={})
    assert response.status_code == 422, f"{method} {path} -> {response.status_code}"


@pytest.mark.parametrize("method,template,kind", ROUTES)
def test_an_id_of_the_wrong_kind_is_rejected(client, method, template, kind):
    other = {"task": "run", "run": "proposal", "proposal": "task"}[kind]
    path = P + template.format(id=f"{other}_{uuid4().hex}")
    assert client.request(method, path, json={}).status_code == 422


@pytest.mark.parametrize(
    "template,kind,expected",
    [("/tasks/{id}", "task", "task"), ("/runs/{id}", "run", "run"), ("/proposals/{id}", "proposal", "proposal")],
)
def test_a_minted_id_passes_validation_and_reaches_the_bridge(monkeypatch, template, kind, expected):
    monkeypatch.setattr(main, "domain_control", NotFound())
    response = TestClient(main.app).get(P + template.format(id=f"{kind}_{uuid4().hex}"))
    # What this test guards is "a well-formed id gets past route validation and actually reaches the
    # bridge". It used to assert 404, but review item A-15 collapsed every domain failure into one
    # fixed 503 so that "missing" and "unavailable" cannot be told apart through the bridge.
    assert response.status_code in (404, 503), response.text
    if response.status_code == 404:
        assert expected in response.text.lower()
    else:
        assert "UNAVAILABLE" in response.text
