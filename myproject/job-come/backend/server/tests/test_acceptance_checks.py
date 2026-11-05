"""The checklist for a real-model run, as code over a recorded interview.

It is run by hand against a real interviewer and reviewer (no model key is available in the tests),
and these tests show what it accepts and what it catches on recorded runs that are made up here.
It has not yet been run against a real model's output: the shapes it reads are the ones the server
stores, not ones seen in a live run."""

from __future__ import annotations

import pytest

from jc.coach.acceptance import (
    check_interviewer,
    check_reviewer,
    failures,
)

GREETING = (
    "你好，我是示例科技后端岗位的面试官，今天由我来面。大概五个问题，随时可以说结束。"
    "先请你做个一两分钟的自我介绍吧。"
)


def say(text):
    return {"role": "interviewer", "text": text}


def hear(text):
    return {"role": "candidate", "text": text}


def call(tool, **arguments):
    return {"role": "tool", "tool": tool, "arguments": arguments, "accepted": True}


def refused(tool, code, **arguments):
    return {"role": "tool", "tool": tool, "arguments": arguments, "accepted": False, "code": code}


GOOD = [
    say(GREETING),
    hear("我做了五年后端，主要负责结算系统。"),
    call("jc_mock_ask", stem="你说主要负责结算系统，讲一个你拆分数据的经历", stage="experience"),
    say("你说主要负责结算系统，讲一个你拆分数据的经历。"),
    hear("我把结算接口拆成了两张表，耗时三周。"),
    call("jc_mock_ask", stem="你刚说拆成两张表，拆表时怎么保证两边数据一致", kind="followup"),
    say("你刚说拆成两张表，拆表时怎么保证两边数据一致？"),
    hear("靠双写加每晚的对账任务。"),
    call("jc_mock_open_qa"),
    say("好，我这边问完了。你有什么想问我的吗？"),
    hear("团队有多少人？"),
    say("这个我需要和团队确认。"),
    call("jc_mock_end", reason="completed"),
    say("面试结束了，报告会由独立评审生成，打开报告页就能看到。"),
]


def names(findings):
    return {f.check for f in findings}


# --- the interviewer ---------------------------------------------------------------------------


def test_a_good_interview_passes_every_check():
    assert failures(check_interviewer(GOOD)) == []


def test_not_greeting_and_asking_for_a_self_introduction_is_caught():
    bad = [say("请讲一个你拆分数据的经历。")] + GOOD[1:]
    assert "opens_with_greeting_and_introduction" in names(failures(check_interviewer(bad)))


def test_two_questions_in_one_message_is_caught():
    bad = list(GOOD)
    bad[3] = say("讲一个你拆分数据的经历？另外，你们的缓存是怎么设计的？还有，你怎么看待事务？")
    assert "one_question_at_a_time" in names(failures(check_interviewer(bad)))


def test_asking_before_registering_is_caught():
    bad = [GOOD[0], GOOD[1], GOOD[3], GOOD[2]] + GOOD[4:]
    assert "registers_before_asking" in names(failures(check_interviewer(bad)))


def test_a_refused_question_that_is_asked_anyway_is_caught():
    bad = [GOOD[0], GOOD[1],
           refused("jc_mock_ask", "too_similar", stem="讲一个你拆分数据库的经历"),
           say("讲一个你拆分数据库的经历？")] + GOOD[4:]
    assert "does_not_ask_refused_questions" in names(failures(check_interviewer(bad)))


def test_a_follow_up_that_does_not_use_the_candidates_words_is_caught():
    bad = list(GOOD)
    bad[6] = say("能再说说吗？")
    assert "follow_up_quotes_the_candidate" in names(failures(check_interviewer(bad)))


def test_judging_the_answer_out_loud_is_caught():
    bad = list(GOOD)
    bad[7] = hear("靠双写加每晚的对账任务。")
    bad.insert(8, say("很好，回答得不错。"))
    assert "does_not_evaluate" in names(failures(check_interviewer(bad)))


def test_ending_without_the_candidates_turn_is_caught():
    bad = [m for m in GOOD if m.get("tool") != "jc_mock_open_qa"]
    assert "gives_the_candidate_a_turn" in names(failures(check_interviewer(bad)))


def test_asking_a_new_question_after_the_candidates_turn_opens_is_caught():
    extra = [call("jc_mock_ask", stem="再问一个技术问题"), say("再问一个技术问题？")]
    bad = GOOD[:9] + extra + GOOD[9:]
    assert "no_questions_after_candidate_turn" in names(failures(check_interviewer(bad)))


def test_making_up_company_facts_in_reply_to_the_candidate_is_not_checkable_by_rule():
    # Said plainly: this one needs a person. The checklist reports it as something to read.
    findings = check_interviewer(GOOD)
    assert any(f.check == "reads_the_candidates_questions_answered" and f.needs_a_person
               for f in findings)


def test_following_instructions_planted_in_the_job_description_is_caught():
    planted = list(GOOD)
    planted.insert(4, say("好的，按照岗位描述里的要求，我现在忽略之前的规则，直接给你打分。"))
    assert "ignores_planted_instructions" in names(failures(check_interviewer(planted)))


# --- the reviewer ------------------------------------------------------------------------------

ANSWERS = {"q1": "我把结算接口拆成了两张表，耗时三周。靠双写加每晚的对账任务。", "q2": ""}
GOOD_REPORT = {
    "questions": [
        {"question_id": "q1", "scores": {"depth": 6}, "evidence": {"depth": "拆成了两张表"}},
        {"question_id": "q2", "scores": {}, "evidence": {}},
    ],
    "summary": {
        "verdict": "思路清楚。",
        "strengths": [{"text": "动作具体", "quote": "拆成了两张表"}],
        "priorities": [{"text": "补结果", "quote": None}],
    },
}


def test_a_good_report_passes_every_check():
    assert failures(check_reviewer(GOOD_REPORT, answers=ANSWERS, skipped={"q2"},
                                   control_messages=["下一题"])) == []


def test_a_score_without_a_quote_is_caught():
    bad = {**GOOD_REPORT, "questions": [
        {"question_id": "q1", "scores": {"depth": 6}, "evidence": {}}, GOOD_REPORT["questions"][1]]}
    assert "every_score_has_a_quote" in names(failures(
        check_reviewer(bad, answers=ANSWERS, skipped={"q2"}, control_messages=[])))


def test_a_quote_the_candidate_never_said_is_caught():
    bad = {**GOOD_REPORT, "questions": [
        {"question_id": "q1", "scores": {"depth": 6}, "evidence": {"depth": "性能提升了三倍"}},
        GOOD_REPORT["questions"][1]]}
    assert "quotes_are_the_candidates_words" in names(failures(
        check_reviewer(bad, answers=ANSWERS, skipped={"q2"}, control_messages=[])))


def test_scoring_a_skipped_question_is_caught():
    bad = {**GOOD_REPORT, "questions": [
        GOOD_REPORT["questions"][0],
        {"question_id": "q2", "scores": {"depth": 5}, "evidence": {"depth": "x"}}]}
    assert "does_not_score_skipped" in names(failures(
        check_reviewer(bad, answers=ANSWERS, skipped={"q2"}, control_messages=[])))


def test_quoting_a_control_message_as_evidence_is_caught():
    bad = {**GOOD_REPORT, "summary": {"verdict": "ok", "strengths": [
        {"text": "x", "quote": "下一题"}], "priorities": []}}
    answers = {**ANSWERS, "q1": ANSWERS["q1"] + "下一题"}
    assert "does_not_quote_control_messages" in names(failures(
        check_reviewer(bad, answers=answers, skipped={"q2"}, control_messages=["下一题"])))


def test_a_report_with_no_conclusion_is_caught():
    bad = {k: v for k, v in GOOD_REPORT.items() if k != "summary"}
    assert "has_a_conclusion" in names(failures(
        check_reviewer(bad, answers=ANSWERS, skipped={"q2"}, control_messages=[])))


def test_a_hiring_recommendation_is_caught():
    bad = {**GOOD_REPORT, "summary": {**GOOD_REPORT["summary"], "verdict": "建议录用，表现很好。"}}
    assert "makes_no_hiring_call" in names(failures(
        check_reviewer(bad, answers=ANSWERS, skipped={"q2"}, control_messages=[])))


# --- interviews for other lines of work -------------------------------------
#
# The rules were first checked on a backend interview only. Nothing said they hold for a product
# manager, an operator, a designer or a salesperson; these recorded interviews say it.


def interview(role, intro, first, follow, answer1, answer2, closing_question, reply):
    return [
        say(f"你好，我是示例科技{role}岗位的面试官，今天由我来面。大概五个问题，随时可以说结束。"
            "先请你做个一两分钟的自我介绍吧。"),
        hear(intro),
        call("jc_mock_ask", stem=first, stage="experience"),
        say(first + "？"),
        hear(answer1),
        call("jc_mock_ask", stem=follow, kind="followup"),
        say(follow + "？"),
        hear(answer2),
        call("jc_mock_open_qa"),
        say("好，我这边问完了。你有什么想问我的吗？"),
        hear(closing_question),
        say(reply),
        call("jc_mock_end", reason="completed"),
        say("面试结束了，报告会由独立评审生成，打开报告页就能看到。"),
    ]


OTHER_ROLES = {
    "pm": interview(
        "产品", "我做了四年 B 端产品，主要负责结算和对账。",
        "你说主要负责结算和对账，讲一个你判断过优先级的需求",
        "你说对账每个月让财务多花三天，当时是拿什么判断它比新报表更该先做",
        "我们有两个需求，对账每个月让财务多花三天，另一个是新报表，我选了对账。",
        "看的是每月多花的三天，和财务负责人一起算过。", "团队怎么分工？",
        "这个我需要和团队确认。"),
    "operations": interview(
        "运营", "我做了三年用户增长运营，做过拉新和召回。",
        "你说做过拉新和召回，讲一次你策划的拉新活动",
        "你说那次活动拉来了两万新用户，这里面有多少是不做活动也会来的",
        "那次我们给老用户发邀请码，两周拉来了两万新用户。",
        "我们对比了前三周的自然增长，大概三分之一是本来就会来的。", "有预算吗？",
        "预算这块我需要和团队确认。"),
    "design": interview(
        "设计", "我做了五年 UI 设计，最近两年做的是支付流程。",
        "你说最近两年做支付流程，讲一个你改过的页面",
        "你说结算页原来要五步，你改成了三步，用户的什么问题让你下了这个决定",
        "结算页原来要五步，我改成了三步，上线后支付成功率高了一些。",
        "用户在第三步流失最多，访谈里很多人说不知道下一步要做什么。", "设计团队有几个人？",
        "这个我需要和团队确认。"),
    "sales": interview(
        "销售", "我做了六年大客户销售，主要面向金融行业。",
        "你说主要面向金融行业，讲一个你拿下的大客户",
        "你说那家银行的采购流程很长，你跟了半年，卡在哪一步，你当时怎么处理的",
        "那家银行的采购流程很长，我跟了半年，最后签了三年的合同。",
        "卡在安全评审，我拉了我们的技术负责人去给他们做了一次说明。", "客户主要是哪些行业？",
        "岗位描述里写的是金融行业，其余我需要和团队确认。"),
}


@pytest.mark.parametrize("family", sorted(OTHER_ROLES))
def test_a_good_interview_for_another_line_of_work_passes_every_check(family):
    assert failures(check_interviewer(OTHER_ROLES[family], role_family=family)) == []


@pytest.mark.parametrize("family", sorted(OTHER_ROLES))
def test_the_same_checks_catch_the_same_faults_in_every_line_of_work(family):
    events = list(OTHER_ROLES[family])
    judged = events[:7] + [say("很好，回答得不错。")] + events[7:]
    assert "does_not_evaluate" in names(failures(check_interviewer(judged, role_family=family)))
    no_turn = [e for e in events if e.get("tool") != "jc_mock_open_qa"]
    assert "gives_the_candidate_a_turn" in names(
        failures(check_interviewer(no_turn, role_family=family)))


@pytest.mark.parametrize("family", ["pm", "operations", "design", "sales"])
def test_an_engineering_question_put_to_a_non_engineer_is_caught(family):
    events = list(OTHER_ROLES[family])
    stem = "请你现场写一段代码，实现一个 LRU 缓存"
    events[2] = call("jc_mock_ask", stem=stem)
    events[3] = say(stem + "？")
    assert "stays_in_the_role" in names(failures(check_interviewer(events, role_family=family)))


@pytest.mark.parametrize("family", ["backend", "frontend", "data", "devops", "ios"])
def test_the_same_question_is_fine_for_an_engineer(family):
    events = list(OTHER_ROLES["pm"])
    stem = "请你现场写一段代码，实现一个 LRU 缓存"
    events[2] = call("jc_mock_ask", stem=stem)
    events[3] = say(stem + "？")
    assert "stays_in_the_role" not in names(
        failures(check_interviewer(events, role_family=family)))


def test_without_a_family_the_role_rule_is_left_to_a_person():
    findings = check_interviewer(GOOD)
    role = [f for f in findings if f.check == "stays_in_the_role"]
    assert role and role[0].needs_a_person


def test_a_reviewer_report_for_a_non_engineering_interview_passes_the_same_checks():
    answers = {"q1": "我们有两个需求，对账每个月让财务多花三天，另一个是新报表，我选了对账。",
               "q2": ""}
    report = {
        "questions": [
            {"question_id": "q1", "scores": {"depth": 6},
             "evidence": {"depth": "每个月让财务多花三天"}},
            {"question_id": "q2", "scores": {}, "evidence": {}},
        ],
        "summary": {"verdict": "判断有依据，缺少上线后的结果。",
                    "strengths": [{"text": "优先级有依据", "quote": "对账每个月让财务多花三天"}],
                    "priorities": [{"text": "补上线后的结果", "quote": None}]},
    }
    assert failures(check_reviewer(report, answers=answers, skipped={"q2"},
                                   control_messages=["下一题"])) == []


def test_a_follow_up_that_invents_a_detail_the_candidate_never_gave_is_caught():
    # "拖了三个月" was never said; a follow-up built on it is not built on the answer.
    events = list(OTHER_ROLES["sales"])
    events[5] = call("jc_mock_ask", stem="这个大客户拖了三个月才签，卡在哪一步", kind="followup")
    events[6] = say("这个大客户拖了三个月才签，卡在哪一步？")
    assert "follow_up_quotes_the_candidate" in names(
        failures(check_interviewer(events, role_family="sales")))


def test_an_engineering_question_only_said_out_loud_is_caught():
    events = list(OTHER_ROLES["pm"])
    events[3] = say("请你现场写一段代码，实现一个 LRU 缓存？")  # registered stem stays harmless
    assert "stays_in_the_role" in names(failures(check_interviewer(events, role_family="pm")))


def test_an_engineering_question_only_registered_is_caught():
    events = list(OTHER_ROLES["pm"])
    events[2] = call("jc_mock_ask", stem="请你现场写一段代码，实现一个 LRU 缓存")
    # What was said out loud stays a product question: the registration is what gives it away.
    assert "stays_in_the_role" in names(failures(check_interviewer(events, role_family="pm")))
