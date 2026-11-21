"""Studio identity (agent_bff.auth): the server decides who is acting, never the browser.

No network and no database. Accounts live in a temporary file and the session secret is a throwaway
value. Written for the final test pass, not run during development.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from agent_bff import auth, main
from fastapi.testclient import TestClient

P = main.API_PREFIX
SECRET = "test-secret-test-secret-test-secret-0123"
EDITOR_PW, REVIEWER_PW = "correct-horse-1", "correct-horse-2"


def write_users(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps({"users": entries}), encoding="utf-8")
    stat = path.stat()
    os.utime(path, (stat.st_atime, stat.st_mtime + 5))  # the store keys its cache on mtime


def user(uid: str, role: str, password: str, name: str = "") -> dict:
    return {"id": uid, "name": name or uid, "role": role, "password_hash": auth.hash_password(password)}


@pytest.fixture
def secured(tmp_path, monkeypatch):
    users_file = tmp_path / "users.json"
    write_users(users_file, [
        user("li-editor", "CONTENT_EDITOR", EDITOR_PW),
        user("wang-reviewer", "HISTORICAL_REVIEWER", REVIEWER_PW),
    ])
    monkeypatch.setenv("POETRY_STUDIO_AUTH", "required")
    monkeypatch.setenv("POETRY_STUDIO_USERS_FILE", str(users_file))
    monkeypatch.setenv("POETRY_STUDIO_SESSION_SECRET", SECRET)
    auth.limiter._failures.clear()  # isolate the in-process lockout between tests
    client = TestClient(main.app)
    client.users_file = users_file  # type: ignore[attr-defined]
    return client


def login(client: TestClient, uid: str = "li-editor", password: str = EDITOR_PW):
    return client.post(f"{P}/auth/login", json={"user_id": uid, "password": password})


def bearer(client: TestClient, uid: str = "li-editor", password: str = EDITOR_PW) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, uid, password).json()['token']}"}


# ------------------------------------------------------------------------------ fail closed

def test_authentication_is_required_unless_explicitly_set_to_off(monkeypatch):
    monkeypatch.delenv("POETRY_STUDIO_AUTH", raising=False)
    assert auth.auth_mode() == "required"
    for value in ("", "false", "0", "no", "disabled", "OFFF"):
        monkeypatch.setenv("POETRY_STUDIO_AUTH", value)
        assert auth.auth_mode() == "required", value
    monkeypatch.setenv("POETRY_STUDIO_AUTH", " OFF ")
    assert auth.auth_mode() == "off"


def test_every_api_route_needs_a_session_but_health_and_login_do_not(secured):
    assert secured.get("/health/live").status_code == 200
    assert secured.get("/health/ready").status_code == 200
    for method, path in [("GET", "/tasks"), ("GET", "/proposals"), ("GET", "/works"), ("GET", "/sources"),
                         ("POST", "/tasks"), ("GET", "/auth/me"), ("GET", f"/proposals/proposal_{uuid4().hex}")]:
        response = secured.request(method, P + path, json={} if method == "POST" else None)
        assert response.status_code == 401, (method, path)
        assert response.json()["error"]["code"] == "AUTH_REQUIRED"
        assert response.headers["www-authenticate"] == "Bearer"


def test_preflight_requests_are_not_blocked(secured):
    response = secured.options(f"{P}/tasks", headers={"Origin": "http://localhost:5190", "Access-Control-Request-Method": "POST"})
    assert response.status_code == 200


def test_the_published_example_secret_is_never_accepted(secured, monkeypatch):
    monkeypatch.setenv("POETRY_STUDIO_SESSION_SECRET", "change-me-studio-session-secret-replace-before-use")
    assert auth.secret() is None
    assert login(secured).status_code == 503


def test_login_is_unavailable_when_accounts_or_secret_are_missing(secured, monkeypatch):
    monkeypatch.setenv("POETRY_STUDIO_SESSION_SECRET", "too-short")
    response = login(secured)
    assert response.status_code == 503 and response.json()["error"]["code"] == "AUTH_NOT_CONFIGURED"


# ---------------------------------------------------------------------------------- login

def test_a_correct_login_returns_a_token_and_the_server_side_identity(secured):
    response = login(secured, "wang-reviewer", REVIEWER_PW)
    assert response.status_code == 200
    body = response.json()
    assert body["actor"] == {"actor_id": "wang-reviewer", "role": "HISTORICAL_REVIEWER", "name": "wang-reviewer"}
    me = secured.get(f"{P}/auth/me", headers={"Authorization": f"Bearer {body['token']}"}).json()
    assert me["auth_mode"] == "required" and me["actor"]["role"] == "HISTORICAL_REVIEWER"


def test_wrong_password_and_unknown_user_are_indistinguishable(secured):
    wrong = login(secured, "li-editor", "not-the-password")
    ghost = login(secured, "no-such-user", "not-the-password")
    assert wrong.status_code == ghost.status_code == 401
    assert wrong.json() == ghost.json()
    assert wrong.json()["error"]["code"] == "LOGIN_FAILED"


def test_five_failures_lock_the_account_even_for_the_right_password(secured):
    codes = [login(secured, "li-editor", "bad-bad-bad-1").status_code for _ in range(5)]
    assert codes == [401] * 5
    locked = login(secured, "li-editor", EDITOR_PW)
    assert locked.status_code == 429 and int(locked.headers["retry-after"]) > 0


def test_a_success_clears_the_failure_count(secured):
    for _ in range(3):
        login(secured, "li-editor", "bad-bad-bad-1")
    assert login(secured).status_code == 200
    for _ in range(4):
        assert login(secured, "li-editor", "bad-bad-bad-1").status_code == 401


# ---------------------------------------------------------------------------------- tokens

def test_tampered_malformed_and_foreign_tokens_are_rejected(secured):
    token = login(secured).json()["token"]
    body, signature = token.split(".")
    for bad in (f"{body}.{signature[:-2]}ab", f"{body[:-2]}ab.{signature}", "a.b", "nodot", token + "x.y", ""):
        response = secured.get(f"{P}/auth/me", headers={"Authorization": f"Bearer {bad}"})
        assert response.status_code == 401, bad


def test_a_token_signed_with_another_secret_is_rejected(secured, monkeypatch):
    token = login(secured).json()["token"]
    monkeypatch.setenv("POETRY_STUDIO_SESSION_SECRET", "another-secret-another-secret-another-0")
    assert secured.get(f"{P}/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_an_expired_token_is_rejected(secured, monkeypatch):
    monkeypatch.setattr(auth, "SESSION_TTL_SECONDS", -10)
    token = login(secured).json()["token"]
    assert secured.get(f"{P}/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_removing_an_account_or_changing_its_role_takes_effect_immediately(secured):
    headers = bearer(secured)
    assert secured.get(f"{P}/auth/me", headers=headers).status_code == 200
    write_users(secured.users_file, [user("li-editor", "RELEASE_MANAGER", EDITOR_PW)])
    assert secured.get(f"{P}/auth/me", headers=headers).status_code == 401  # role no longer matches the token
    write_users(secured.users_file, [])
    assert secured.get(f"{P}/auth/me", headers=headers).status_code == 401


def test_an_invalid_account_entry_is_skipped_not_trusted(secured):
    write_users(secured.users_file, [
        {"id": "ok-user", "role": "NOT_A_ROLE", "password_hash": auth.hash_password("whatever-1234")},
        {"id": "x", "role": "CONTENT_EDITOR", "password_hash": auth.hash_password("whatever-1234")},
        {"id": "plain-user", "role": "CONTENT_EDITOR", "password_hash": "plaintext-password"},
    ])
    assert auth.users.count() == 0


# --------------------------------------------------------------------- identity not from body

def test_a_body_actor_that_disagrees_with_the_session_is_rejected(secured):
    headers = bearer(secured)  # an editor
    body = {"actor": {"actor_id": "li-editor", "role": "HISTORICAL_REVIEWER"}, "locator": "卷二百二十五"}
    response = secured.put(f"{P}/sources/citations/claim-a/src-a/locator", json=body, headers=headers)
    assert response.status_code == 403 and response.json()["error"]["code"] == "ACTOR_MISMATCH"
    other = {"actor": {"actor_id": "wang-reviewer", "role": "CONTENT_EDITOR"}, "locator": "卷二百二十五"}
    assert secured.put(f"{P}/sources/citations/claim-a/src-a/locator", json=other, headers=headers).status_code == 403


def test_the_role_comes_from_the_account_so_an_editor_cannot_enter_locators(secured):
    headers = bearer(secured)
    response = secured.put(f"{P}/sources/citations/claim-a/src-a/locator", json={"locator": "卷二百二十五"}, headers=headers)
    assert response.status_code == 403 and response.json()["error"]["code"] == "SOURCE_REVIEW_ROLE_REQUIRED"
    verify = secured.post(f"{P}/sources/src-a/verification", json={"decision": "VERIFY"}, headers=headers)
    assert verify.status_code == 403


def test_the_signed_in_account_is_what_gets_recorded_as_the_requester(secured, monkeypatch):
    sent = {}

    class Domain:
        def create_task(self, payload):
            sent.update(payload)
            return {"status": "OK", "data": {
                **payload, "task_id": payload["task_id"], "status": "CREATED", "active_run_id": None,
                "created_at": "2026-11-06T10:00:00", "updated_at": None}}

    monkeypatch.setattr(main, "domain_control", Domain())
    body = {"work_id": "work-chun-wang", "title": "缺口分析", "task_type": "GAP_ANALYSIS", "instructions": "看一下"}
    response = secured.post(f"{P}/tasks", json=body, headers=bearer(secured, "wang-reviewer", REVIEWER_PW))
    assert response.status_code == 201
    assert sent["requested_by"] == "wang-reviewer" and sent["requested_role"] == "HISTORICAL_REVIEWER"


def test_with_auth_off_the_body_actor_is_required_and_trusted(monkeypatch):
    monkeypatch.setenv("POETRY_STUDIO_AUTH", "off")
    client = TestClient(main.app)
    body = {"work_id": "work-chun-wang", "title": "缺口分析", "task_type": "GAP_ANALYSIS", "instructions": "看一下"}
    response = client.post(f"{P}/tasks", json=body)
    assert response.status_code == 422 and response.json()["error"]["code"] == "ACTOR_REQUIRED"
    me = client.get(f"{P}/auth/me").json()
    assert me["auth_mode"] == "off" and me["actor"] is None and "离线演示" in me["warning"]
    assert client.post(f"{P}/auth/login", json={"user_id": "li-editor", "password": "x"}).status_code == 409


# --------------------------------------------------------------------------- event tickets

def test_an_events_ticket_is_scoped_to_one_run_and_one_purpose(secured):
    headers = bearer(secured)
    run_a, run_b = f"run_{uuid4().hex}", f"run_{uuid4().hex}"
    ticket = secured.post(f"{P}/auth/events-ticket/{run_a}", headers=headers).json()["ticket"]
    assert auth.identity_from_ticket(ticket, run_a) is not None
    assert auth.identity_from_ticket(ticket, run_b) is None  # another run
    assert auth.identity_from_session(ticket) is None  # a ticket is not a session
    session = headers["Authorization"].removeprefix("Bearer ")
    assert auth.identity_from_ticket(session, run_a) is None  # a session is not a ticket


def test_a_ticket_only_opens_the_events_route_of_its_own_run(secured, monkeypatch):
    run_a, run_b = f"run_{uuid4().hex}", f"run_{uuid4().hex}"
    ticket = secured.post(f"{P}/auth/events-ticket/{run_a}", headers=bearer(secured)).json()["ticket"]

    class Domain:
        def get_run(self, run_id):
            raise main.DomainControlError("run not found")

    monkeypatch.setattr(main, "domain_control", Domain())
    assert secured.get(f"{P}/runs/{run_b}/events?ticket={ticket}").status_code == 401
    assert secured.get(f"{P}/runs/{run_a}/events").status_code == 401
    assert secured.get(f"{P}/runs/{run_a}/budget?ticket={ticket}").status_code == 401  # not an events route
    # 403/503, not the 404 this line used to expect: review item A-15 made every domain lookup failure
    # collapse into one fixed 503, because a 404 that distinguishes "missing" from "unavailable" leaks
    # upstream state through the bridge. What matters here is "authenticated but not served".
    assert secured.get(f"{P}/runs/{run_a}/events?ticket={ticket}").status_code == 503  # authenticated, run missing


def test_an_expired_ticket_is_rejected(secured, monkeypatch):
    monkeypatch.setattr(auth, "TICKET_TTL_SECONDS", -5)
    run = f"run_{uuid4().hex}"
    ticket = secured.post(f"{P}/auth/events-ticket/{run}", headers=bearer(secured)).json()["ticket"]
    assert auth.identity_from_ticket(ticket, run) is None


# ------------------------------------------------------------------------------ passwords

def test_password_hashes_are_salted_verifiable_and_never_the_password():
    first, second = auth.hash_password("correct-horse-1"), auth.hash_password("correct-horse-1")
    assert first != second and "correct-horse-1" not in first
    assert auth.verify_password("correct-horse-1", first) and not auth.verify_password("correct-horse-2", first)
    for broken in ("", "scrypt$1$2", "md5$a$b$c$d$e", "scrypt$x$y$z$a$b"):
        assert auth.verify_password("correct-horse-1", broken) is False


def test_the_users_cli_writes_a_private_file_with_hashes_only(tmp_path, monkeypatch):
    from agent_bff import users as cli

    path = tmp_path / "out" / "users.json"
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "a-long-password-1")
    assert cli.main(["add", "--file", str(path), "--id", "wang-reviewer", "--role", "HISTORICAL_REVIEWER"]) == 0
    text = path.read_text(encoding="utf-8")
    assert "a-long-password-1" not in text and "scrypt$" in text
    assert (path.stat().st_mode & 0o777) == 0o600
    assert cli.main(["remove", "--file", str(path), "--id", "wang-reviewer"]) == 0
    assert json.loads(path.read_text(encoding="utf-8"))["users"] == []
