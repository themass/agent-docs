from jc.agent.resume_task import (
    build_profile_digest,
    coach_role_family_for,
    coach_shortfall_for,
    coach_skill_for,
    wrap_resume_coach_message,
)
from jc.agent.standing_instructions import build_standing_block
from jc.schemas.agent import AgentUiContext, AgentUiFocus
from jc.schemas.profile_payload import (
    ProfileContact,
    ProfileExperience,
    ProfilePayload,
    ProfilePreferences,
)


def _standing(payload) -> str:
    """The system-layer text this profile's session would actually carry.

    The role-family methodology moved out of the per-turn user message into the
    system layer (see `jc.agent.standing_instructions`), so the methodology
    assertions below exercise the composition the middleware performs rather
    than a string that no longer exists in the turn. `coach_role_family_for` and
    `coach_skill_for` are the two profile-derived inputs `AgentService` feeds it.
    """
    return build_standing_block(
        skill_id=coach_skill_for(payload),
        role_family=coach_role_family_for(payload),
        reply_language="（回复语言规则）",
    )


def test_profile_digest_includes_company_and_highlight_paths() -> None:
    payload = ProfilePayload(
        contact=ProfileContact(name="杨鹏飞"),
        experiences=[
            ProfileExperience(
                id="e1",
                company="杭州华为技术有限公司",
                title="内核开发工程师",
                start_date="2017-05",
                end_date="2018-10",
                highlights=["参与公司内源 Docker 版本的维护和交付"],
            )
        ],
    )
    digest = build_profile_digest(payload)
    assert "experiences[0] 杭州华为技术有限公司" in digest
    assert "highlights[0]" in digest


def test_the_turn_carries_only_the_user_and_this_turns_facts() -> None:
    """Conduct rules are no longer re-asserted in front of the user's question.

    They were being sent twice per turn -- once as prose at the top of the
    `HumanMessage` and once as system content from `JCProductRulesMiddleware` --
    with the weaker copy sitting between the model and what the user asked.
    """
    text = wrap_resume_coach_message(
        "华为工作内容能再丰富一些么",
        profile_id="prof_1",
        digest="experiences[0] 华为 · 内核",
    )
    assert "华为工作内容能再丰富一些么" in text
    assert "prof_1" in text
    assert "experiences[0] 华为" in text
    # Standing policy must not reappear in the turn.
    assert "不要自我介绍" not in text
    assert "ask_clarification" not in text
    assert "简历优化任务" not in text
    # The user's words come last: closest to where the model starts writing.
    assert text.rstrip().endswith("华为工作内容能再丰富一些么")


def test_the_conduct_rules_are_stated_once_at_the_system_layer() -> None:
    standing = _standing(_payload("后端开发工程师"))

    assert "不要自我介绍" in standing
    assert "ask_clarification" in standing
    # Exactly once, not once per phrasing.
    assert standing.count("不要调用 ask_clarification") == 1
    # And the reply language is here rather than prepended to the turn.
    assert "（回复语言规则）" in standing


def test_wrap_includes_ui_focus_path() -> None:
    ctx = AgentUiContext(
        page="resume-agent",
        step="review",
        focus=AgentUiFocus(
            path="experiences[0]",
            kind="experience",
            label="杭州华为 · 内核开发工程师",
        ),
    )
    text = wrap_resume_coach_message(
        "这块写具体一点",
        profile_id="prof_1",
        digest="experiences[0] 华为",
        ui_context=ctx,
    )
    assert "path=experiences[0]" in text
    assert "这块写具体一点" in text
    assert "不要再问改哪一段" in text


def test_profile_digest_shows_every_highlight_by_default() -> None:
    """The coach can only rewrite what the digest shows.

    The digest used to cap highlights at 8, so 「这段再丰富一些」 was answered against a
    truncated career and the remaining bullets were silently invisible to the agent.
    """
    from jc.schemas.profile_payload import ProfileProject

    payload = ProfilePayload(
        experiences=[
            ProfileExperience(
                id="e1",
                company="ACME",
                title="技术专家",
                start_date="2014-07",
                highlights=[f"主导系统 {i} 的重构" for i in range(11)],
            )
        ],
        projects=[
            ProfileProject(
                id="prj1",
                name="统一配置中心",
                role="负责人",
                highlights=["接入 120+ 服务", "配置事故下降 70%"],
            )
        ],
    )
    digest = build_profile_digest(payload)
    assert "highlights[10]" in digest
    assert "另有" not in digest
    assert "projects[0] 统一配置中心 · 负责人" in digest
    assert "120+ 服务" in digest


def test_profile_digest_still_honors_an_explicit_cap() -> None:
    payload = ProfilePayload(
        experiences=[
            ProfileExperience(
                id="e1",
                company="ACME",
                title="工程师",
                start_date="2020-01",
                highlights=["a", "b", "c"],
            )
        ],
    )
    digest = build_profile_digest(payload, max_highlights=2)
    assert "highlights[1]" in digest
    assert "另有 1 条" in digest


# --- coach methodology ----------------------------------------------------------------
# The agent path cannot read a SKILL.md: DeerFlow injects only a skill's name and
# location, and the body is loaded by the model calling `read_file`, which V1 does
# not grant. These tests cover the host-side composition that replaces it.


def _payload(title: str, *, role_family: str | None = None) -> ProfilePayload:
    """A profile that can already generate a resume, so the coach is in editing mode.

    Three highlights is not incidental: below the viability floor the coach switches to
    interview methodology, which is correct behaviour and a different set of assertions.
    A one-bullet fixture here would be testing the editing path against a profile the
    product considers unfinished.
    """
    return ProfilePayload(
        contact=ProfileContact(name="张三"),
        preferences=ProfilePreferences(role_family=role_family),
        experiences=[
            ProfileExperience(
                id="e1",
                company="ACME",
                title=title,
                start_date="2020-01",
                highlights=[
                    "参与订单系统开发",
                    "负责支付回调链路",
                    "参与大促容量准备",
                ],
            )
        ],
    )


def _thin_payload(title: str) -> ProfilePayload:
    """A profile with a job but no evidence — the shape that needs an interview."""
    return ProfilePayload(
        contact=ProfileContact(name="张三"),
        experiences=[
            ProfileExperience(id="e1", company="ACME", title=title, start_date="2020-01")
        ],
    )


def test_the_coach_turn_carries_the_bullet_method() -> None:
    """Without this the coach had identity rules and no methodology at all.

    That is why 「这段丰富一点」 produced longer sentences instead of the
    constraint / method / scope / outcome material the profile already contained.
    """
    standing = _standing(_payload("后端开发工程师"))

    assert "动作 + 对象 + 结果" in standing
    assert "约束" in standing and "范围" in standing
    # And the prohibition travels with it.
    assert "不要编数字" in standing


def test_the_coach_gets_the_role_familys_own_standard() -> None:
    standing = _standing(_payload("后端开发工程师"))

    assert "这个岗位族怎么写" in standing
    assert "量级" in standing


def test_an_explicit_family_choice_beats_the_inferred_title() -> None:
    """The user's own pick must win: inferring wrong coaches the wrong audience."""
    standing = _standing(_payload("后端开发工程师", role_family="legal"))

    assert "法务" in standing
    assert "不要为这个族的要点索要指标" in standing


def test_a_qualitative_family_is_told_not_to_demand_a_number() -> None:
    assert "这个岗位的成果常常没有数字" in _standing(_payload("法务经理"))
    assert "这个岗位的成果常常没有数字" not in _standing(_payload("后端开发工程师"))


def test_an_unrecognised_title_gets_the_neutral_methodology_not_a_guess() -> None:
    standing = _standing(_payload("某种没听过的岗位"))

    assert "动作 + 对象 + 结果" in standing
    assert "这个岗位族怎么写" not in standing


def test_a_missing_profile_still_yields_the_universal_methodology() -> None:
    """A failed profile load must not leave the coach with no method at all."""
    standing = _standing(None)

    assert "动作 + 对象 + 结果" in standing


def test_the_methodology_is_system_content_and_never_rides_the_turn() -> None:
    """The ordering contract moved layers rather than disappearing.

    It used to be expressed as "methodology appears before the user's words in the
    same `HumanMessage`". System content outranks user content by design, so the
    stronger version of that contract is: methodology is in the system block, and
    the turn carries nothing but this turn's facts and the question.
    """
    payload = _payload("后端开发工程师")
    standing = _standing(payload)
    message = wrap_resume_coach_message(
        "这段丰富一点", profile_id="p1", digest="DIGEST"
    )

    assert "动作 + 对象 + 结果" in standing
    assert "动作 + 对象 + 结果" not in message
    assert "改写方法" not in message
    # The digest stays the only user-data block in the turn, and the question is last.
    assert "DIGEST" in message
    assert message.rstrip().endswith("这段丰富一点")


def test_a_skill_without_fragments_leaves_no_dangling_header() -> None:
    """A skill outside the resume paths gets conduct rules and nothing else.

    A mock-interview turn must not be handed resume rewriting methodology, and an
    empty composition must not leave the 「改写方法」 header sitting over nothing.
    """
    standing = build_standing_block(
        skill_id="mock-interview", role_family="backend", reply_language="L"
    )

    assert "改写方法" not in standing
    assert "动作 + 对象 + 结果" not in standing
    # The conduct rules still apply to every skill.
    assert "不要自我介绍" in standing


# --- building a profile that does not exist yet ---------------------------------------
#
# The coach was only ever an editor. On an empty or skeleton profile that is the wrong
# job: "rewrite this bullet to lead with the outcome" has nothing to operate on, and a
# model given editing methodology answers 「帮我改改」 by producing resume-shaped prose
# containing none of the user's career.


def test_a_profile_that_cannot_generate_gets_interview_methodology() -> None:
    assert coach_skill_for(_thin_payload("后端开发工程师")) == "profile-interview"
    assert coach_skill_for(ProfilePayload()) == "profile-interview"


def test_a_profile_that_can_generate_keeps_the_editing_methodology() -> None:
    assert coach_skill_for(_payload("后端开发工程师")) == "resume-coach"


def test_a_failed_profile_load_does_not_turn_the_turn_into_an_interview() -> None:
    """Unknown is not empty. Interviewing a user who has a full profile is worse than
    coaching one whose digest failed to load, because it re-asks what they already gave."""
    assert coach_skill_for(None) == "resume-coach"


def test_interview_guidance_says_to_ask_rather_than_polish() -> None:
    """The interview skill's own contract must travel with its fragments.

    `resume-coach`'s identity is registered with the runtime, so its guidance omits the
    contract to avoid sending it twice. `profile-interview`'s contract is the instruction
    that contradicts that identity, so dropping it would leave the model behaving like an
    editor while holding interview methodology — and it would look like the skill loaded.
    """
    standing = _standing(_thin_payload("后端开发工程师"))

    assert "把简历问出来" in standing
    assert "一次只问一个问题" in standing
    # Methodology for asking, not for rewriting.
    assert "他知道那个数字，只是从来没人问过他" in standing
    # The role family still applies: a backend interview asks about backend evidence.
    assert "量级" in standing


def test_the_interview_still_forbids_inventing_facts() -> None:
    standing = _standing(ProfilePayload())

    assert "不要编公司、学校、日期、职级、数字" in standing
    assert "不要在材料还不够时就生成简历" in standing


def test_the_interview_turn_is_not_framed_as_a_rewrite() -> None:
    """Every fixed line in the wrapper used to assume a resume existed to edit.

    The framing now lives in the session block, so the assertion splits: the turn
    must not read as an edit request, and the session block must say this session
    is an interview.
    """
    message = wrap_resume_coach_message(
        "帮我改改简历",
        profile_id="p1",
        digest="DIGEST",
        interview=True,
        shortfall=("经历要点太少（当前 0 条，至少需要 3 条）",),
    )

    assert "简历优化任务" not in message
    assert "只基于这些事实改写" not in message
    # The shortfall is quoted so the model does not have to infer the gap from an
    # empty digest, which reads the same as a failed profile load.
    assert "经历要点太少" in message
    assert "DIGEST" in message
    assert message.rstrip().endswith("帮我改改简历")

    standing = _standing(_thin_payload("后端开发工程师"))
    assert "建档访谈" in standing
    assert "一次只问一个问题" in standing


def test_the_editing_session_is_framed_as_editing_not_as_an_interview() -> None:
    standing = _standing(_payload("后端开发工程师"))

    assert "简历优化" in standing
    assert "建档访谈" not in standing
    assert "改写方法" in standing


def test_the_shortfall_quotes_what_the_intake_panel_shows() -> None:
    """One source, so the sidebar and the panel cannot disagree about what is missing."""
    from jc.services.profile_intake import build_intake_plan

    profile = _thin_payload("后端开发工程师")
    assert coach_shortfall_for(profile) == tuple(build_intake_plan(profile).blocking)
    assert coach_shortfall_for(_payload("后端开发工程师")) == ()
    assert coach_shortfall_for(None) == ()


# --- pointer form: the full digest only on the first turn -----------------------------
#
# `jc_llm_call` payload capture on a real session showed the editing turn resending a
# ~4k token digest on every turn, unchanged, duplicate of what `jc_profile_get`'s own
# tool result already carried. These guard the fix: later turns must not repeat it, and
# must still tell the model how to get current data.


def test_later_turn_omits_the_full_digest_and_points_at_the_tool() -> None:
    message = wrap_resume_coach_message(
        "这段丰富一点",
        profile_id="p1",
        digest="DIGEST-FULL-TEXT",
        include_digest=False,
    )

    assert "DIGEST-FULL-TEXT" not in message
    assert "jc_profile_get" in message
    assert "档案摘要已在本会话开头给过" in message
    assert "这段丰富一点" in message
    assert "p1" in message


def test_first_turn_still_sends_the_full_digest() -> None:
    message = wrap_resume_coach_message(
        "这段丰富一点",
        profile_id="p1",
        digest="DIGEST-FULL-TEXT",
        include_digest=True,
    )

    assert "DIGEST-FULL-TEXT" in message


def test_the_interview_branch_ignores_the_pointer_flags() -> None:
    """A profile still being interviewed is short by definition; the model reads its
    digest to decide what is still missing, so it is never swapped for a pointer."""
    message = wrap_resume_coach_message(
        "帮我改改简历",
        profile_id="p1",
        digest="DIGEST-FULL-TEXT",
        interview=True,
        shortfall=("经历要点太少（当前 0 条，至少需要 3 条）",),
        include_digest=False,
    )

    assert "DIGEST-FULL-TEXT" in message
