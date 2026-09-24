# Hybrid Visual Prompt Guide

Hybrid prompts should make visuals more relevant than generic stock footage while keeping the GitHub evidence chain intact.

## Segment Selection

Use `ai_broll` only for:

- `intro-ai-broll`: visualizes the thesis.
- one mid-video metaphor segment: visualizes the workflow or industry shift.
- `outro-ai-broll`: visualizes the long-term judgement.

Do not use `ai_broll` for every repository. Repository proof belongs to `github` segments.

## Prompt Formula

```text
[visual metaphor] + [technical meaning] + [composition] + [style] + [constraints]
```

Example:

```text
A vertical cinematic visualization of open-source AI agents turning scattered prompts into reusable skill modules, glowing modular blocks snapping into a version-controlled workflow, dark navy interface space, subtle motion potential, clean professional developer-tool aesthetic, no readable text, no logos.
```

## Good Prompts

### Thesis

```text
A clean vertical 9:16 scene showing AI agent workflows becoming structured engineering pipelines, modular cards connected by luminous rails, professional dark interface atmosphere, subtle depth, no readable text, no logos.
```

### Cost / Routing

```text
A cinematic vertical diagram-like scene of AI requests flowing through a smart routing gateway, high-cost and low-cost paths splitting into different glowing channels, precise technical mood, no readable text, no logos.
```

### Local / Private Deployment

```text
A secure local AI workspace visualized as a private server room inside a developer laptop, agent nodes operating behind a protective glass boundary, clean futuristic but realistic, no readable text, no logos.
```

## Bad Prompts

Avoid:

```text
coding, developer, AI, technology
```

Why: these produce the same generic visuals as Pixabay.

Avoid:

```text
GitHub screenshot of owner/repo with stars and README
```

Why: generated screenshots will be fake. Use real `github` segments for evidence.

Avoid:

```text
Chinese text on screen, project names on UI, exact logos
```

Why: generated text is unreliable and can create trademark or misinformation issues.

## Negative Prompt

Default:

```text
watermark, logo, fake text, unreadable text, blurry, distorted hands, deformed UI, low quality, random stock footage, generic programmer typing
```

## Quality Gate

Before accepting a prompt:

- Does it map to a specific thesis or metaphor?
- Does it avoid fake evidence?
- Would this still make sense without text?
- Is it visually distinct from generic `coding` footage?
