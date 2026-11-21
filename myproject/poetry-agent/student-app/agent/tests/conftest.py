"""Shared fixtures. Everything runs offline against the demo files; no network, no model, no database."""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest
from student_agent.config import AGENT_ROOT, APP_ROOT, Settings
from student_agent.lesson import build_context, clear_sidecar_cache, load_sidecar
from student_agent.service import TurnService

# pytest runs with --import-mode=importlib, which does not put this directory on sys.path.
sys.path.insert(0, str(Path(__file__).parent))
from student_test_helpers import HASH, WORK

CONTRACTS = APP_ROOT / "runtime" / "contracts"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _fresh_sidecar_cache():
    clear_sidecar_cache()


@pytest.fixture()
def bundle():
    return read(CONTRACTS / "sample.chun-wang.json")


@pytest.fixture()
def pack():
    return read(CONTRACTS / "demo" / "pack.chun-wang.json")


@pytest.fixture()
def ctx(bundle, pack):
    return build_context(bundle, pack, load_sidecar(AGENT_ROOT / "data" / "lessons", WORK), WORK, HASH)


@pytest.fixture()
def script_settings():
    return dataclasses.replace(Settings(), mode_override="script", source="fixture")


@pytest.fixture()
def service(script_settings):
    return TurnService(script_settings)

