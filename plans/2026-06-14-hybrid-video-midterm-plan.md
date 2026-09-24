# Hybrid Video Midterm Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a third, independent hybrid video pipeline that uses storyboard-driven related visuals and optional Volcengine Seedance AI assets, without changing or replacing the current sop and mpt video pipelines.

**Architecture:** Keep the existing `video-pipeline` and `moneyprinter-video` commands untouched. Add a new Content Studio Skill and script that produce `*-hybrid-video.mp4` from the same daily report and script inputs, using a hybrid production spec with `asset_type` and `visual_prompt` fields. The first midterm version should focus on deterministic storyboard/spec generation, concept/card assets, GitHub evidence segments, and 2-3 AI visual segments.

**Tech Stack:** Hermes Content Studio Skills, Bash orchestration, Python 3.12, ffmpeg, existing GitHub visual renderer modules, optional Volcengine Seedance API, Markdown/YAML production specs.

---

## 1. Decision Summary

We will not discard or weaken the two current video links:

| Link | Current command | Output | Role |
|------|-----------------|--------|------|
| sop video | `content-studio.sh video-pipeline [DATE]` | `YYYY-MM-DD-video.mp4` | Main evidence video with GitHub scroll/callouts. |
| mpt video | `content-studio.sh video-mpt-pipeline [DATE]` | `YYYY-MM-DD-mpt-video.mp4` | Fast narration + stock B-roll preview video. |
| hybrid video | `content-studio.sh video-hybrid-pipeline [DATE]` | `YYYY-MM-DD-hybrid-video.mp4` | New third link: storyboard-driven related visuals, cards, GitHub evidence, and selected AI-generated assets. |

The new work must be additive:

- Do not change the meaning of `video-pipeline`.
- Do not change the meaning of `video-mpt` or `video-mpt-pipeline`.
- Do not overwrite `*-video.mp4` or `*-mpt-video.mp4`.
- New outputs use `*-hybrid-*`.
- Shared skills may be strengthened only in backward-compatible ways.

## 2. Why Hybrid Exists

MPT is useful for fast preview videos, but its stock B-roll is too generic for GitHub project introductions. The hybrid pipeline should solve that without losing the evidence-first quality of sop videos.

The hybrid pipeline should combine:

- **GitHub evidence**: repository page scroll/callouts for real project proof.
- **Concept cards**: thesis, project role, capability breakdown, and summary cards.
- **AI visuals**: only 2-3 carefully selected abstract/metaphor segments, generated from storyboard prompts.
- **Optional motion**: start with still images plus simple motion; later add text-to-video or image-to-video with Seedance.

## 3. Naming and Files

Create a new Skill:

```text
/Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/
  SKILL.md
  references/
    SEEDANCE.md
    VISUAL_PROMPT_GUIDE.md
  templates/
    hybrid-production-spec.yaml
    hybrid-storyboard.md
  scripts/
    hybrid_video.py
    hybrid_spec.py
    hybrid_assets.py
    seedance_client.py
    hybrid_compositor.py
```

Add new orchestration commands in:

```text
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh
```

New commands:

```bash
content-studio.sh video-hybrid DATE
content-studio.sh video-hybrid-pipeline DATE
content-studio.sh hybrid-status DATE
```

Add routing only for new phrases:

```text
生成 hybrid视频
hybrid视频
生成 AI增强视频
生成相关素材视频
```

These routes should call the new `hybrid-video` Skill and must use `terminal`, not `execute_code`.

## 4. Output Contract

For `DATE=2026-06-14`, the hybrid pipeline writes:

```text
reports/2026/06/
  2026-06-14-video-script.md                 # existing shared script
  2026-06-14-hybrid-storyboard.md            # new
  2026-06-14-hybrid-production-spec.yaml     # new
  2026-06-14-hybrid-video.mp4                # new
  2026-06-14-hybrid-video-cover.jpg          # new
  2026-06-14-hybrid-video-publish.md         # new
  assets/2026-06-14-hybrid/
    cards/
    github/
    ai-broll/
    clips/
```

The current two video outputs remain unchanged:

```text
2026-06-14-video.mp4
2026-06-14-mpt-video.mp4
```

## 5. Hybrid Production Spec

The hybrid spec is separate from the current `storyboard-planner/templates/production-spec.yaml` so today's work does not destabilize sop rendering.

Minimum v1 structure:

```yaml
version: 1
profile: content-studio
pipeline: hybrid-video

metadata:
  date: "YYYY-MM-DD"
  source_report: "/Users/gqli/.hermes/profiles/content-studio/reports/YYYY/MM/YYYY-MM-DD.md"
  script_file: "/Users/gqli/.hermes/profiles/content-studio/reports/YYYY/MM/YYYY-MM-DD-video-script.md"
  output_video: "/Users/gqli/.hermes/profiles/content-studio/reports/YYYY/MM/YYYY-MM-DD-hybrid-video.mp4"

render_policy:
  preserve_existing_pipelines: true
  fail_fast_on_github: true
  ai_broll_failure_policy: card_fallback
  max_ai_broll_segments: 3

theme:
  thesis: "一句行业判断"
  trend_label: "趋势标签"

segments:
  - id: intro-thesis
    asset_type: card
    visual_type: concept_card
    duration_seconds: 12
    narration_ref: intro
    card:
      title: "趋势标签"
      subtitle: "一句 thesis"
      bullets:
        - "证据 1"
        - "证据 2"

  - id: intro-ai-broll
    asset_type: ai_broll
    visual_type: ai_generated
    duration_seconds: 6
    narration_ref: intro_metaphor
    visual_prompt: "English visual prompt, specific to the thesis, no generic coding stock footage."
    negative_prompt: "watermark, logo, unreadable text, distorted hands, blurry"
    ai_broll:
      provider: volcengine_seedance
      mode: text_to_video
      fallback: concept_card

  - id: project-1-github
    asset_type: github
    visual_type: github_scroll_callout
    duration_seconds: 20
    narration_ref: project_1_evidence
    repo: "owner/repo"
    callouts:
      - repo_name
      - stars
      - readme

  - id: project-1-card
    asset_type: card
    visual_type: concept_card
    duration_seconds: 8
    narration_ref: project_1_capabilities
    card:
      title: "链上角色"
      bullets:
        - "痛点"
        - "能力"
        - "意义"

  - id: outro-summary
    asset_type: card
    visual_type: summary_card
    duration_seconds: 12
    narration_ref: outro
    card:
      title: "长期判断"
      bullets:
        - "趋势"
        - "机会"
```

## 6. Asset Types

Hybrid v1 supports the following `asset_type` values:

| asset_type | Meaning | Source | Required today |
|------------|---------|--------|----------------|
| `ranking` | Daily ranking proof | Existing daily chart renderer | Optional |
| `github` | Repository proof | Existing GitHub scroll/callout renderer | Required for each selected project |
| `card` | Thesis/project/summary card | New or existing card renderer | Required |
| `ai_broll` | AI-generated related visual | Volcengine Seedance | Optional, max 2-3 |
| `transition` | Segment transition | ffmpeg | Optional |

Avoid stock-video search in hybrid v1. The purpose is to stop generic `coding/developer` footage from dominating project introductions.

## 7. Seedance Provider Decision

Use Volcengine Seedance as the preferred AI visual provider if credentials are available.

Important provider note:

- Seedance is primarily useful for video generation. If the account/API supports text-to-video directly, use `mode: text_to_video`.
- If a still first frame is required, use the Volcengine image generation model available in the account to create the first frame, then send it to Seedance as image-to-video.
- Do not hard-code model IDs in the plan. Copy the exact model ID from the Volcengine console into environment variables.

Environment variables:

```bash
VOLCENGINE_ACCESS_KEY_ID=...
VOLCENGINE_SECRET_ACCESS_KEY=...
VOLCENGINE_REGION=cn-beijing
VOLCENGINE_SEEDANCE_MODEL=<copy-from-volcengine-console>
VOLCENGINE_IMAGE_MODEL=<optional-copy-from-volcengine-console>
HYBRID_AI_PROVIDER=volcengine_seedance
```

`seedance_client.py` should expose a stable local interface:

```python
def generate_ai_broll(
    *,
    prompt: str,
    negative_prompt: str,
    output_path: Path,
    duration_seconds: float,
    aspect_ratio: str = "9:16",
    mode: str = "text_to_video",
) -> Path:
    ...
```

The rest of the hybrid pipeline must not know Volcengine details. It only calls `generate_ai_broll`.

## 8. Today's Midterm Scope

Today means: build the independent hybrid scaffolding and a usable v1 pipeline without touching the current sop/mpt behavior.

Required today:

- Create `hybrid-video` Skill.
- Create hybrid spec/storyboard templates.
- Create Python scripts with clear boundaries.
- Add `content-studio.sh video-hybrid` and `video-hybrid-pipeline`.
- Generate hybrid storyboard/spec from an existing `*-video-script.md`.
- Render at least a hybrid asset package:
  - cards
  - GitHub segment placeholders or imported existing GitHub assets
  - Seedance AI segment if credentials work
- Produce `hybrid-status`.

Nice to have today:

- End-to-end `*-hybrid-video.mp4`.
- Seedance smoke test.
- Publish guide.

Allowed fallback today:

- If Seedance credentials/API are not ready, write `ai_broll` prompts and render fallback concept cards. The pipeline still succeeds with `ai_broll_failure_policy: card_fallback`.

## 9. Implementation Tasks

### Task 1: Create Hybrid Skill

**Files:**

- Create: `/Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/SKILL.md`
- Create: `/Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/references/SEEDANCE.md`
- Create: `/Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/references/VISUAL_PROMPT_GUIDE.md`

**Steps:**

1. Write frontmatter for `hybrid-video`.
2. Document that this is a third pipeline, not a replacement for sop/mpt.
3. Define trigger phrases: `生成 hybrid视频`, `hybrid视频`, `生成 AI增强视频`.
4. Require `terminal` execution and ban `execute_code` for video generation.
5. Explain Seedance credentials and fallback behavior.

**Verification:**

```bash
test -f /Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/SKILL.md
```

Expected: exit code 0.

### Task 2: Add Hybrid Templates

**Files:**

- Create: `/Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/templates/hybrid-storyboard.md`
- Create: `/Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/templates/hybrid-production-spec.yaml`

**Steps:**

1. Copy only the useful structure from existing storyboard templates.
2. Add `asset_type`, `visual_prompt`, `negative_prompt`, and `ai_broll`.
3. Require `github` segments for selected projects.
4. Limit `ai_broll` to 2-3 segments.

**Verification:**

```bash
python - <<'PY'
from pathlib import Path
p = Path('/Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/templates/hybrid-production-spec.yaml')
text = p.read_text()
assert 'asset_type' in text
assert 'ai_broll' in text
assert 'volcengine_seedance' in text
PY
```

Expected: no output, exit code 0.

### Task 3: Implement Hybrid Spec Generator

**Files:**

- Create: `/Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/scripts/hybrid_spec.py`

**Behavior:**

Input:

```bash
python hybrid_spec.py \
  --date YYYY-MM-DD \
  --report-dir /Users/gqli/.hermes/profiles/content-studio/reports
```

Output:

```text
YYYY-MM-DD-hybrid-storyboard.md
YYYY-MM-DD-hybrid-production-spec.yaml
```

Minimum logic:

1. Read `YYYY-MM-DD-video-script.md`.
2. Parse `## 本期主题`, `## 入选项目`, and `## 完整口播文本`.
3. Select 3-5 projects from `## 入选项目`.
4. Emit:
   - intro card
   - optional intro `ai_broll`
   - for each project: `github` + `card`
   - outro card
5. Add 2-3 AI prompts only for abstract/thematic segments.

**Verification:**

```bash
/Users/gqli/work/deepagents/venv/bin/python3 \
  /Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/scripts/hybrid_spec.py \
  --date 2026-06-13 \
  --report-dir /Users/gqli/.hermes/profiles/content-studio/reports
```

Expected:

- `2026-06-13-hybrid-storyboard.md`
- `2026-06-13-hybrid-production-spec.yaml`

### Task 4: Implement Seedance Client Boundary

**Files:**

- Create: `/Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/scripts/seedance_client.py`

**Behavior:**

1. Check required environment variables.
2. If missing, return a structured `ProviderUnavailable` error.
3. Do not crash the whole pipeline if `ai_broll_failure_policy=card_fallback`.
4. Keep Volcengine API payload isolated inside this file.

**Verification without credentials:**

```bash
/Users/gqli/work/deepagents/venv/bin/python3 \
  /Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/scripts/seedance_client.py \
  --smoke-test
```

Expected:

- Clear message that credentials are missing.
- Exit code 0 or documented non-zero code that `hybrid_video.py` can handle.

### Task 5: Implement Asset Renderer

**Files:**

- Create: `/Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/scripts/hybrid_assets.py`

**Behavior:**

1. Read `*-hybrid-production-spec.yaml`.
2. Create asset folders:
   - `assets/YYYY-MM-DD-hybrid/cards`
   - `assets/YYYY-MM-DD-hybrid/github`
   - `assets/YYYY-MM-DD-hybrid/ai-broll`
   - `assets/YYYY-MM-DD-hybrid/clips`
3. For `card` segments, render a simple PNG card.
4. For `ai_broll`, call `seedance_client.py`.
5. If Seedance fails or is missing, render a fallback card image and mark it in status.
6. For `github` segments, either:
   - call existing GitHub visual functions if safe, or
   - write a placeholder entry in v1 and leave actual composition for the next task.

**Verification:**

```bash
/Users/gqli/work/deepagents/venv/bin/python3 \
  /Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/scripts/hybrid_assets.py \
  --spec /Users/gqli/.hermes/profiles/content-studio/reports/2026/06/2026-06-13-hybrid-production-spec.yaml
```

Expected:

- `assets/2026-06-13-hybrid/cards/*.png`
- `assets/2026-06-13-hybrid/ai-broll/*` or fallback cards

### Task 6: Implement Hybrid Orchestrator

**Files:**

- Create: `/Users/gqli/.hermes/profiles/content-studio/skills/content-studio/hybrid-video/scripts/hybrid_video.py`

**Behavior:**

Modes:

```bash
hybrid_video.py spec --date YYYY-MM-DD
hybrid_video.py assets --date YYYY-MM-DD
hybrid_video.py render --date YYYY-MM-DD
hybrid_video.py pipeline --date YYYY-MM-DD
hybrid_video.py status --date YYYY-MM-DD
```

Minimum v1:

- `pipeline` calls `spec`, then `assets`, then attempts `render`.
- `status` prints:
  - script path
  - spec path
  - asset counts
  - output video path if present
  - fallback counts

Progress output:

```text
CONTENT_STUDIO_PROGRESS date=YYYY-MM-DD pipeline=hybrid-video stage=1/4 status=ok msg=spec artifact=...
CONTENT_STUDIO_PROGRESS date=YYYY-MM-DD pipeline=hybrid-video stage=2/4 status=ok msg=assets artifact=...
```

### Task 7: Add Shell Commands

**Files:**

- Modify: `/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh`

Add cases:

```bash
video-hybrid|hybrid-video|vh)
  run_video_hybrid
  ;;
video-hybrid-pipeline|hybrid-pipeline|vhp)
  run_video_hybrid_pipeline
  ;;
hybrid-status)
  run_video_hybrid_status
  ;;
```

Rules:

- Do not modify existing `video-pipeline` behavior.
- Do not modify existing `video-mpt` behavior.
- New functions call `hybrid_video.py`.

**Verification:**

```bash
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh hybrid-status 2026-06-13
```

Expected:

- No crash.
- Status mentions missing or existing hybrid spec/assets.

### Task 8: Add Routing Docs

**Files:**

- Modify: `/Users/gqli/.hermes/profiles/content-studio/SOUL.md`
- Modify: `/Users/gqli/.hermes/profiles/content-studio/skills/content-studio/playbook/SKILL.md`
- Modify: `/Users/gqli/.hermes/profiles/content-studio/skills/content-studio/help-manual/SKILL.md`
- Modify: `/Users/gqli/.hermes/profiles/content-studio/skills/content-studio/video-execution/SKILL.md`

Add only new routes:

```text
生成 hybrid视频 → hybrid-video Skill → terminal content-studio.sh video-hybrid-pipeline [DATE]
hybrid 进度 → terminal content-studio.sh hybrid-status [DATE]
```

Do not alter existing route behavior for:

- `生成 sop视频`
- `生成 mpt视频`

## 10. Today's Acceptance Criteria

Minimum acceptable result today:

- `hybrid-video/SKILL.md` exists.
- `hybrid_video.py` exists.
- `content-studio.sh hybrid-status DATE` works.
- `content-studio.sh video-hybrid-pipeline DATE` creates:
  - `*-hybrid-storyboard.md`
  - `*-hybrid-production-spec.yaml`
  - `assets/DATE-hybrid/`
- If Seedance is unavailable, fallback cards are generated and status explains why.
- Current commands still work:
  - `content-studio.sh video-pipeline DATE`
  - `content-studio.sh video-mpt-pipeline DATE`

Stretch result today:

- `*-hybrid-video.mp4` is generated.
- At least one AI-generated segment is produced through Volcengine Seedance.

## 11. Testing Checklist

Run these in order:

```bash
# Existing sop route should still be discoverable.
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh sop-status 2026-06-13

# New hybrid status.
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh hybrid-status 2026-06-13

# New hybrid spec/assets pipeline.
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh video-hybrid-pipeline 2026-06-13

# Existing mpt command should not be affected.
/Users/gqli/.hermes/profiles/content-studio/scripts/content-studio.sh video-mpt 2026-06-13
```

Expected:

- Hybrid files are created under `*-hybrid-*`.
- Existing sop/mpt files are not overwritten.
- Logs include `CONTENT_STUDIO_PROGRESS pipeline=hybrid-video`.

## 12. Development Rules

1. The hybrid pipeline is additive.
2. Existing current video outputs must not be overwritten.
3. Seedance failures should not kill v1 unless user explicitly requests strict AI mode.
4. GitHub evidence failures should fail fast when the segment is required.
5. Video generation must use `terminal`, not `execute_code`.
6. All generated files must use absolute paths in status output.
7. The first version should prefer a simple working pipeline over a perfect cinematic system.

## 13. Future Work After Midterm

After today's midterm is stable:

1. Replace fallback cards with real GitHub scroll clips in hybrid composition.
2. Add image-to-video mode if Volcengine requires a first frame.
3. Add provider adapter interface for multiple platforms.
4. Add cost controls:
   - max AI seconds per video
   - max provider calls
   - dry-run mode
5. Add review report:
   - which segments used AI
   - which segments fell back
   - cost estimate
6. Add `video-hybrid-render` to reuse existing spec/assets without regenerating them.

## 14. Recommended Implementation Order Today

Do this order to avoid destabilizing the existing system:

1. Create `hybrid-video` Skill and templates.
2. Create `hybrid_spec.py`.
3. Create `hybrid_video.py status`.
4. Add `content-studio.sh hybrid-status`.
5. Add `hybrid_assets.py` with card fallback.
6. Add `seedance_client.py` boundary.
7. Add `video-hybrid-pipeline`.
8. Update routing docs.
9. Run existing sop/mpt status checks.
10. Only then attempt full hybrid mp4.

## 15. What the User Needs to Provide

Before real Seedance output can be generated, provide:

- Volcengine credentials or environment variable names.
- The exact Seedance model ID copied from the Volcengine console.
- Whether the account supports direct text-to-video or requires first-frame image-to-video.
- Whether strict AI failure should stop the pipeline or fallback to cards.

Default for today:

```text
AI failure policy: fallback to cards
max AI segments: 2
provider: volcengine_seedance if configured, otherwise fallback
```
