# Content Studio — Skill Package

Hermes profile skill group for daily GitHub Trending analysis, weekly deep dives, community briefs, and Xiaohongshu-style vertical video production.

## Layout (AgentSkills / Hermes convention)

```text
skills/content-studio/
├── README.md
├── DESCRIPTION.md
├── lib/
│   ├── profile_paths.py      # Resolve profile root from any script
│   └── paths.sh              # Bash path constants for orchestrator
├── playbook/                 # Router SOP (no scripts)
├── help-manual/              # User manual (no scripts)
├── github-daily/
│   ├── SKILL.md
│   └── scripts/
│       ├── generate_daily_report.py
│       └── github_trending_snapshot.py
├── tool-radar/    # LLM-only skill
├── weekly-digest/     # LLM-only skill
├── video-script-generator/
│   ├── SKILL.md
│   └── scripts/
│       └── generate_video_script_fallback.py
├── video-pipeline/
│   ├── SKILL.md
│   └── scripts/
│       └── video_generator.py          # GitHub 滚动核心渲染器（--engine fallback）
├── moneyprinter-video/
│   ├── SKILL.md
│   ├── scripts/
│   │   └── moneyprinter_video.py       # MoneyPrinterTurbo 独立链路
│   └── references/
│       └── SERVICE.md
├── community-pulse/
│   ├── SKILL.md
│   └── scripts/
│       ├── generate_community_pulse.py
│       └── validate_community_pulse.py
└── knowledge-library/
    ├── SKILL.md
    ├── scripts/
    │   ├── report_index.py
    │   └── report_dispatcher.py
    └── assets/
        └── dispatcher_config.yaml

profile/scripts/              # Orchestrator (cron + manual CLI)
├── content-studio.sh
├── content-studio-*.sh
└── setup-cron.sh

profile/config/               # Runtime secrets (not in skill assets)
└── tts-providers.yaml

profile/reports/              # Generated artifacts
└── YYYY/MM/
```

## Environment

| Variable | Purpose |
|----------|---------|
| `HERMES_HOME` | Profile root (default `~/.hermes/profiles/content-studio`) |
| `CONTENT_STUDIO_PROFILE_DIR` | Same as `HERMES_HOME` when set |
| `CONTENT_STUDIO_TTS_CONFIG` | TTS config path (default `config/tts-providers.yaml`) |
| `CONTENT_STUDIO_SKIP_AUTO_VIDEO` | Set `1` to skip auto video after daily report |
| `CONTENT_STUDIO_PYTHON` | Python for pipeline scripts (default: pyenv shims → `python3.12` → `python3`) |

## Quick start

```bash
export HERMES_HOME=~/.hermes/profiles/content-studio

# Manual orchestrator
"$HERMES_HOME/scripts/content-studio.sh" daily
"$HERMES_HOME/scripts/content-studio.sh" video-pipeline
"$HERMES_HOME/scripts/content-studio.sh" video-mpt-pipeline   # MoneyPrinterTurbo 独立链路
"$HERMES_HOME/scripts/content-studio.sh" browse

# Direct skill scripts
python3 "$HERMES_HOME/skills/content-studio/github-daily/scripts/generate_daily_report.py" \
  --date "$(date +%Y-%m-%d)" \
  --report-dir "$HERMES_HOME/reports"

# 完整视频 pipeline（推荐）
"$HERMES_HOME/scripts/content-studio.sh" video-pipeline

# 仅查看底层生成器帮助（开发调试用，不要用于 Chat 生产流程）
python3 "$HERMES_HOME/skills/content-studio/video-pipeline/scripts/video_generator.py" --help
```

## Cron

```bash
"$HERMES_HOME/scripts/setup-cron.sh"
```

Cron wrappers call `content-studio.sh`, which delegates to skill scripts under `skills/content-studio/*/scripts/`.

## Design principles

1. **Skill = SOP + colocated scripts** — Agent reads `SKILL.md` and runs `scripts/` in the same directory.
2. **Profile orchestrator** — `content-studio.sh` chains skills for cron and one-shot SOP (`sop` command).
3. **Shared lib** — `lib/profile_paths.py` lets scripts find `reports/` and `config/` regardless of skill depth.
4. **Legacy wrappers** — Thin delegators at `profile/scripts/*.py` remain for old bookmarks; prefer skill paths.
