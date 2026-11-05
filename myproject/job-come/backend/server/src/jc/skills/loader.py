"""Load role-scoped methodology from skill packages on disk.

Why this module exists
----------------------
JC's writing methodology lived entirely inside `prompts/elevate/resume_writer.md`
(340 lines) while `skills/public/*/SKILL.md` held 10-line stubs. That split was not
a tidiness problem, it was a reachability problem, and it had two separate causes
that have to be fixed in different ways:

1. **The agent path could not read a skill body at all.** DeerFlow injects only a
   skill's *name, description and location* into the system prompt; the body is
   loaded when the model calls `read_file` on that location. JC's tool allowlist
   (`deerflow_harness_client._get_tools`) strips every tool outside the role's `tools`,
   and `read_file` is deliberately not in it — V1 does not give the agent host file
   access. So the progressive-loading contract DeerFlow advertises to the model
   could never complete, and every SKILL.md body was dead text.

2. **The engineering path had no notion of skills.** `resume_elevator` read one
   prompt file and appended playbook text, so a role family could change vocabulary
   but never change *methodology*.

Both are fixed by the same move: skills become **data the host composes**, not files
the model fetches. The host reads the body, selects the fragments this role actually
needs, and puts them in the system prompt itself. Nothing depends on the model
choosing to read a file, and the agent still gets no filesystem access.

What a skill package is
-----------------------
    skills/public/<skill-id>/
        SKILL.md                    the contract: what this way of working is, and
                                    its frontmatter declares what it may use
        references/<topic>.md       methodology fragments, loaded by name

Frontmatter (the Agent Skills standard, which DeerFlow also reads):

    ---
    name: resume-coach                # must equal the folder name
    description: ...                  # shown to the model in the skill listing
    allowed-tools: [jc_profile_get]   # the tools a run of this skill may hold
    metadata:                         # JC's own keys; unknown keys are an error
      always-loaded: [method]         # references every composition carries
      borrow-family-from: resume-writer
    ---

`SKILL.md` is the always-loaded part and stays short. `references/*.md` are loaded
selectively: a backend resume and a legal resume pull different fragments, which is
the whole point of saying "different roles have different methodology".

Trust
-----
Skill content is **first-party authored** and ships with the repo, so it is trusted
input to the system prompt — unlike a profile or a JD. Reading is confined to
`skills/public` and `skills/custom` under the configured root, and a reference name
that escapes that root raises rather than resolving: the selection key reaching this
layer is derived from a role family id, but it must not be possible for a future
caller to turn it into an arbitrary file read.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from jc.config import settings
from jc.paths import resolve_under_server

logger = logging.getLogger(__name__)

_FRONTMATTER_FENCE = "---"


@dataclass(frozen=True, slots=True)
class SkillPackage:
    """One skill: its contract, the references it can offer, and what it declares."""

    id: str
    description: str
    #: SKILL.md with its YAML frontmatter stripped.
    body: str
    #: Reference topic name -> file contents, for every file under `references/`.
    references: dict[str, str]
    #: The tool names a run of this skill may hold (standard `allowed-tools`).
    allowed_tools: tuple[str, ...]
    #: Reference topics every composition of this skill carries, in prompt order.
    always_loaded: tuple[str, ...]
    #: A skill that has no family fragments of its own borrows them from this skill.
    borrow_family_from: str | None
    #: Which view of a role family this skill is given: "writing" (how to write a résumé for that
    #: audience, the default) or "interview" (where to probe and what a good answer shows).
    playbook_view: str = "writing"

    def reference(self, name: str) -> str:
        """Return one reference body, or empty string when this skill has no such topic.

        Missing is not an error: reference sets differ per skill on purpose, and a
        caller composing a prompt for several skills asks each of them for the same
        topic list.
        """
        return self.references.get(name, "")


def _skills_roots() -> tuple[Path, ...]:
    root = resolve_under_server(settings.jc_skills_root)
    return tuple(p for p in (root / "public", root / "custom") if p.is_dir())


_METADATA_KEYS = frozenset({"always-loaded", "borrow-family-from", "playbook"})
_PLAYBOOK_VIEWS = ("writing", "interview")


def _parse_skill_markdown(text: str, *, where: Path) -> tuple[dict, str]:
    """Split a SKILL.md into (frontmatter, body). Malformed first-party content is an error."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        raise ValueError(f"{where}: SKILL.md must start with a frontmatter block")
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_FENCE:
            front = yaml.safe_load("\n".join(lines[1:index])) or {}
            if not isinstance(front, dict):
                raise ValueError(f"{where}: frontmatter must be a mapping")
            return front, "\n".join(lines[index + 1 :]).strip()
    raise ValueError(f"{where}: frontmatter is not terminated")


def _names(value: object, *, where: Path, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise ValueError(f"{where}: {key} must be a list of names")
    return tuple(value)


def _package(skill_dir: Path, text: str) -> SkillPackage:
    where = skill_dir / "SKILL.md"
    front, body = _parse_skill_markdown(text, where=where)
    name, description = front.get("name"), front.get("description")
    if name != skill_dir.name:
        raise ValueError(f"{where}: name {name!r} must equal the folder name {skill_dir.name!r}")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"{where}: description is required")
    metadata = front.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"{where}: metadata must be a mapping")
    unknown = set(metadata) - _METADATA_KEYS
    if unknown:
        raise ValueError(f"{where}: unknown metadata keys {sorted(unknown)}")
    borrow = metadata.get("borrow-family-from")
    if borrow is not None and not isinstance(borrow, str):
        raise ValueError(f"{where}: borrow-family-from must be a skill id")
    view = metadata.get("playbook", "writing")
    if view not in _PLAYBOOK_VIEWS:
        raise ValueError(f"{where}: playbook must be one of {_PLAYBOOK_VIEWS}, got {view!r}")
    return SkillPackage(
        id=skill_dir.name,
        description=description.strip(),
        body=body,
        references=_load_references(skill_dir),
        allowed_tools=_names(front.get("allowed-tools"), where=where, key="allowed-tools"),
        always_loaded=_names(metadata.get("always-loaded"), where=where, key="always-loaded"),
        borrow_family_from=borrow,
        playbook_view=view,
    )


def _load_references(skill_dir: Path) -> dict[str, str]:
    refs_dir = skill_dir / "references"
    if not refs_dir.is_dir():
        return {}
    out: dict[str, str] = {}
    for path in sorted(refs_dir.glob("*.md")):
        out[path.stem] = path.read_text(encoding="utf-8").strip()
    return out


@lru_cache(maxsize=1)
def _packages() -> dict[str, SkillPackage]:
    """Read every skill package once per process.

    Cached because this is first-party content that cannot change under a running
    server, and the writer path would otherwise re-read a dozen files per request.
    `reload_skills()` exists for tests that write packages to a temp root.
    """
    found: dict[str, SkillPackage] = {}
    for root in _skills_roots():
        for skill_md in sorted(root.glob("*/SKILL.md")):
            skill_id = skill_md.parent.name
            if skill_id in found:
                # public wins over custom: a vendored skill must not silently
                # replace the one this product's behaviour is specified against.
                continue
            found[skill_id] = _package(skill_md.parent, skill_md.read_text(encoding="utf-8"))
    if not found:
        logger.warning("No skill packages found under %s", [str(p) for p in _skills_roots()])
    return found


def reload_skills() -> None:
    """Drop the package cache. For tests and for a deliberate hot reload."""
    _packages.cache_clear()


def get_skill(skill_id: str) -> SkillPackage | None:
    return _packages().get(skill_id)


def require_skill(skill_id: str) -> SkillPackage:
    """Fetch a skill the caller's behaviour depends on.

    Raises rather than degrading: a writer that silently loses its methodology
    still returns a resume, so the failure would reach the user as a quietly worse
    document instead of an error anyone notices.
    """
    package = get_skill(skill_id)
    if package is None:
        raise LookupError(
            f"skill package {skill_id!r} not found under "
            f"{[str(p) for p in _skills_roots()]}"
        )
    return package


def all_skill_ids() -> tuple[str, ...]:
    return tuple(sorted(_packages()))
