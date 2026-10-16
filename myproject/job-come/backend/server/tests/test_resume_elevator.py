from jc.services.resume_elevator import ResumeElevator


def test_split_bullet_keeps_full_sentence() -> None:
    long = "精通 Docker 源码，给内源的 Docker 版本修复了 40 多个 bug，向开源社区提交了 10 多个 patch，对容器相关技术有很深的研究。"
    assert ResumeElevator._split_bullet(long) == [long]


def test_split_bullet_on_semicolon() -> None:
    text = "维护内源 Docker；提交上游 patch"
    assert ResumeElevator._split_bullet(text) == ["维护内源 Docker", "提交上游 patch"]


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
    assert out["experience_blocks"][0]["bullets"] == ["维护内源 Docker", "提交上游 patch"]
    assert out["project_blocks"][0]["bullets"] == ["统一配置中心", "覆盖 120+ 服务"]


def test_diff_map_reports_project_rewrites() -> None:
    baseline = {"project_blocks": [{"bullets": ["参与配置中心建设"]}]}
    elevated = {"project_blocks": [{"bullets": ["负责配置中心建设，覆盖 120+ 服务"]}]}
    out = ResumeElevator._diff_maps(baseline, elevated, "elevated")
    assert [e["field_path"] for e in out] == ["project_blocks[0].bullets[0]"]
    assert out[0]["needs_defense"] is True


def test_system_prompt_carries_the_playbook_and_the_chosen_angles() -> None:
    """Both are appended, so the base prompt stays the only place honesty rules live."""
    from jc.services.role_families import get_playbook

    elevator = object.__new__(ResumeElevator)
    elevator._system_prompt = "BASE RULES"
    prompt = elevator._compose_system_prompt(get_playbook("pm"), ["ownership", "outcome"])

    assert prompt.startswith("BASE RULES")
    assert "Role playbook for this document" in prompt
    assert "产品经理" in prompt
    assert "Framing angles chosen for this document" in prompt
    assert prompt.index("Primary") < prompt.index("Secondary")
    # The boundary must travel with the angle text into the prompt.
    assert "never license a new fact" in prompt


def test_system_prompt_omits_the_angle_section_when_there_is_none() -> None:
    """An empty block would leave a dangling header the model has to interpret."""
    from jc.services.role_families import get_playbook

    elevator = object.__new__(ResumeElevator)
    elevator._system_prompt = "BASE RULES"
    prompt = elevator._compose_system_prompt(get_playbook("backend"), [])

    assert "Framing angles chosen for this document" not in prompt
    assert "Role playbook for this document" in prompt
