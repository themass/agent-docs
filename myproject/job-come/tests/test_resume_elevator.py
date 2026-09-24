from jobcome.services.resume_elevator import ResumeElevator


def test_split_bullet_keeps_full_sentence() -> None:
    long = "精通 Docker 源码，给内源的 Docker 版本修复了 40 多个 bug，向开源社区提交了 10 多个 patch，对容器相关技术有很深的研究。"
    assert ResumeElevator._split_bullet(long) == [long]


def test_split_bullet_on_semicolon() -> None:
    text = "维护内源 Docker；提交上游 patch"
    assert ResumeElevator._split_bullet(text) == ["维护内源 Docker", "提交上游 patch"]


def test_trim_bullets_does_not_ellipsis() -> None:
    bullets = [
        "作为组内 Docker 技术重要的底层技术之一 cgroup 的内核维护者，负责调度与隔离相关问题排查。",
        "b",
    ]
    out = ResumeElevator._trim_bullets(bullets)
    assert "…" not in out[0]
    assert out[0].startswith("作为组内")
