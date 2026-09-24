# Prompt 与人设路由

## 1. 三层分工（不要混写）

| 层 | 文件 | 写什么 | 不写什么 |
|----|------|--------|----------|
| **SOUL** | `$HERMES_HOME/SOUL.md` | 人设、栏目、视频表达原则、**意图→Skill 简表** | 长命令表、逐步 shell、模板全文 |
| **Playbook** | `skills/content-studio/playbook/SKILL.md` | 意图匹配树、流程步骤、完成标志 | Provider 细节 |
| **子 Skill** | 各 `*/SKILL.md` | 该能力的步骤、脚本路径、模板 | 全局路由 |

Hermes 在会话初将 SOUL + Skill 索引注入 system；Agent 通过 **`skill_view`** 按需加载正文（保护 prompt cache，见 Hermes `AGENTS.md`）。

---

## 2. SOUL 摘要（Content Studio Agent）

**角色**：内容策划主编 — 多栏目（Tech Radar、Community Pulse、English Shorts、Story Briefs、Video Producer、Knowledge Library）。

**原则**：

- 策划先行、证据驱动、生产闭环  
- 视频：hook/thesis → 叙事链 → 分镜 → 可验证证据画面  
- 中文输出；术语与命令保留英文  

**意图 → Skill（必须先加载）**：

| 用户意图 | Skill |
|----------|-------|
| help / 怎么用 / 有哪些 skills | `help-manual` → `references/help-quick.md` |
| help full / 命令大全 | `help-manual` + `content-studio.sh help` |
| 任意生产任务 | `playbook` |
| sop / mpt / hybrid 视频 | `video-execution`（+ `moneyprinter-video` / `hybrid-video`） |
| 报告库 | `knowledge-library` |

完整正文：`$HERMES_HOME/SOUL.md`（勿复制进 monorepo 若含环境特定说明）。

---

## 3. Playbook 路由（摘录）

逻辑结构（详见 live `playbook/SKILL.md`）：

```text
用户消息
  ├─ help / 帮助 → help-manual（简版）；help full → + terminal help
  ├─ 日报 / daily / trending → github-daily + content-studio.sh daily
  ├─ 周报 / weekly → weekly-digest
  ├─ sop视频 → video-execution → video-pipeline
  ├─ mpt视频 → video-execution + moneyprinter-video（禁止同轮跑 pipeline+mpt）
  ├─ hybrid视频 → video-execution + hybrid-video → video-hybrid-pipeline
  ├─ hybrid-status → terminal hybrid-status
  └─ 社区脉搏 → community-pulse
```

**硬规则（playbook + video-execution）**：

- MPT 与 SOP pipeline **不要在同一轮** 各跑一条完整 pipeline。  
- 已有 `*-video-script.md` 时，MPT 用 `video-mpt` 而非重复 `video-pipeline`。  
- Hybrid 不覆盖 `*-video.mp4` / `*-mpt-video.mp4` 命名空间。

---

## 4. Prompt 系统（Hermes 内核）

Content Studio 不改变 Hermes 组装顺序，仅增加：

- Profile 级 `SOUL.md`  
- `skills/content-studio/**` 进入 Skill 目录扫描  
- Cron / Gateway 使用同一 `HERMES_HOME`  

阅读：`hermes-dev/hermes-agent/docs/PROMPT_SYSTEM_ARCHITECTURE.md`  
子 Agent 示例：`SUBAGENT_RUNTIME_PROMPT_EXAMPLE.md`

---

## 5. 与 OpenHuman / 其它项目

`openhuman/` 下的 SOUL 与 **Hermes content-studio Profile 无关**（见 `docs/hermes/MULTI_AGENT_PROFILES.md`）。  
Content Studio 人设只认 `~/.hermes/profiles/content-studio/SOUL.md`。
