"""Routing by the annotation headword a learner names. Rules only; no model, no network."""
from __future__ import annotations

from student_agent.router import route


def test_naming_an_annotated_word_finds_the_line_it_is_on(ctx):
    r = route("烽火是什么", ctx)
    assert (r.action, r.line_seq) == ("hint", 5)
    r = route("山河是什么意思", ctx)
    assert (r.action, r.line_seq) == ("hint", 1)


def test_a_question_nothing_in_the_bundle_explains_is_declined_not_invented(ctx):
    for q in ("他为什么哭", "他当时在想什么", "他为什么不回家"):
        assert route(q, ctx).action == "decline", q


def test_an_explicit_line_number_beats_the_headword(ctx):
    assert route("第一句烽火是什么意思", ctx).line_seq == 1


def test_asking_for_the_basis_keeps_its_own_route(ctx):
    r = route("烽火是真的吗", ctx)
    assert r.action == "basis" and r.line_seq is None


def test_a_word_with_no_annotation_does_not_get_a_line_that_merely_uses_it(ctx):
    # 「草木」只出现在一句话里，没有注释。问词义不该拿到那句话冒充解释。
    assert route("草木是什么意思", ctx).action != "faq"


def test_the_stale_triggers_are_gone(ctx):
    # 这些词已不在台词里；留着触发词只会把问题路由到一句并不回答它的话。
    for q in ("驿路是什么", "城门怎么样了"):
        assert route(q, ctx).action == "decline", q


def test_a_why_question_nothing_answers_is_declined_not_given_a_layer_card(ctx):
    # 「长安」会把它带到“这座城”那一层，但那张卡描述的是“是什么”，不是“为什么”。
    r = route("他为什么被困在长安", ctx)
    assert (r.action, r.reason) == ("decline", "why_unanswered")


def test_a_why_question_with_a_prepared_answer_still_gets_it(ctx):
    assert route("为什么打仗", ctx).action == "faq"
    assert route("为什么说家书抵万金", ctx).action == "faq"
