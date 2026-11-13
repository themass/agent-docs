import pytest

from companion.skills.library import SkillFormatError, SkillLibrary, SkillNotFound, SkillPathError, split_frontmatter

SKILL_MD = """\
---
name: 语气控制
description: 让角色说话更短、更像真人
allowed-tools: set_emotion, avatar_play
metadata:
  always-loaded: false
  references: [tone, pacing]
---

正文第一段。

正文第二段。
"""


def write_skill(root, skill_id, text=SKILL_MD, refs=None):
    skill_dir = root / skill_id
    (skill_dir / "references").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")
    for topic, body in (refs or {}).items():
        (skill_dir / "references" / f"{topic}.md").write_text(body, encoding="utf-8")
    return skill_dir


@pytest.fixture
def skills_root(tmp_path):
    write_skill(
        tmp_path,
        "tone",
        refs={"tone": "语气参考。", "pacing": "节奏参考。"},
    )
    write_skill(
        tmp_path,
        "chinese-only",
        text="---\nname: 只写中文\ndescription: 不要英文\nmetadata:\n  always-loaded: true\n---\n\n中文正文。\n",
    )
    return tmp_path


def test_split_frontmatter_reads_mapping_and_body():
    meta, body = split_frontmatter(SKILL_MD)
    assert meta["name"] == "语气控制"
    assert meta["metadata"]["references"] == ["tone", "pacing"]
    assert body.lstrip().startswith("正文第一段。")


def test_split_frontmatter_absent_returns_whole_text():
    meta, body = split_frontmatter("# 没有 frontmatter\n\n正文\n")
    assert meta == {}
    assert body.startswith("# 没有 frontmatter")


def test_split_frontmatter_rejects_broken_yaml():
    with pytest.raises(SkillFormatError):
        split_frontmatter("---\nname: [unclosed\n---\n\n正文\n")


def test_load_parses_frontmatter(two_skills):
    package = two_skills.load("tone")
    assert package.name == "语气控制"
    assert package.description == "让角色说话更短、更像真人"
    # allowed-tools 写的是逗号串，要拆成元组
    assert package.allowed_tools == ("set_emotion", "avatar_play")
    assert package.always_loaded is False
    assert "正文第二段。" in package.body


def test_load_reads_named_references(two_skills):
    package = two_skills.load("tone")
    refs = dict(package.references())
    assert refs == {"tone": "语气参考。", "pacing": "节奏参考。"}


def test_load_picks_up_reference_mentioned_in_body(tmp_path):
    write_skill(
        tmp_path,
        "mood",
        text="---\nname: 情绪\ndescription: d\n---\n\n细节见 references/gaze.md。\n",
        refs={"gaze": "视线参考。"},
    )
    refs = dict(SkillLibrary(tmp_path).load("mood").references())
    assert refs == {"gaze": "视线参考。"}


def test_reference_path_escape_is_rejected(skills_root):
    package = SkillLibrary(skills_root).load("tone")
    with pytest.raises(SkillPathError):
        package.read_reference("../../../etc/passwd")


def test_skill_id_escape_is_rejected(skills_root):
    library = SkillLibrary(skills_root)
    for bad in ("../../secret", "tone/../../etc", "..", "/etc", "", "a\\b"):
        with pytest.raises(SkillPathError):
            library.load(bad)


def test_symlinked_references_dir_is_rejected(skills_root, tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "secret.md").write_text("不该被读到", encoding="utf-8")

    skill_dir = skills_root / "linked"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: 链接\nmetadata:\n  references: [secret]\n---\n\n正文\n", encoding="utf-8"
    )
    (skill_dir / "references").symlink_to(outside, target_is_directory=True)

    with pytest.raises(SkillPathError):
        SkillLibrary(skills_root).load("linked").references()


def test_missing_skill_raises(skills_root):
    with pytest.raises(SkillNotFound):
        SkillLibrary(skills_root).load("nope")


def test_missing_reference_raises(skills_root):
    with pytest.raises(SkillNotFound):
        SkillLibrary(skills_root).load("tone").read_reference("absent")


def test_compose_order_and_dedupe(skills_root):
    text = SkillLibrary(skills_root).compose(["tone", "tone"])
    assert text.count("## 语气控制") == 1


def test_compose_appends_always_loaded_after_requested(skills_root):
    text = SkillLibrary(skills_root).compose(["tone"])
    # tone 不是常驻，中文本 skill 是常驻，所以它被追加到后面
    assert text.index("## 语气控制") < text.index("## 只写中文")


def test_compose_override_forces_and_suppresses(skills_root):
    library = SkillLibrary(skills_root)
    forced = library.compose([], {"tone": True})
    assert "## 语气控制" in forced

    suppressed = library.compose([], {"chinese-only": False})
    assert "## 只写中文" not in suppressed

    # 显式请求的不因 False 覆盖而消失
    assert "## 只写中文" in library.compose(["chinese-only"], {"chinese-only": False})


def test_compose_inlines_references(skills_root):
    text = SkillLibrary(skills_root).compose(["tone"])
    assert "语气参考。" in text
    assert "### 参考：tone" in text


def test_reference_topic_forms_dedupe(skills_root):
    package = SkillLibrary(skills_root).load("tone")
    # 声明用裸名，正文写 references/pacing.md：同一片段只出现一次
    assert [topic for topic, _ in package.references()] == ["tone", "pacing"]
    assert package.read_reference("tone.md") == package.read_reference("tone")
    assert package.read_reference("./tone") == "语气参考。"


def test_broken_unrequested_skill_does_not_break_compose(skills_root):
    broken = skills_root / "broken"
    broken.mkdir()
    (broken / "SKILL.md").write_text("---\nname: [unclosed\n---\n\n正文\n", encoding="utf-8")
    # 坏了但没被点名：跳过；点名了就报错
    assert "## 语气控制" in SkillLibrary(skills_root).compose(["tone"])
    with pytest.raises(SkillFormatError):
        SkillLibrary(skills_root).compose(["broken"])


def test_skill_ids_lists_only_directories_with_skill_md(tmp_path):
    write_skill(tmp_path, "one")
    (tmp_path / "empty").mkdir()
    (tmp_path / "loose.md").write_text("x", encoding="utf-8")
    assert SkillLibrary(tmp_path).skill_ids() == ["one"]


@pytest.fixture(name="two_skills")
def two_skills_fixture(skills_root):
    return SkillLibrary(skills_root)
