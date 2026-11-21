"""Shared fixtures for the BFF tests.

Studio authentication is **required** by default (see ``agent_bff.auth``). Most tests exercise route
behaviour and send an ``actor`` in the body, so they run with authentication off; the tests that
exercise authentication itself (``test_bff_auth.py``) switch it back on explicitly.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _studio_auth_off_by_default(monkeypatch):
    monkeypatch.setenv("POETRY_STUDIO_AUTH", "off")
