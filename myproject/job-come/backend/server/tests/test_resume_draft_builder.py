"""Resume draft builder tests."""

from jc.models.enums import ElevationLevel
from jc.schemas.profile_payload import (
    ProfileContact,
    ProfileExperience,
    ProfilePayload,
    ProfileProject,
)
from jc.services.resume_draft_builder import ResumeDraftBuilder


def test_elevate_changes_bullets() -> None:
    profile = ProfilePayload(
        contact=ProfileContact(name="张三"),
        experiences=[
            ProfileExperience(
                id="exp1",
                company="ACME",
                title="工程师",
                start_date="2020-01",
                highlights=["参与订单系统开发"],
            )
        ],
    )
    sections, elevation_map = ResumeDraftBuilder().build(
        profile,
        elevation_level=ElevationLevel.ELEVATED,
    )
    bullet = sections["experience_blocks"][0]["bullets"][0]
    assert bullet != "参与订单系统开发"
    assert elevation_map


def _bullet(text: str, level: str, *, english: bool = False) -> str:
    return ResumeDraftBuilder._elevate_bullet(text, level, english=english)


def test_fallback_never_appends_an_unsupported_outcome() -> None:
    """The rule-based path may re-word, never invent a result.

    A fabricated outcome is a blocking reviewer error and would sink the candidate
    in an interview, so no level is allowed to add one.
    """
    fabrications = ("可量化", "业务成果", "提升", "降低", "%")
    for level in (
        ElevationLevel.CONSERVATIVE,
        ElevationLevel.STANDARD,
        ElevationLevel.ELEVATED,
    ):
        out = _bullet("参与订单系统开发", level)
        assert not any(f in out for f in fabrications), (level, out)


def test_conservative_is_verbatim() -> None:
    assert _bullet("参与订单系统开发", ElevationLevel.CONSERVATIVE) == "参与订单系统开发"


def test_english_bullets_are_untouched() -> None:
    text = "Involved in order system development"
    assert _bullet(text, ElevationLevel.ELEVATED, english=True) == text


def test_existing_ownership_verb_is_not_restacked() -> None:
    for level in (ElevationLevel.STANDARD, ElevationLevel.ELEVATED):
        assert _bullet("主导网关重构", level) == "主导网关重构"
        assert _bullet("负责风控策略", level) == "负责风控策略"


def test_weak_opener_is_lifted_at_most_to_negative_ownership() -> None:
    out = _bullet("参与推送链路改造", ElevationLevel.ELEVATED)
    assert out == "负责推送链路改造"
    assert "主导" not in out, "claiming 主导 needs evidence the profile does not carry"


def test_weak_opener_is_kept_at_standard_level() -> None:
    assert _bullet("参与推送链路改造", ElevationLevel.STANDARD) == "参与推送链路改造"


def test_filler_suffix_is_trimmed() -> None:
    assert _bullet("参与推送链路相关工作", ElevationLevel.STANDARD) == "参与推送链路"


def test_vague_opener_does_not_produce_stacked_verbs() -> None:
    out = _bullet("做数据同步", ElevationLevel.STANDARD)
    assert out == "负责数据同步"
    assert "负责做" not in out


def test_short_text_is_left_alone_rather_than_mangled() -> None:
    assert _bullet("做", ElevationLevel.ELEVATED) == "负责做"
    assert _bullet("", ElevationLevel.ELEVATED) == ""


def test_elevation_map_entries_carry_technique_labels() -> None:
    profile = ProfilePayload(
        contact=ProfileContact(name="张三"),
        experiences=[
            ProfileExperience(
                id="exp1",
                company="ACME",
                title="工程师",
                start_date="2020-01",
                highlights=["参与订单系统开发"],
            )
        ],
    )
    _, elevation_map = ResumeDraftBuilder().build(
        profile,
        elevation_level=ElevationLevel.ELEVATED,
    )
    assert elevation_map
    assert "ownership" in elevation_map[0]["techniques"]


def _profile_with_projects() -> ProfilePayload:
    return ProfilePayload(
        contact=ProfileContact(name="张三"),
        experiences=[
            ProfileExperience(
                id="exp1",
                company="ACME",
                title="技术专家",
                start_date="2019-04",
                end_date="2024-06",
                highlights=["主导后台迁移到微服务"],
            )
        ],
        projects=[
            ProfileProject(
                id="prj1",
                name="统一配置中心",
                role="负责人",
                description="主导配置中心建设，接入 120+ 服务，配置变更事故下降 70%",
            ),
            ProfileProject(id="prj2", name="无描述项目"),
        ],
    )


def test_projects_reach_the_rendered_sections() -> None:
    """A profile's projects must survive into project_blocks.

    The builder used to hardcode `project_blocks: []`, so every separately-listed
    project silently vanished from the resume even though the renderer and both
    templates support the section. For a senior profile that is the single largest
    source of "the resume looks far thinner than my career" .
    """
    sections, _ = ResumeDraftBuilder().build(
        _profile_with_projects(),
        elevation_level=ElevationLevel.ELEVATED,
    )

    blocks = sections["project_blocks"]
    assert len(blocks) == 2, "every project in the profile must be rendered"
    assert blocks[0]["name"] == "统一配置中心"
    assert blocks[0]["role"] == "负责人"
    # The description carries the evidence, so it must land in a bullet, not be dropped.
    assert blocks[0]["bullets"], "a project with a description must produce a bullet"
    assert "120+ 服务" in blocks[0]["bullets"][0]
    # A project with nothing to say gets no bullets rather than a placeholder string.
    assert blocks[1]["bullets"] == []


def test_projects_are_ordered_before_education_and_skills() -> None:
    """Projects are senior-signal content and belong next to experience.

    Rendering them after 技能 buries the strongest evidence below a comma-separated
    keyword list.
    """
    sections, _ = ResumeDraftBuilder().build(
        _profile_with_projects(),
        elevation_level=ElevationLevel.ELEVATED,
    )
    order = sections["section_order"]
    assert order.index("projects") < order.index("education")
    assert order.index("projects") < order.index("skills")
    assert order.index("experience") < order.index("projects")


def test_project_bullets_stay_truth_preserving() -> None:
    """Project text goes through the same no-fabrication path as experience bullets."""
    profile = ProfilePayload(
        contact=ProfileContact(name="张三"),
        projects=[ProfileProject(id="prj1", name="项目", description="参与权限模块重构")],
    )
    sections, _ = ResumeDraftBuilder().build(
        profile,
        elevation_level=ElevationLevel.ELEVATED,
    )
    bullet = sections["project_blocks"][0]["bullets"][0]
    assert "权限模块重构" in bullet
    # `参与` may be lifted to `负责`, never to an ownership claim the source lacks.
    assert "主导" not in bullet
    for fabrication in ("%", "提升", "降低"):
        assert fabrication not in bullet


def test_project_highlights_each_become_a_bullet() -> None:
    """Multi-bullet projects must not collapse into a single line.

    `ProfileProject` originally held one free-text `description`, so a 项目经历 entry with six
    source bullets was flattened to one. `highlights` now carries them, one bullet each, exactly
    like `ProfileExperience`.
    """
    profile = ProfilePayload(
        contact=ProfileContact(name="黄炎久"),
        projects=[
            ProfileProject(
                id="prj1",
                name="统一配置中心",
                role="负责人",
                start_date="2021-03",
                end_date="2023-08",
                description="面向全集团的配置下发平台",
                highlights=[
                    "主导配置中心建设，接入 120+ 服务",
                    "推动配置变更事故下降 70%",
                    "设计灰度发布能力，覆盖 6 个业务线",
                ],
            )
        ],
    )
    block = ResumeDraftBuilder().build(
        profile, elevation_level=ElevationLevel.STANDARD
    )[0]["project_blocks"][0]

    assert len(block["bullets"]) == 3, "every project highlight must render as its own bullet"
    assert "120+ 服务" in block["bullets"][0]
    assert "6 个业务线" in block["bullets"][2]
    # With highlights present, the overview stays an overview instead of being promoted.
    assert block["description"] == "面向全集团的配置下发平台"
    assert block["date_range"] == "2021-03 – 2023-08"


def test_project_without_end_date_reads_as_ongoing() -> None:
    profile = ProfilePayload(
        projects=[ProfileProject(id="prj1", name="项目", start_date="2024-01")],
    )
    sections, _ = ResumeDraftBuilder().build(profile, elevation_level=ElevationLevel.CONSERVATIVE)
    assert sections["project_blocks"][0]["date_range"] == "2024-01 – 至今"


def test_project_rewrites_are_recorded_in_the_elevation_map() -> None:
    """Users must be able to review and defend project lines, not just experience lines."""
    profile = ProfilePayload(
        projects=[
            ProfileProject(id="prj1", name="项目", highlights=["参与权限模块重构"]),
        ],
    )
    _, elevation_map = ResumeDraftBuilder().build(
        profile, elevation_level=ElevationLevel.ELEVATED
    )
    paths = [entry["field_path"] for entry in elevation_map]
    assert "project_blocks[0].bullets[0]" in paths
