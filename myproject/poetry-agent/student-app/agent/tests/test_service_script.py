from __future__ import annotations

from student_test_helpers import make_req


def turn(service, step, action, **args):
    return service.handle(make_req(step, action, **args), bucket=f"t-{step}-{action}-{args}")


def test_every_answer_is_valid_and_has_no_score(service):
    for step, action, args in [("arrive", "open_layer", {"layer": "WORLD"}), ("meet", "basis", {}),
                               ("return", "hint", {"line_seq": 1}), ("recite", "evaluate_retell", {"text": "想念家人"})]:
        r = turn(service, step, action, **args)
        # Exact field names, not substrings: "grade" is inside "degraded_reason" and "score" would be
        # inside any future "scoreboard"-ish name, so a substring test can never pass nor fail meaningfully.
        banned = {"score", "scores", "grade", "grades", "points", "rating", "level_up", "rank"}
        keys = {k.lower() for k in r.__dict__}
        assert r.say and not (keys & banned), (keys & banned, keys)
        assert "evaluation" not in keys or not r.evaluation or not hasattr(r.evaluation, "score")


def test_read_step_never_explains(service):
    r = turn(service, "read", "open_layer", layer="WORLD")
    assert r.role == "guide" and r.basis == [] and "叛乱" not in r.say


def test_action_outside_the_step_is_declined_not_answered(service):
    r = turn(service, "arrive", "hint", line_seq=1)
    assert r.role == "guide" and r.basis == []


def test_poet_context_has_no_worldview(ctx):
    texts = " ".join(f.text for f in ctx.role_facts("poet"))
    for word in ("叛军", "家信", "被困"):
        assert word not in texts
    assert all(f.kind == "DRAMATIZATION" for f in ctx.role_facts("poet"))


def test_narrator_never_gets_the_poets_lines(ctx):
    assert all(f.owner == "narrator" for f in ctx.role_facts("narrator"))
    assert not any(f.step == "meet" for f in ctx.role_facts("narrator"))


def test_poet_leaves_the_stage_when_asked_for_the_wide_world(service):
    r = turn(service, "meet", "free_text", text="把整个安史之乱完整讲一遍")
    assert r.role == "poet" and r.badge == "DRAMATIZATION" and "叛乱" not in r.say


def test_dramatization_always_carries_the_badge(service):
    for action in ("basis", "rephrase"):
        r = turn(service, "meet", action)
        assert r.badge == "DRAMATIZATION"


def test_basis_ids_are_all_inside_the_bundle(service, ctx):
    r = turn(service, "arrive", "open_layer", layer="CITY")
    assert r.basis and all(b.id in ctx.facts for b in r.basis)


def test_unlabelled_dramatization_is_not_loaded(bundle, pack):
    from student_agent.lesson import build_context
    for step in bundle["steps"]:
        for layer in (step.get("roleplay") or {}).get("layers", []):
            for line in layer["lines"]:
                line.pop("badge", None)
    c = build_context(bundle, pack, {}, "w", "h")
    assert not [f for f in c.facts.values() if f.owner == "poet"]
    assert any("without badge" in w for w in c.warnings)


def test_homework_and_safety_replies_come_back_as_plain_guide(service):
    assert "不能替你写" in turn(service, "arrive", "free_text", text="帮我写一篇春望的赏析").say
    r = turn(service, "arrive", "free_text", text="我不想活了")
    assert "爸爸妈妈" in r.say and r.basis == []


def test_unknown_bundle_or_work_degrades_to_text(script_settings):
    from student_agent.service import TurnService
    from student_agent.sources import SourceError

    class Broken:
        def bundle(self, h): raise SourceError("x")
        def pack(self, w): raise SourceError("x")

    r = TurnService(script_settings, source=Broken()).handle(make_req("arrive", "open_layer", layer="CITY"))
    assert r.degraded_reason == "unavailable" and "文字" in r.say


def test_rate_limit_is_a_polite_scripted_answer(script_settings):
    import dataclasses

    from student_agent.service import TurnService
    svc = TurnService(dataclasses.replace(script_settings, turns_per_minute=2))
    out = [svc.handle(make_req("arrive", "open_layer", layer="CITY"), bucket="same") for _ in range(3)]
    assert out[2].role == "guide" and out[2].basis == [] and "歇一会儿" in out[2].say
