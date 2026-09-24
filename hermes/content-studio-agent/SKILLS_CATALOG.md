# Skills 目录（Content Studio）

路径基准：`$HERMES_HOME/skills/`（生产环境 `HERMES_HOME=~/.hermes/profiles/content-studio`）。

---

## 1. 自研包 `content-studio/`（核心）

以下 Skill **共同构成 Content Studio Agent**；编排关系见 `playbook/SKILL.md`。

| Skill | 路径 | 类型 | 职责 |
|-------|------|------|------|
| **playbook** | `content-studio/playbook/` | 纯 SOP | 意图路由 → 子 Skill + `content-studio.sh` |
| **help-manual** | `content-studio/help-manual/` | 纯 SOP | help / help full；引用 `help-quick.md` |
| **github-daily** | `content-studio/github-daily/` | 脚本 + SOP | GitHub Trending 日报 |
| **tool-radar** | `content-studio/tool-radar/` | LLM | 生产级工具雷达 |
| **weekly-digest** | `content-studio/weekly-digest/` | LLM | 周报 / 深度分析 |
| **community-pulse** | `content-studio/community-pulse/` | 脚本 | last30days 社区脉搏 |
| **video-script-generator** | `content-studio/video-script-generator/` | 脚本 + 模板 | 口播稿、叙事链、分镜输入 |
| **storyboard-planner** | `content-studio/storyboard-planner/` | 模板 | storyboard、production-spec |
| **video-pipeline** | `content-studio/video-pipeline/` | 脚本 | SOP 视频：`video_generator.py`（GitHub 滚动红框） |
| **video-execution** | `content-studio/video-execution/` | SOP | 三条视频链路的统一执行规范 |
| **moneyprinter-video** | `content-studio/moneyprinter-video/` | 脚本 | MPT API 封装 |
| **hybrid-video** | `content-studio/hybrid-video/` | 脚本 + 模板 | Hybrid spec、assets、Seedance 可选 |
| **web-story-renderer** | `content-studio/web-story-renderer/` | 脚本 | Web Story 页面 |
| **knowledge-library** | `content-studio/knowledge-library/` | 脚本 | `report_index`、dispatcher、Open Notebook 同步 |

共享库：

- `content-studio/lib/profile_paths.py` — Python 解析 Profile 根目录  
- `content-studio/lib/paths.sh` — Bash 常量（被 `content-studio.sh` 引用）

包说明：`content-studio/README.md`、`DESCRIPTION.md`

---

## 2. Git 内基线：`hermes-dev/profiles/github/`

早期 **GitHub Analyst** 技能树（结构与 content-studio 同源，能力较少）：

```text
hermes-dev/profiles/github/skills/github-analyst/
├── playbook/
├── daily-trending/
├── weekly-deep-analysis/
├── video-script-generator/
├── storyboard-planner/
├── video-pipeline/
└── social-trend-brief/
```

安装：`cd hermes-dev/profiles/github && ./install.sh` → `~/.hermes/profiles/github`

与 **content-studio** 的关系：content-studio 是 github-analyst 的 **栏目扩展 + 三条视频 + 报告库 + Open Notebook** 超集；新功能应写在 content-studio，github 目录仅作历史参考或最小安装包。

---

## 3. Profile 内其它 Skill（依赖 / 扩展）

Content Studio Profile 通常还安装大量 **官方或社区 Skill**（非本仓库维护）。常见与内容生产相关：

| 目录 | 用途 |
|------|------|
| `creative/*` | 插图、ComfyUI、Manim、像素风等 |
| `media-content` | 媒体内容总览 |
| `document-processing` | 文档处理 |
| `github/github-management` | GitHub 操作 |
| `software-development/writing-plans` | 计划类 SOP |

完整列表以本机为准：

```bash
find "$HERMES_HOME/skills" -name SKILL.md | wc -l
```

---

## 4. Hermes Skill 机制（阅读顺序）

1. 用户消息 → Prompt 注入 Skill 索引（见 `PROMPTS_AND_ROUTING.md`）  
2. Agent `skill_view(name, file_path?)` 加载 SKILL.md  
3. 按 SOP 调用 `terminal` → `content-studio.sh`  
4. 脚本写 `reports/` 与 `CONTENT_STUDIO_PROGRESS` 日志 → Agent / `sop-status` 可读  

上游文档：`hermes-dev/hermes-agent/docs/SKILLS_SYSTEM.md`

---

## 5. 修改 Skill 的检查清单

- [ ] 更新 `playbook` 路由（若新增用户意图）  
- [ ] 更新 `help-manual/references/help-quick.md`（若新增命令）  
- [ ] 更新 `content-studio.sh` 与 `SCRIPTS_AND_COMMANDS.md`  
- [ ] 勿在 `SOUL.md` 重复长命令表  
- [ ] 考虑 rsync 到 `hermes-dev/profiles/content-studio/`（镜像落地后）
