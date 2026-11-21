from __future__ import annotations

from student_agent.evaluator import BANNED_WORDS, evaluate, normalize


def test_full_retell_covers_everything_and_needs_no_supplement(ctx):
    ev, used = evaluate("杜甫被困在长安，那时候在打仗，春天看见花和鸟很伤心，想念家人收不到家书", ctx)
    assert sorted(ev.covered) == ["p-era", "p-home", "p-place", "p-trigger"]
    assert ev.missing == [] and ev.supplement == [] and used == []


def test_partial_retell_names_what_is_missing_and_quotes_the_bundle_verbatim(ctx):
    ev, used = evaluate("他想念家人", ctx)
    assert ev.covered == ["p-home"]
    assert set(ev.missing) == {"p-era", "p-place", "p-trigger"}
    assert len(ev.supplement) == 2  # capped
    for sup in ev.supplement:
        fact = ctx.facts[sup.basis[0].id]
        assert sup.say == fact.text  # verbatim, never model-written
    assert {f.id for f in used} == {s.basis[0].id for s in ev.supplement}


def test_empty_retell_is_not_reported_as_everything_missing(ctx):
    ev, used = evaluate("   ", ctx)
    assert ev.covered == [] and ev.missing == [] and used == []
    assert ev.summary


def test_no_score_no_verdict_anywhere_in_the_output(ctx):
    for text in ("", "不知道", "他想念家人", "杜甫被困在长安，打仗，春天看见花鸟，想念家人家书"):
        ev, _ = evaluate(text, ctx)
        dumped = ev.model_dump_json()
        for word in BANNED_WORDS:
            assert word not in dumped, (text, word)
        assert "score" not in dumped and "grade" not in dumped


def test_traditional_characters_and_punctuation_are_normalised():
    assert normalize("長安！陷。") == normalize("长安 陷")


def test_supplement_whose_ref_left_the_bundle_is_dropped_not_invented(bundle, pack):
    from student_agent.lesson import build_context
    side = {"points": [{"id": "p-x", "label": "x", "any_of": ["zzz"], "supplement_ref": "arrive/NOPE/9"}]}
    c = build_context(bundle, pack, side, "work-chun-wang", "h")
    assert any("not in bundle" in w for w in c.warnings)
    ev, used = evaluate("随便说点什么", c)
    assert ev.missing == ["p-x"] and ev.supplement == [] and used == []
