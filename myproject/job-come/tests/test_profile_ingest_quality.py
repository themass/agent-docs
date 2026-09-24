"""Profile ingest quality scoring tests."""

from jobcome.schemas.profile_payload import ProfileContact, ProfileExperience, ProfilePayload
from jobcome.services.profile_ingest_quality import is_low_quality_payload, payload_quality_score


def test_good_payload_scores_high() -> None:
    payload = ProfilePayload(
        contact=ProfileContact(name="张三", email="a@b.com", phone="13800000000"),
        summary="5年后端经验",
        experiences=[
            ProfileExperience(
                id="exp1",
                company="字节跳动",
                title="高级后端",
                start_date="2020-01",
                highlights=["优化 P99 30%"],
            )
        ],
    )
    assert payload_quality_score(payload, file_name="resume.pdf") >= 50
    assert not is_low_quality_payload(payload, file_name="resume.pdf")


def test_filename_as_name_scores_low() -> None:
    payload = ProfilePayload(
        contact=ProfileContact(name="与爱为舞 杨鹏飞 上海"),
        summary="（解析草稿）",
        experiences=[
            ProfileExperience(
                id="exp1",
                company="",
                title="后端",
                start_date="2020-01",
                highlights=[],
            )
        ],
    )
    assert is_low_quality_payload(payload, file_name="与爱为舞-杨鹏飞-上海.pdf")
