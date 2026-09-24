from jobcome.agent.resume_task import build_profile_digest, wrap_resume_coach_message
from jobcome.schemas.profile_payload import ProfileContact, ProfileExperience, ProfilePayload


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
