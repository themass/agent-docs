"""Compose a role's system prompt from skill fragments.

The selection problem
---------------------
"Different jobs need different resume methodology" is easy to assert and easy to
implement wrongly. Two wrong versions were already in the tree:

- **One prompt for everyone.** The 340-line writer prompt carried every rule for
  every role, so a legal candidate's prompt spent its strongest instructions on
  metric ladders that do not apply, and the model was told to demand numbers that
  the role legitimately does not produce.
- **Sixteen prompts.** The obvious fix, and worse: the honesty rules would be
  copied sixteen times and would drift apart within a month. The rule that matters
  most ("never invent a fact") must exist exactly once.

So the composition is layered, and the layers are ordered by how universal they
are. Everything above a role's own fragments is identical for all roles:

    1. base        the skill's own contract — identity, scope, hard prohibitions
    2. method      how any bullet is written (Action + Object + Outcome)
    3. structure   how any document is assembled (conclusion-first, scope lines)
    4. family      what *this* audience reads for, and which rules relax here
    5. document    the measurable bar for this specific document

Only layer 4 varies by role. That keeps the honesty rules single-sourced while
still letting a sales resume and an SRE resume be written to different standards.

What varies and what may not
----------------------------
A family fragment may change **what evidence to look for, which vocabulary to use,
what reads as concrete, and which warnings are legitimate.** It may never change
what counts as a fact or relax the prohibition on inventing one. That boundary is
restated in the shared layers rather than per family, so a family fragment cannot
be written in a way that quietly overrides it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jc.domain.role_families import RolePlaybook
from jc.skills.loader import require_skill

#: Fragments a skill always loads, in prompt order. These carry the rules that must
#: not vary by audience, which is why they sit outside the per-family selection.
#:
#: Keyed by skill because the writer and the reviewer need different universal
#: layers: the writer is told how to build a document, the reviewer is told what
#: severity to assign and what counts as source evidence. A skill not listed here
#: contributes only its SKILL.md plus whatever family fragment applies.
_ALWAYS_LOADED: dict[str, tuple[str, ...]] = {
    "resume-writer": ("structure", "method", "targeting"),
    "resume-reviewer": ("severity", "method", "structure", "evidence"),
    "resume-coach": ("method",),
    "profile-interview": ("method",),
}

#: The skill whose identity the agent runtime already carries, via `config.yaml` and the
#: turn wrapper. Guidance for *this* skill omits its own contract text, because sending
#: it again inside the user message duplicates the role definition at the weaker of the
#: two positions.
#:
#: Guidance for any *other* skill must include the contract, and that is not symmetry for
#: its own sake: `profile-interview`'s contract is precisely the instruction that this
#: turn is for asking rather than editing, which contradicts the registered identity.
#: Drop it and the model keeps behaving like an editor while holding interview
#: methodology — the worst of both, and it would look like the skill was loaded.
_REGISTERED_AGENT_SKILL = "resume-coach"

#: Role families whose outcomes are often qualitative share one fragment rather
#: than each carrying a near-copy. `quantification_optional` on the playbook is the
#: same signal the reviewer uses, so the writer and the reviewer cannot disagree
#: about whether this role owes a number.
_QUALITATIVE_FRAGMENT = "qualitative-outcomes"


@dataclass(frozen=True, slots=True)
class ComposedPrompt:
    """A system prompt plus the provenance of what went into it.

    `layers` exists so a composition problem is diagnosable from an audit row or a
    test without re-deriving the selection: "this document was written with the
    management fragment and no qualitative fragment" is a fact worth keeping.
    """

    text: str
    layers: tuple[str, ...] = field(default=())

    def __str__(self) -> str:
        return self.text


def _section(title: str, body: str) -> str:
    return f"## {title}\n{body.strip()}"


def family_reference_name(playbook: RolePlaybook) -> str:
    """The fragment topic for this family, by convention `families/<id>`.

    Families without their own fragment fall back to the shared baseline rather
    than to another family's: being written to the wrong audience's standard is a
    worse failure than being written to a neutral one.
    """
    return f"family-{playbook.id}"


def compose_writing_prompt(
    *,
    skill_id: str,
    playbook: RolePlaybook,
    document_contract: str = "",
    extra_sections: tuple[tuple[str, str], ...] = (),
) -> ComposedPrompt:
    """Build the system prompt for a writing-side role.

    `skill_id` decides the contract and the fragment pool, so the writer and the
    reviewer can share this function while reading their own methodology. A skill
    that lacks a requested fragment contributes nothing for it — reference sets
    differ by role on purpose and a missing topic is not an error.
    """
    skill = require_skill(skill_id)
    parts: list[str] = [skill.body]
    layers: list[str] = [f"{skill_id}:base"]

    for topic in _ALWAYS_LOADED.get(skill_id, ()):
        fragment = skill.reference(topic)
        if fragment:
            parts.append(fragment)
            layers.append(f"{skill_id}:{topic}")

    family_fragment = skill.reference(family_reference_name(playbook))
    if family_fragment:
        parts.append(family_fragment)
        layers.append(f"{skill_id}:{family_reference_name(playbook)}")

    if playbook.quantification_optional:
        qualitative = skill.reference(_QUALITATIVE_FRAGMENT)
        if qualitative:
            parts.append(qualitative)
            layers.append(f"{skill_id}:{_QUALITATIVE_FRAGMENT}")

    # The playbook is rendered rather than stored as a fragment: it is already the
    # single source of role vocabulary for the reviewer and the UI, and a second
    # copy in a markdown file is exactly the drift this module exists to avoid.
    parts.append(_section("Role playbook for this document", playbook.as_prompt_block()))
    layers.append(f"playbook:{playbook.id}")

    if document_contract.strip():
        parts.append(_section("The bar this document must clear", document_contract))
        layers.append("blueprint")

    for title, text in extra_sections:
        if text and text.strip():
            parts.append(_section(title, text))
            layers.append(f"extra:{title}")

    return ComposedPrompt(text="\n\n".join(parts), layers=tuple(layers))


def compose_role_baseline(skill_id: str) -> str:
    """The part of a role's prompt that does not depend on which job the user wants.

    Exists for one caller: the generated DeerFlow runtime config, which declares JC's
    roles as subagents and whose schema requires a `system_prompt` string. That string
    used to be three hand-written English lines per role, sitting in `config.yaml`
    alongside the skill package that says the same thing properly — a second definition
    of the role, in a file nobody re-reads, already drifted from the first.

    Static YAML genuinely cannot carry the whole prompt: the family layer is chosen per
    request from the user's target role, and a file written at boot has no request. So
    this returns exactly the layers that are the same for everyone — the skill's own
    contract and its always-loaded methodology — and the per-request composition stays
    with `compose_writing_prompt`, which is what actually runs today. The result is one
    source of truth with a documented seam, rather than two sources pretending to agree.
    """
    skill = require_skill(skill_id)
    parts: list[str] = [skill.body]
    for topic in _ALWAYS_LOADED.get(skill_id, ()):
        fragment = skill.reference(topic)
        if fragment:
            parts.append(fragment)
    return "\n\n".join(parts)


def compose_coach_guidance(*, skill_id: str, playbook: RolePlaybook) -> str:
    """Methodology for a conversational turn, without the skill's own identity text.

    The agent path cannot use `compose_writing_prompt`: DeerFlow owns the system
    prompt, and the skill's identity ("you are the resume coach, reply in Chinese")
    already reaches the model through `config.yaml` and the turn wrapper. Sending it
    again inside the user message would duplicate the role definition and put it at
    the weaker of the two positions.

    What the agent path is actually missing is the **methodology** — how to rewrite
    a bullet, what to look for when the user says "丰富一点", and what this role
    family is read for. That is what this returns.

    Returns an empty string when the skill ships no fragments, so a caller can
    append unconditionally.
    """
    skill = require_skill(skill_id)
    parts: list[str] = []
    if skill_id != _REGISTERED_AGENT_SKILL:
        parts.append(skill.body)

    for topic in _ALWAYS_LOADED.get(skill_id, ()):
        fragment = skill.reference(topic)
        if fragment:
            parts.append(fragment)

    family_fragment = skill.reference(family_reference_name(playbook))
    if family_fragment:
        parts.append(family_fragment)
    elif playbook.id != "general":
        # The coach keeps no per-family fragments of its own: the writer's are
        # written for the same audience and saying it twice in two voices is how
        # the two drift. Falling back to the writer's is deliberate, and only for
        # the family layer — never for identity or output contract.
        writer = require_skill("resume-writer")
        borrowed = writer.reference(family_reference_name(playbook))
        if borrowed:
            parts.append(borrowed)

    if playbook.quantification_optional:
        qualitative = skill.reference(_QUALITATIVE_FRAGMENT) or require_skill(
            "resume-writer"
        ).reference(_QUALITATIVE_FRAGMENT)
        if qualitative:
            parts.append(qualitative)

    if not parts:
        return ""
    parts.append(_section("这份档案的岗位族", playbook.as_prompt_block()))
    return "\n\n".join(parts)
