"""Content Studio hook for Open Notebook podcast worker.

Imported via ``surreal-commands-worker --import-modules content_studio_podcast_bootstrap``
(PYTHONPATH must include ``hermes-dev/scripts``).

On import, registers short-form outline/transcript templates with ``podcast-creator``
when ``CONTENT_STUDIO_PODCAST_SHORT=1`` (default). Does not modify Open Notebook source.
"""

from __future__ import annotations

import os

from loguru import logger
from podcast_creator import configure

OUTLINE_TEMPLATE = """You are an AI assistant specialized in creating podcast outlines. Your task is to create a detailed outline for a podcast episode based on a provided briefing. The outline you create will be used to generate the podcast transcript.

Here is the briefing for the podcast episode:
<briefing>
{{ briefing }}
</briefing>

The user has provided content to be used as the context for this podcast episode:
<context>
{% if context is string %}
{{ context }}
{% else %}
{% for item in context %}
<content_piece>
{{ item }}
</content_piece>
{% endfor %}
{% endif %}
</context>

The podcast will feature the following speakers:
<speakers>
{% for speaker in speakers %}
- **{{ speaker.name }}**: {{ speaker.backstory }}
  Personality: {{ speaker.personality }}
{% endfor %}
</speakers>
{% if language %}

IMPORTANT LANGUAGE INSTRUCTION: You MUST generate ALL content in {{ language }}. This includes segment names, descriptions, and all text in your response. Do not use English unless the content itself contains English terms. The entire output must be written in {{ language }}.

{% endif %}
Please create an outline based on this briefing.

STRICT LENGTH RULES (highest priority — violating any rule is a failure):
1. Output EXACTLY {{ num_segments }} segments — no more, no less.
2. Do NOT add separate Introduction or Conclusion segments; fold hook and wrap-up into the {{ num_segments }} segments.
3. EVERY segment MUST have `"size": "short"` — NEVER use `"medium"` or `"long"`.
4. The full episode transcript (all segments combined) must stay under 600 Chinese characters.
5. Keep each segment description to 1–2 sentences; prioritize only the most important facts from context.

Additional guidelines:
1. Read the briefing carefully and identify the main topics and themes.
2. For each segment, provide a clear and concise name that reflects its content.
3. Consider the speaker personalities when planning segments.
4. Segments are topic markers only — no need to reintroduce speakers each segment.

Format your outline using the following structure:

```json
{
    "segments": [
        {
            "name": "[Segment Name]",
            "description": "[Brief description]",
            "size": "short"
        }
    ]
}
```

Formatting instructions:
{{ format_instructions}}

Additional tips:
- Do not return ```json in your response. Return purely the JSON object with a "segments" key
- The "segments" array length MUST equal {{ num_segments }}
- Every segment "size" MUST be "short"

Please provide your outline now, following the format and guidelines provided above."""

TRANSCRIPT_TEMPLATE = """You are an AI assistant specialized in creating podcast transcripts.
Your task is to generate a transcript for a specific segment of a podcast episode based on a provided briefing and outline.
The transcript will be used to generate podcast audio. Follow these instructions carefully:

First, review the briefing for the podcast episode:
<briefing>
{{ briefing }}
</briefing>

The user has provided content to be used as the context for this podcast episode:
<context>
{% if context is string %}
{{ context }}
{% else %}
{% for item in context %}
<content_piece>
{{ item }}
</content_piece>
{% endfor %}
{% endif %}
</context>

The podcast features the following speakers:
<speakers>
{% for speaker in speakers %}
- **{{ speaker.name }}**: {{ speaker.backstory }}
  Personality: {{ speaker.personality }}
{% endfor %}
</speakers>
{% if language %}

IMPORTANT LANGUAGE INSTRUCTION: You MUST generate ALL dialogue and content in {{ language }}. Every speaker's dialogue must be written entirely in {{ language }}. Do not use English unless quoting specific English terms. The entire transcript must be in {{ language }}.

{% endif %}
Next, examine the outline produced by our director:
<outline>
{{ outline }}
</outline>

{% if transcript %}
Here is the current transcript so far:
<transcript>
{{ transcript }}
</transcript>
{% endif %}

{% if is_final %}
This is the final segment of the podcast. Wrap up briefly in one short line — do not add a long conclusion.
{% endif %}

You will focus on creating the dialogue for the following segment ONLY:
<segment>
{{ segment }}
</segment>

STRICT LENGTH RULES (highest priority — violating any rule is a failure):
1. This segment must have at most {{ turns }} dialogue turns (fewer is OK if content is complete).
2. Each "dialogue" line must be at most 80 Chinese characters (or 80 words for English).
3. The ENTIRE episode transcript (previous segments plus this segment) must not exceed 600 characters total.
4. Use short, punchy sentences suitable for a 2–3 minute daily briefing podcast.
5. Do not repeat information already covered in previous transcript lines.

Follow these format requirements strictly:
   - Use the actual speaker names ({{ speaker_names|join(', ') }}) to denote speakers.
   - Choose which speaker should speak based on their personality and the content being discussed.
   - Stick to the segment; do not go beyond what is requested.
   - Each speaker should contribute meaningfully based on their expertise and personality.

```json
{
    "transcript": [
        {
            "speaker": "[Actual Speaker Name]",
            "dialogue": "[Speaker's dialogue based on their personality and expertise]"
        }
    ]
}
```

Formatting instructions:
{{ format_instructions}}

Guidelines for creating the transcript:
   - Do not return ```json in your response. Return purely the JSON object with a "transcript" key
   - Ensure the conversation flows naturally and covers points in the outline.
   - Make the dialogue sound conversational and engaging.
   - Include relevant details from the briefing and context only — skip filler.
   - Avoid long monologues; keep exchanges balanced and brief.
   - IMPORTANT: Only use the provided speaker names: {{ speaker_names|join(', ') }}

When you're ready, provide the transcript.
Remember, you are creating a realistic but SHORT podcast conversation. Brevity is mandatory."""


def apply_short_podcast_templates() -> None:
    """Register strict short-form outline/transcript templates with podcast-creator."""
    configure(
        "templates",
        {
            "outline": OUTLINE_TEMPLATE,
            "transcript": TRANSCRIPT_TEMPLATE,
        },
    )
    logger.info("Content Studio: registered short-podcast prompt templates")


def _bootstrap() -> None:
    if os.getenv("CONTENT_STUDIO_PODCAST_SHORT", "1") != "1":
        logger.info(
            "Content Studio: short-podcast templates disabled "
            "(CONTENT_STUDIO_PODCAST_SHORT=0)"
        )
        return
    apply_short_podcast_templates()


_bootstrap()
