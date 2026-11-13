"""回合判定与队列转移的纯规则（D §6.1、§3.3）。"""

import pytest

from companion.db.port import QUEUE_TRANSITIONS
from companion.service.turn.queue import (
    DRAIN_BATCH_SIZE,
    DRAIN_MAX_ATTEMPTS,
    Disposition,
    TurnPhase,
    decide,
)


def d(**kw):
    base = dict(lock_held=True, phase=TurnPhase.PRE_OUTPUT, restarts=0, max_restarts=2,
                steerable=True, steer_used=0, steer_budget=3)
    base.update(kw)
    return decide(**base)


def test_no_lock_means_started():
    assert d(lock_held=False) is Disposition.STARTED


def test_before_first_token_a_new_message_merges():
    assert d(phase=TurnPhase.PRE_OUTPUT) is Disposition.MERGED


def test_merge_stops_after_max_restarts():
    assert d(phase=TurnPhase.PRE_OUTPUT, restarts=2) is Disposition.QUEUED


def test_output_phase_steers_when_steerable_and_within_budget():
    assert d(phase=TurnPhase.OUTPUT) is Disposition.STEERED
    assert d(phase=TurnPhase.OUTPUT, steer_used=3) is Disposition.QUEUED
    assert d(phase=TurnPhase.OUTPUT, steerable=False) is Disposition.QUEUED


def test_tool_phase_never_merges_or_steers():
    assert d(phase=TurnPhase.TOOL) is Disposition.QUEUED


@pytest.mark.parametrize("pair", [("queued", "draining"), ("draining", "drained"), ("queued", "withdrawn"),
                                  ("steered", "queued"), ("draining", "failed"), ("failed", "queued")])
def test_allowed_queue_transitions(pair):
    assert pair in QUEUE_TRANSITIONS


@pytest.mark.parametrize("pair", [("drained", "queued"), ("withdrawn", "queued"), ("queued", "drained")])
def test_illegal_queue_transitions_are_refused(pair):
    assert pair not in QUEUE_TRANSITIONS


def test_drain_limits():
    assert DRAIN_BATCH_SIZE == 10
    assert DRAIN_MAX_ATTEMPTS == 3
