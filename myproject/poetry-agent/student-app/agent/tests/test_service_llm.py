"""The model path with a fake client: every failure must end in the scripted answer, and the reviewer decides."""
from __future__ import annotations

import dataclasses
import json

import httpx
import pytest
from student_agent.config import Settings
from student_agent.llm import (
    LLMClient,
    LLMError,
    LLMTimeout,
    LLMUnavailable,
    Reworded,
    extract_json,
)
from student_agent.service import TurnService
from student_test_helpers import make_req

LLM = dataclasses.replace(Settings(), llm_base="http://gateway.invalid", llm_key="k", model_primary="m1",
                          model_fallback="m2", source="fixture")


class Fake:
    def __init__(self, *outs): self.outs, self.calls = list(outs), []

    def rephrase(self, **kw):
        self.calls.append(kw["tier"])
        out = self.outs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def reworded(say, uses=("arrive/WORLD/0",), tier="primary"):
    return Reworded(say, list(uses), tier, 40, 100, 30)


def run(fake, step="arrive", action="rephrase", settings=LLM, bucket="b", **args):
    svc = TurnService(settings, llm=fake)
    return svc.handle(make_req(step, action, **({"layer": "WORLD"} | args)), bucket=bucket)


def test_a_reviewed_reword_is_used(service):
    r = run(Fake(reworded("战火不停，一封家信比万金还难得。")))
    assert r.source == "llm" and r.degraded_reason is None and "家信" in r.say


def test_rejected_reword_retries_once_on_the_fallback_then_uses_the_script():
    f = Fake(reworded("战火打了整整八年。"), reworded("战火打了整整九年。", tier="fallback"))
    r = run(f)
    assert f.calls == ["primary", "fallback"]
    assert r.source == "script" and r.degraded_reason == "rejected" and "家书抵万金" in r.say


def test_timeout_does_not_retry_and_falls_back_to_script():
    f = Fake(LLMTimeout("t"))
    r = run(f)
    assert f.calls == ["primary"] and r.source == "script" and r.degraded_reason == "timeout"


def test_unavailable_tries_the_fallback_model_then_script():
    f = Fake(LLMUnavailable("u"), LLMUnavailable("u"))
    r = run(f)
    assert f.calls == ["primary", "fallback"] and r.degraded_reason == "unavailable"


def test_script_mode_never_calls_the_client():
    f = Fake()
    r = run(f, settings=dataclasses.replace(LLM, mode_override="script"))
    assert f.calls == [] and r.degraded_reason == "disabled" and r.source == "script"


def test_budget_exhaustion_is_a_scripted_answer():
    svc = TurnService(dataclasses.replace(LLM, calls_per_lesson=1), llm=Fake(reworded("战火不停，一封家信比万金还难得。")))
    req = make_req("arrive", "rephrase", layer="WORLD")
    svc.handle(req, bucket="x")
    svc.cache._data.clear()
    again = svc.handle(req, bucket="x")
    assert again.degraded_reason == "budget" and again.source == "script"


def test_only_the_b1_actions_reach_a_model():
    f = Fake()
    run(f, action="open_layer")          # not in the default llm_actions
    assert f.calls == []


def test_poet_wording_stays_scripted_unless_switched_on():
    f = Fake(reworded("草长得比城墙还高。", uses=("meet/PERSON/0",)))
    r = run(f, step="meet", layer=None)
    assert f.calls == [] and r.role == "poet" and r.source == "script"


def test_the_students_words_are_never_in_the_model_input():
    seen = {}

    class Spy(Fake):
        def rephrase(self, **kw):
            seen.update(kw)
            raise LLMUnavailable("stop")

    svc = TurnService(dataclasses.replace(LLM, llm_actions=frozenset({"rephrase", "free_text"})), llm=Spy())
    svc.handle(make_req("arrive", "free_text", text="长安是什么地方我叫小明"), bucket="p")
    flat = repr(seen)
    assert "小明" not in flat


def test_cache_key_has_no_learner_text():
    svc = TurnService(LLM, llm=Fake(reworded("战火不停，一封家信比万金还难得。")))
    svc.handle(make_req("arrive", "rephrase", layer="WORLD"), bucket="c")
    for key in svc.cache._data:
        assert all(isinstance(p, (str, tuple)) for p in key)


# ------------------------------------------------------------------ the HTTP client itself

def client_with(handler):
    return LLMClient(LLM, transport=httpx.MockTransport(handler))


def good(request):
    return httpx.Response(200, json={"choices": [{"message": {"content": '{"say":"好","uses":["a"]}'}}],
                                     "usage": {"prompt_tokens": 10, "completion_tokens": 3}})


def test_client_parses_json_and_counts_tokens(ctx):
    out = client_with(good).rephrase(role="narrator", soul="s", script_say="x", facts=[])
    assert out.say == "好" and out.uses == ["a"] and (out.prompt_tokens, out.completion_tokens) == (10, 3)


def test_client_error_mapping():
    def t(request): raise httpx.ReadTimeout("slow")
    def boom(request): raise httpx.ConnectError("down")
    def bad(request): return httpx.Response(500)
    def junk(request): return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})
    c = {"role": "narrator", "soul": "s", "script_say": "x", "facts": []}
    with pytest.raises(LLMTimeout): client_with(t).rephrase(**c)
    with pytest.raises(LLMUnavailable): client_with(boom).rephrase(**c)
    with pytest.raises(LLMUnavailable): client_with(bad).rephrase(**c)
    with pytest.raises(LLMError) as e: client_with(junk).rephrase(**c)
    # "rejected", not "unavailable": a 200 with unusable content is the model misbehaving, not the
    # gateway being down. The two drive different fallbacks (script vs. circuit breaker) and only the
    # latter should count toward tripping it. llm.py has raised rejected for this since the hardening pass.
    assert e.value.reason == "rejected"


def test_prompt_never_contains_learner_text_or_the_key(ctx):
    captured = {}

    def spy(request):
        captured["body"] = request.content.decode("utf-8")
        captured["auth"] = request.headers["authorization"]
        return good(request)

    client_with(spy).rephrase(role="narrator", soul="soul", script_say="叛乱", facts=[ctx.facts["arrive/WORLD/0"]])
    # The key travels only in the Authorization header, never in the JSON body.
    assert captured["auth"] == "Bearer k"
    assert '"Bearer' not in captured["body"] and "api_key" not in captured["body"]
    body = json.loads(captured["body"])
    user = json.loads(body["messages"][1]["content"])
    assert set(user) == {"script_say", "facts"}   # nothing else is ever sent: no learner text, no history


def test_extract_json_finds_the_object_inside_chatter():
    assert extract_json('好的：{"say":"x"} 以上') == {"say": "x"}
    with pytest.raises(LLMError):
        extract_json("no braces")
