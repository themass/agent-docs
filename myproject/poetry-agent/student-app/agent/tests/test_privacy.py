"""Logs carry metadata only. A learner's words, the key and the prompt must never reach a log record."""
from __future__ import annotations

import logging

from student_test_helpers import make_req


def test_turn_logs_contain_no_learner_text(service, caplog):
    secret = "我叫张小明我家住在幸福路"
    with caplog.at_level(logging.DEBUG):
        service.handle(make_req("arrive", "free_text", text=secret), bucket="p1")
        service.handle(make_req("recite", "evaluate_retell", text="杜甫被困在长安"), bucket="p2")
    blob = " ".join(r.getMessage() for r in caplog.records)
    assert "turn action=" in blob
    for leaked in (secret, "张小明", "幸福路", "杜甫被困在长安"):
        assert leaked not in blob


def test_the_response_to_a_pii_message_does_not_echo_it(service):
    r = service.handle(make_req("arrive", "free_text", text="我的手机号是13800138000"), bucket="p3")
    assert "13800138000" not in r.say and "13800138000" not in r.model_dump_json()


def test_text_is_truncated_before_anything_sees_it():
    from student_agent.models import TurnArgs
    assert len(TurnArgs(text="长" * 5000).text) == 400


def test_budget_buckets_hash_the_token():
    from student_agent.budget import bucket_for
    b = bucket_for("Bearer super-secret-device-key")
    assert "super-secret" not in b and len(b) == 16 and bucket_for(None) == "anon"
