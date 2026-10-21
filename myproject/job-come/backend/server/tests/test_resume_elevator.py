from jc.services.resume_elevator import ResumeElevator


def test_split_bullet_keeps_full_sentence() -> None:
    """A Chinese comma does not end a sentence, so this stays one bullet.

    Written as a single literal on purpose: splitting it for line length would change
    what is under test. The commas here are the whole point.
    """
    long = (
        "精通 Docker 源码，给内源的 Docker 版本修复了 40 多个 bug，"
        "向开源社区提交了 10 多个 patch，对容器相关技术有很深的研究。"
    )
    assert ResumeElevator._split_bullet(long) == [long]


def test_semicolon_is_not_a_source_unit_boundary() -> None:
    text = "维护内源 Docker；提交上游 patch"
    assert ResumeElevator._split_bullet(text) == [text]


def test_clean_bullets_does_not_ellipsis() -> None:
    bullets = [
        "作为组内 Docker 技术重要的底层技术之一 cgroup 的内核维护者，负责调度与隔离相关问题排查。",
        "b",
    ]
    out = ResumeElevator._clean_bullets(bullets)
    assert "…" not in out[0]
    assert out[0].startswith("作为组内")


def test_clean_bullets_keeps_every_bullet_of_a_senior_role() -> None:
    """A 12-year career can legitimately carry more than 8 bullets in one role.

    The old 8-bullet cap silently deleted accomplishments the extractor was told to keep.
    """
    bullets = [f"主导系统 {i} 的重构，服务可用性提升至 99.9%" for i in range(12)]
    assert len(ResumeElevator._clean_bullets(bullets)) == 12


def test_clean_bullets_drops_blanks_and_duplicates() -> None:
    out = ResumeElevator._clean_bullets(["  搭建配置中心  ", "", "搭建配置中心", "推动上线"])
    assert out == ["搭建配置中心", "推动上线"]


def test_normalize_sections_covers_project_bullets() -> None:
    sections = {
        "experience_blocks": [{"bullets": ["维护内源 Docker；提交上游 patch"]}],
        "project_blocks": [{"bullets": ["统一配置中心；覆盖 120+ 服务", "", "统一配置中心"]}],
    }
    out = ResumeElevator._normalize_sections(sections)
    assert out["experience_blocks"][0]["bullets"] == ["维护内源 Docker；提交上游 patch"]
    assert out["project_blocks"][0]["bullets"] == ["统一配置中心；覆盖 120+ 服务", "统一配置中心"]


def test_diff_map_reports_project_rewrites() -> None:
    baseline = {"project_blocks": [{"bullets": ["参与配置中心建设"]}]}
    elevated = {"project_blocks": [{"bullets": ["负责配置中心建设，覆盖 120+ 服务"]}]}
    out = ResumeElevator._diff_maps(baseline, elevated, "elevated")
    assert [e["field_path"] for e in out] == ["project_blocks[0].bullets[0]"]
    assert out[0]["needs_defense"] is True


def test_system_prompt_carries_the_playbook_and_the_chosen_angles() -> None:
    """Playbook and angles are appended, so honesty rules stay in the skill body."""
    from jc.domain.role_families import get_playbook

    prompt = ResumeElevator._compose_system_prompt(
        get_playbook("pm"), ["ownership", "outcome"]
    )

    assert "Role playbook for this document" in prompt
    assert "产品经理" in prompt
    assert "## Framing angles chosen for this document" in prompt
    assert prompt.index("Primary") < prompt.index("Secondary")
    # The boundary must travel with the angle text into the prompt.
    assert "never license a new fact" in prompt


def test_system_prompt_omits_the_angle_section_when_there_is_none() -> None:
    """An empty block would leave a dangling header the model has to interpret."""
    from jc.domain.role_families import get_playbook

    prompt = ResumeElevator._compose_system_prompt(get_playbook("backend"), [])

    # The heading, not the phrase: the targeting fragment names the section in prose.
    assert "## Framing angles chosen for this document" not in prompt
    assert "Role playbook for this document" in prompt


def test_the_writing_methodology_reaches_the_prompt_from_the_skill_package() -> None:
    """The methodology must not live only in a file nothing reads.

    It used to live in a 340-line prompt beside 10-line skill stubs whose bodies
    were unreachable, so "we have skills" and "the model was told the methodology"
    were two different claims. This asserts the second one.
    """
    from jc.domain.role_families import get_playbook

    prompt = ResumeElevator._compose_system_prompt(get_playbook("backend"), [])

    # The universal layers: how a bullet is written, how a document is assembled.
    assert "Action + Object + Outcome" in prompt
    assert "结论先行" in prompt
    # The output contract, which lives in the skill's always-loaded body.
    assert "experience_blocks" in prompt
    # And the rule no fragment may relax.
    assert "Never invent" in prompt


def test_two_role_families_are_written_to_different_methodologies() -> None:
    """The point of per-family fragments: a legal resume is not judged like a backend one.

    Asserts the *difference*, not the presence of a label. A version that appended
    only the playbook label passed every "does it mention the family" check while
    giving both roles the same instructions.
    """
    from jc.domain.role_families import get_playbook

    backend = ResumeElevator._compose_system_prompt(get_playbook("backend"), [])
    legal = ResumeElevator._compose_system_prompt(get_playbook("legal"), [])

    assert "取舍" in backend
    assert "取舍" not in legal.split("这个岗位族怎么写")[-1]
    # Legal outcomes are often "the risk never materialised", so this family must be
    # told not to demand a number — and backend must not be told that.
    assert "不要为这个族的要点索要指标" in legal
    assert "这个岗位的成果常常没有数字" in legal
    assert "这个岗位的成果常常没有数字" not in backend


def test_a_family_without_its_own_fragment_falls_back_to_the_neutral_one() -> None:
    """Falling back to another family's methodology would be worse than being neutral."""
    from jc.domain.role_families import get_playbook

    prompt = ResumeElevator._compose_system_prompt(get_playbook("general"), [])

    assert "这个岗位族怎么写" not in prompt
    # It still gets the universal layers and the qualitative relaxation.
    assert "Action + Object + Outcome" in prompt
    assert "这个岗位的成果常常没有数字" in prompt
