from __future__ import annotations

import pytest
from student_agent.reviewer import review


def facts(ctx, *ids):
    return [ctx.facts[i] for i in ids]


def ok(ctx, say, ids, role="narrator", uses=None, **kw):
    return review(say, role=role, allowed_facts=facts(ctx, *ids),
                  uses=ids if uses is None else uses, forbidden=ctx.forbidden, **kw)


def test_a_faithful_reword_passes(ctx):
    assert ok(ctx, "战火不停，一封家信比万金还难得。", ["arrive/WORLD/0"]).ok


def test_empty_is_rejected(ctx):
    assert ok(ctx, "  ", ["arrive/WORLD/0"]).rule == "R-empty"


def test_uses_must_be_inside_the_allowed_list(ctx):
    assert ok(ctx, "战火不停，一封家信比万金还难得。", ["arrive/WORLD/0"], uses=["arrive/CITY/0"]).rule == "R-basis"
    assert ok(ctx, "战火不停，一封家信比万金还难得。", ["arrive/WORLD/0"], uses=[]).rule == "R-basis"


def test_invented_numbers_and_names_are_rejected(ctx):
    assert ok(ctx, "战火打了整整八年，一封家信比万金还难得。", ["arrive/WORLD/0"]).rule == "R-fact"
    assert ok(ctx, "战火不停，安禄山的人马拦下了家信。", ["arrive/WORLD/0"]).rule in {"R-fact", "R-uncovered"}


def test_a_name_in_the_allowed_text_is_not_an_invention(ctx):
    assert ok(ctx, "叛军攻下长安之后，杜甫被困在这座城里。", ["arrive/CITY/0"]).ok


def test_forbidden_entity_from_the_sidecar_is_rejected(ctx):
    assert ok(ctx, "战火不停，后来唐军收复了。", ["arrive/WORLD/0"]).rule == "R-uncovered"


def test_mode_mixing_is_rejected(ctx):
    assert ok(ctx, "我觉得战火不停，一封家信比万金还难得。", ["arrive/WORLD/0"], role="narrator").rule == "R-mode"
    assert ok(ctx, "据记载，草长得比城墙还高。", ["meet/PERSON/0"], role="poet").rule == "R-mode"


def test_absolute_words_are_rejected_on_interpretations(ctx):
    assert ok(ctx, "家书到不了，所以抵万金一定有分量。", ["return/PERSON/0"]).rule == "R-hedge"


def test_one_length_limit_for_every_reader(ctx):
    # There is no grade split (2026-11-12): one limit, SAY_LIMIT = 100 characters.
    # "战火不停，家信比万金还难得，" is 14 chars: 7 copies = 98 pass the length rule, 8 = 112 do not.
    assert ok(ctx, "战火不停，家信比万金还难得，" * 7, ["arrive/WORLD/0"]).rule != "R-len"
    assert ok(ctx, "战火不停，家信比万金还难得，" * 8, ["arrive/WORLD/0"]).rule == "R-len"


@pytest.mark.parametrize("bad", ["战火不停，看 http://x.cn", "战火不停，你叫什么名字", "战火不停 13800138000"])
def test_unsafe_content_is_rejected(ctx, bad):
    assert ok(ctx, bad, ["arrive/WORLD/0"]).ok is False


def test_a_year_the_sources_do_not_give_is_rejected(ctx):
    # Not a grade rule any more: years are fine when the allowed facts carry them. This one does not.
    assert ok(ctx, "公元757年，战火不停。", ["arrive/WORLD/0"]).rule == "R-fact"


def test_ungrounded_prose_with_no_numbers_or_names_is_still_caught(ctx):
    r = ok(ctx, "春天的街市热闹非凡，商贩吆喝着卖花。", ["arrive/WORLD/0"])
    assert r.rule == "R-grounding"


def test_the_guide_must_not_speak_as_the_poet(ctx):
    r = review("我站在城下，认不出这座城。", role="guide", allowed_facts=[], uses=[])
    assert r.rule == "R-mode"
