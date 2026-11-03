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

Every prompt is a skill
-----------------------
Extraction, OCR, JD parsing, fit scoring and translation used to be flat prompt files read by
`prompt_file()`. They are skill packages now (ADR-006): each is a single-call role whose contract
is its body, with no methodology layers beyond it. The writing and review roles add their playbook
on top. A prompt is therefore always owned by one role, and the roles file says which.

The line to hold: a prompt is a skill package owned by a role. A prompt file outside
`skills/` is the drift to stop.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jc.domain.role_families import RolePlaybook
from jc.skills.loader import require_skill

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


def _select_layers(skill_id: str, playbook: RolePlaybook | None) -> list[tuple[str, str]]:
    """The fragments one composition of a skill carries, as `(layer_name, text)` in prompt order.

    The contract (the skill body) is always first, then the fragments the skill declares as
    `always-loaded`, then the role family's fragments. A family fragment the skill does not have
    is borrowed from the skill named by its `borrow-family-from`, never from another family.
    Every caller of this function gets the same layers: there is no per-caller exception.
    """
    skill = require_skill(skill_id)
    layers: list[tuple[str, str]] = [(f"{skill_id}:base", skill.body)]
    for topic in skill.always_loaded:
        fragment = skill.reference(topic)
        if fragment:
            layers.append((f"{skill_id}:{topic}", fragment))
    if playbook is None:
        return layers

    borrow = skill.borrow_family_from
    topic = family_reference_name(playbook)
    family = skill.reference(topic)
    if family:
        layers.append((f"{skill_id}:{topic}", family))
    elif borrow and playbook.id != "general":
        borrowed = require_skill(borrow).reference(topic)
        if borrowed:
            layers.append((f"{borrow}:{topic}", borrowed))

    if playbook.quantification_optional:
        qualitative = skill.reference(_QUALITATIVE_FRAGMENT)
        owner = skill_id
        if not qualitative and borrow:
            qualitative = require_skill(borrow).reference(_QUALITATIVE_FRAGMENT)
            owner = borrow
        if qualitative:
            layers.append((f"{owner}:{_QUALITATIVE_FRAGMENT}", qualitative))
    return layers


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
    selected = _select_layers(skill_id, playbook)
    parts = [text for _, text in selected]
    layers = [name for name, _ in selected]

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


def compose_skill_prompt(skill_id: str) -> str:
    """A skill's system prompt when no per-request composition applies: contract plus always-loaded.

    A single-call role with no family to choose (fit scoring, extraction, translation) sends exactly
    this. The writing and review roles add their playbook and document contract on top, through
    `compose_writing_prompt`.
    """
    return "\n\n".join(text for _, text in _select_layers(skill_id, None))


def compose_turn_methodology(*, skill_id: str, playbook: RolePlaybook | None) -> str:
    """The skill's contract and methodology for a conversational turn, as one system layer.

    The agent path cannot use `compose_writing_prompt`: DeerFlow owns the message list, and the
    turn's methodology reaches the model through the standing block at the system layer. The
    family's playbook block comes last when a playbook is given, so the model sees the audience
    it is writing for.
    """
    parts = [text for _, text in _select_layers(skill_id, playbook)]
    if playbook is not None:
        parts.append(_section("这份档案的岗位族", playbook.as_prompt_block()))
    return "\n\n".join(parts)
