"""Skill 包：加载 SKILL.md，把正文与参考片段拼成提示词块。

格式沿用 job-come：``skills/public/<id>/SKILL.md``（YAML frontmatter + 正文）加
``references/<topic>.md`` 片段。

两条硬约束，都是踩过坑的：

- **参考片段在组装时就内联**。job-come 里正文让模型自己 ``read_file``，而工具白名单
  没有它，正文成了死文本；语音场景更不该为读 skill 多花一次工具调用。
- **路径必须落在 skills 根之下**。skill id 与 topic 都可能来自配置或导入数据，
  ``../../x`` 必须直接报错，而不是读到根外的文件。
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from companion.config import PROJECT_ROOT

SKILL_FILENAME = "SKILL.md"
REFERENCES_DIR = "references"
DEFAULT_SKILLS_ROOT = PROJECT_ROOT / "skills" / "public"

# frontmatter 只认文件最开头、被单独一行 --- 包住的那一段。
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
# 正文里写 references/foo.md 就是在指这个片段，组装时把它读进来。
_REFERENCE_MENTION_RE = re.compile(r"references/([A-Za-z0-9._\-/]+?)\.md")


class SkillError(ValueError):
    """skill 相关的所有错误基类。"""


class SkillPathError(SkillError):
    """路径解析到了 skills 根之外。"""


class SkillFormatError(SkillError):
    """SKILL.md 的 frontmatter 不可用。"""


class SkillNotFound(SkillError):
    """skills 根下没有这个 id / 这个参考片段。"""


def _confine(root: Path, *parts: str) -> Path:
    """把 parts 拼到 root 下并断言结果仍在 root 内（解析符号链接后再比）。"""
    root_resolved = root.resolve()
    candidate = Path(root_resolved, *parts).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise SkillPathError(f"path escapes skills root: {parts!r}")
    return candidate


def _check_id(skill_id: str) -> str:
    """skill id 必须是单段目录名。``../public`` 这类虽然能解析回根内，
    但在语义上不是 id，早报错比后面糊涂更省事。"""
    if not skill_id or skill_id in {".", ".."} or any(sep in skill_id for sep in ("/", "\\", "\x00")):
        raise SkillPathError(f"invalid skill id: {skill_id!r}")
    return skill_id


def _normalize_topic(topic: str) -> str:
    """``references/tone.md``、``tone.md``、``tone`` 是同一个片段。"""
    cleaned = topic.strip()
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    if cleaned.endswith(".md"):
        cleaned = cleaned[: -len(".md")]
    return cleaned


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """拆出 frontmatter 与正文。没有 frontmatter 时返回空 dict 与全文。"""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        raw = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:  # 坏 YAML 要报出来，不能静默当空
        raise SkillFormatError(f"invalid frontmatter yaml: {exc}") from exc
    if not isinstance(raw, dict):
        raise SkillFormatError("frontmatter must be a mapping")
    return raw, text[match.end():]


def _as_str_tuple(value: object) -> tuple[str, ...]:
    """frontmatter 里既可能写列表，也可能写逗号串（allowed-tools 常见）。"""
    if value is None:
        return ()
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        items = [str(item).strip() for item in value]
    else:
        return ()
    return tuple(item for item in items if item)


def _as_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SkillPackage:
    """一个 skill 的只读视图；正文与片段都已经是字符串，不再回读磁盘。"""

    id: str
    name: str
    description: str
    allowed_tools: tuple[str, ...]
    always_loaded: bool
    body: str
    reference_topics: tuple[str, ...]
    path: Path
    root: Path = field(repr=False, compare=False)

    def read_reference(self, topic: str) -> str:
        rel = f"{_normalize_topic(topic)}.md"
        target = _confine(self.root, _check_id(self.id), f"{REFERENCES_DIR}/{rel}")
        if not target.is_file():
            raise SkillNotFound(f"reference not found: {self.id}/{REFERENCES_DIR}/{rel}")
        return target.read_text(encoding="utf-8").strip()

    def references(self) -> list[tuple[str, str]]:
        """按声明顺序读参考片段，再补上正文里点到但没声明的。"""
        topics: list[str] = []
        for topic in self.reference_topics:
            if _normalize_topic(topic) not in topics:
                topics.append(_normalize_topic(topic))
        for match in _REFERENCE_MENTION_RE.finditer(self.body):
            topic = _normalize_topic(match.group(1))
            if topic not in topics:
                topics.append(topic)
        return [(topic, self.read_reference(topic)) for topic in topics]


class SkillLibrary:
    """skills 根目录的读写门面。不做缓存：组装只在建会话 / 换角色时发生。"""

    def __init__(self, root: Path | str = DEFAULT_SKILLS_ROOT) -> None:
        self.root = Path(root).resolve()

    def skill_ids(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(
            child.name
            for child in self.root.iterdir()
            if child.is_dir() and (child / SKILL_FILENAME).is_file()
        )

    def load(self, skill_id: str) -> SkillPackage:
        path = _confine(self.root, _check_id(skill_id), SKILL_FILENAME)
        if not path.is_file():
            raise SkillNotFound(f"skill not found: {skill_id}")
        meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        metadata = meta.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise SkillFormatError(f"{skill_id}: metadata must be a mapping")
        topics = _as_str_tuple(metadata.get("references")) or _as_str_tuple(
            meta.get("references")
        )
        return SkillPackage(
            id=skill_id,
            # name 缺省时退回目录名，组装出来的块永远有个标题
            name=str(meta.get("name") or skill_id),
            description=str(meta.get("description") or "").strip(),
            allowed_tools=_as_str_tuple(meta.get("allowed-tools")),
            always_loaded=_as_bool(metadata.get("always-loaded")),
            body=body.strip(),
            reference_topics=topics,
            path=path,
            root=self.root,
        )

    def compose(
        self,
        skill_ids: Iterable[str],
        always_loaded_overrides: Mapping[str, bool] | None = None,
    ) -> str:
        """按顺序拼出提示词块：先请求的（保持顺序、去重），再常驻的（按 id 排序）。

        ``always_loaded_overrides`` 覆盖 frontmatter 的 ``metadata.always-loaded``：
        True 强制常驻，False 让常驻 skill 从自动集合里退出。显式请求的 skill 不受
        False 影响——调用方点名要的，就给它。
        """
        overrides = dict(always_loaded_overrides or {})
        requested: list[str] = []
        for skill_id in skill_ids:
            if skill_id not in requested:
                requested.append(skill_id)

        selected: list[str] = list(requested)
        for skill_id in self.skill_ids():
            if skill_id in selected:
                continue
            try:
                package = self.load(skill_id)
            except SkillError:
                # 没被点名的 skill 坏了不该拖垮建会话；点名的坏了一定要报。
                continue
            if overrides.get(skill_id, package.always_loaded):
                selected.append(skill_id)

        blocks = [self._render(self.load(skill_id)) for skill_id in selected]
        return "\n\n---\n\n".join(block for block in blocks if block)

    def _render(self, package: SkillPackage) -> str:
        parts = [f"## {package.name}"]
        if package.description:
            parts.append(f"> {package.description}")
        if package.body:
            parts.append(package.body)
        for topic, text in package.references():
            parts.append(f"### 参考：{topic}\n\n{text}")
        return "\n\n".join(parts)


def compose(
    skill_ids: Iterable[str],
    always_loaded_overrides: Mapping[str, bool] | None = None,
    root: Path | str = DEFAULT_SKILLS_ROOT,
) -> str:
    """默认根目录下的便捷入口，供宿主在组装系统提示词时调用。"""
    return SkillLibrary(root).compose(skill_ids, always_loaded_overrides)
