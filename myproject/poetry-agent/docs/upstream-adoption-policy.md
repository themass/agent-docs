# Upstream Prompt, Skill and Persona Adoption Policy

We adopt mature patterns, not unreviewed behavior. External prompt/skill repositories are **sources**, never runtime authorities.

## Four adoption lanes

| Lane | What may enter | Example use | Gate |
|---|---|---|---|
| Reference | Link and ADR only | 12-factor checklist | Maintainer review |
| Template | Structure with all content rewritten | Agent frontmatter; skill folder layout | License + prompt review |
| Adapted skill | Local immutable copy with change log | `annotation-design` workflow | tool allow-list + red-team + eval |
| Runtime integration | Versioned code/MCP package | official MCP SDK | SCA, provenance, deployment review |

No repository is cloned into `deerflow-profile/skills` wholesale. No remote prompt is fetched at runtime. No imported skill is granted tools merely because its upstream version requested them.

## Required review card

Every candidate must have `content-agent/deploy/upstream/catalog.yaml` metadata: upstream URL, commit SHA, license, source file path, intended use, copied/adapted sections, requested tools, data classification, prompt-injection risk, reviewer and version.

## Immediate curated sources

1. `msitarzewski/agency-agents`: role/brief/deliverable **template** source only. Adapt its specialized-role framing for editorial and creative-production support; never import its tool assumptions.
2. `PlexPt/awesome-chatgpt-prompts-zh`: Chinese wording and interaction **inspiration corpus** only. Individual role-play prompts do not meet our evidence, output-schema or safety requirements.
3. `anthropics/skills`: portable SKILL.md packaging and on-demand skill pattern reference.
4. `github/awesome-copilot`: discovery catalog for agents/skills/instructions; individual third-party items require review before adoption.
5. `humanlayer/12-factor-agents`: architecture checklist, especially prompt/context ownership, tool contracts, business-state alignment, pause/resume and human tool calls.
6. `microsoft/ai-agents-for-beginners`: training/evaluation vocabulary and example learning material, not our runtime framework.

## Poetry-specific exclusion policy

Reject an upstream item if it asks for SQL, unrestricted shell/filesystem/browser access, autonomous social publishing, source verification, content release, hidden remote downloads, secret access, or lacks an inspectable license/provenance chain.
