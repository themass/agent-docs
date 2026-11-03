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

Why `backend/agent/prompts/` still exists
-----------------------------------------
Two prompt systems live side by side, and the split is deliberate rather than a
migration someone abandoned halfway:

- **`backend/agent/skills/`** — composed here. For tasks that *write resume prose*:
  the writer, the reviewer, the coach, the interview. These share a methodology and
  one definition of what counts as a fact, which is exactly what layering buys.
- **`backend/agent/prompts/`** — flat files loaded by `prompt_file()`. For tasks that
  *read* rather than write: ingestion, vision OCR, JD parsing, fit scoring,
  localization. Each is a single-purpose extraction contract with its own output
  schema. They share no methodology with each other or with the writer, so layering
  them would build an abstraction over one user apiece.

Both say "do not invent facts", and that is **not** the duplication this module
exists to prevent. "Do not invent a fact while extracting what a PDF says" and "do
not invent a fact while rewriting an achievement" are different rules about different
inputs that happen to read alike in English. Merging them would couple the extraction
contract to the writing methodology, which is a worse outcome than the shared
sentence.

The line to hold: a prompt that produces resume prose belongs in `skills/`. If one is
ever added under `prompts/`, that is the drift to stop.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jc.agent.roles import role_of
from jc.agent.roles import skill as declared_skill
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


def _select_layers(
    skill_id: str,
    playbook: RolePlaybook | None,
    *,
    include_identity: bool = True,
    borrow_family_from: str | None = None,
) -> list[tuple[str, str]]:
    """Pick the fragments for one composition, as `(layer_name, text)` in prompt order.

    The three public functions below differ only in what they *render* — a system
    prompt, a user-message appendix, a static baseline for the generated runtime
    config. They used to differ in how they *selected* too, each re-walking the skill's
    `always_loaded` fragments, then family, then qualitative, with slightly different fallbacks.
    Three copies of a selection order drift the same way sixteen copies of a prompt
    would, and worse: the drift lives in control flow rather than in markdown, where
    nobody re-reads it. The selection exists once, here.

    `include_identity=False` drops the skill's own contract text, for the one caller
    whose runtime already carries it. `borrow_family_from` names a skill to fall back
    to for the family layer only — never for identity or output contract.
    """
    skill = require_skill(skill_id)
    layers: list[tuple[str, str]] = []
    if include_identity:
        layers.append((f"{skill_id}:base", skill.body))

    for topic in declared_skill(skill_id).always_loaded:
        fragment = skill.reference(topic)
        if fragment:
            layers.append((f"{skill_id}:{topic}", fragment))

    if playbook is None:
        return layers

    topic = family_reference_name(playbook)
    family_fragment = skill.reference(topic)
    if family_fragment:
        layers.append((f"{skill_id}:{topic}", family_fragment))
    elif borrow_family_from and playbook.id != "general":
        borrowed = require_skill(borrow_family_from).reference(topic)
        if borrowed:
            layers.append((f"{borrow_family_from}:{topic}", borrowed))

    if playbook.quantification_optional:
        qualitative = skill.reference(_QUALITATIVE_FRAGMENT)
        owner = skill_id
        if not qualitative and borrow_family_from:
            qualitative = require_skill(borrow_family_from).reference(_QUALITATIVE_FRAGMENT)
            owner = borrow_family_from
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
    return "\n\n".join(text for _, text in _select_layers(skill_id, None))


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

    The coach keeps no per-family fragments of its own: the writer's are written for
    the same audience, and saying it twice in two voices is how the two drift. The
    borrow is deliberate, and only for the family layer — never for identity or
    output contract.
    """
    selected = _select_layers(
        skill_id,
        playbook,
        # The role's default skill is the one the agent runtime already carries, through
        # `config.yaml` and the turn wrapper. Guidance for it omits its own contract text,
        # because sending it again inside the user message duplicates the role definition at
        # the weaker of the two positions. Guidance for any *other* skill of the role must
        # include the contract, and that is not symmetry for its own sake: the interview
        # skill's contract is precisely the instruction that this turn is for asking rather
        # than editing, which contradicts the registered identity. Drop it and the model keeps
        # behaving like an editor while holding interview methodology.
        include_identity=skill_id != role_of(skill_id).default_skill.id,
        borrow_family_from="resume-writer",
    )
    if not selected:
        return ""
    parts = [text for _, text in selected]
    parts.append(_section("这份档案的岗位族", playbook.as_prompt_block()))
    return "\n\n".join(parts)
