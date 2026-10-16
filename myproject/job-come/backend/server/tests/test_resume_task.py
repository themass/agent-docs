from jc.agent.resume_task import build_profile_digest, wrap_resume_coach_message
from jc.schemas.agent import AgentUiContext, AgentUiFocus
from jc.schemas.profile_payload import ProfileContact, ProfileExperience, ProfilePayload


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


def test_wrap_resume_coach_forbids_intro_and_keeps_user_text() -> None:
    text = wrap_resume_coach_message(
        "华为工作内容能再丰富一些么",
        profile_id="prof_1",
        digest="experiences[0] 华为 · 内核",
    )
    assert "不要自我介绍" in text
    assert "ask_clarification" in text
    assert "华为工作内容能再丰富一些么" in text
    assert "prof_1" in text
    assert "experiences[0] 华为" in text


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
