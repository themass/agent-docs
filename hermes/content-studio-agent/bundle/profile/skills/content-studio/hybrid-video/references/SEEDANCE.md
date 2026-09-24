# Volcengine Seedance Provider

Seedance is the preferred AI visual provider for the hybrid video pipeline. It is used only for selected `ai_broll` segments, not for every project segment.

## Role in Hybrid Pipeline

Hybrid video uses Seedance for 2-3 abstract or metaphorical clips, such as:

- opening thesis visuals
- industry transition visuals
- closing trend judgement visuals

It should not replace GitHub evidence segments. Project proof still comes from `github` segments.

## Environment Variables

```bash
VOLCENGINE_ACCESS_KEY_ID=...
VOLCENGINE_SECRET_ACCESS_KEY=...
VOLCENGINE_REGION=cn-beijing
VOLCENGINE_SEEDANCE_MODEL=<copy exact model id from Volcengine console>
VOLCENGINE_IMAGE_MODEL=<optional first-frame model id>
HYBRID_AI_PROVIDER=volcengine_seedance
```

Do not hard-code model IDs. They change by account, region, and Volcengine product release.

## Modes

`seedance_client.py` exposes a stable local interface and hides provider details from the rest of the pipeline.

Supported v1 modes:

- `text_to_video`: prompt directly generates a short video, if the configured Seedance endpoint supports it.
- `placeholder`: no API call; explains that credentials are missing and lets the pipeline create a fallback card.

Future modes:

- `image_to_video`: generate or provide a first frame, then animate it through Seedance.

## Failure Policy

Default:

```yaml
ai_broll_failure_policy: card_fallback
```

Meaning:

- Missing credentials: fallback card.
- API not implemented locally yet: fallback card.
- Request timeout: fallback card.
- Provider error: fallback card with reason in status.

Strict failure should only be enabled when the user explicitly asks for real Seedance output.

## Prompt Rules

Use English prompts. Avoid:

- screenshots of fake GitHub pages
- fake UI with unreadable text
- random programmers typing
- broad words like "coding", "AI", "technology" alone

Prefer:

- visual metaphors for the thesis
- architecture-like spatial metaphors
- clean cinematic vertical composition
- minimal or no readable text

Example:

```text
A cinematic vertical 9:16 scene representing AI agent skills becoming reusable engineering assets, modular glowing cards connected by clean data rails, dark navy background, subtle depth, no readable text, no logos, professional developer tooling atmosphere.
```
