# ai-job-search 集成方案

| 版本 | 1.0 |
| 日期 | 2026-09-03 |
| 项目 | [MadsLorentzen/ai-job-search](https://github.com/MadsLorentzen/ai-job-search)（~40k★） |

---

## 1. 一句话结论

**不整仓集成、不绑 Claude Code、不引入其 scrape/丹麦招聘站 CLI。**

**要集成的是已被验证的工作流与工程模式**，映射进 JobCome 现有的 Profile / Job / Interview / Agent 架构：

> 少而精的申请 → 人岗匹配 → Drafter-Reviewer 改稿 → 导出 → 面试准备 → 记 outcome → 反哺 fit 校准

这与产品设计 §7.4 一致：「抄工作流，不 fork 当产品」。

---

## 2. ai-job-search 是什么（拆解）

| 维度 | 它是什么 | JobCome 是否照搬 |
|------|----------|------------------|
| 运行时 | Claude Code CLI + 本地 `documents/` 文件 | ❌ 我们是 Web + FastAPI + DeerFlow |
| 命令 | `/setup` `/scrape` `/apply` `/interview` `/outcome` | ✅ 映射为 Skill + API 阶段 |
| 档案 | 本地 markdown / LaTeX 源文件 | ❌ 真相源是 `jc_profile.payload` |
| 改稿 | Drafter → Reviewer 双 Agent | ✅ 已有 `resume-writer` + `resume-reviewer` |
| 匹配 | Fit score + go/caution/no | ✅ 已有 `jobcome_fit_score` |
| 导出 | LaTeX → PDF + ATS 文本层检查 | ⚠️ 我们 HTML/DOCX；可借鉴 ATS 检查逻辑 |
| 搜岗 | 丹麦 Jobindex 等 + LinkedIn CLI | ❌ 国内另做；默认粘贴 JD |
| 投递 | 人手动投；followup **只起草不发** | ✅ 与「不代投」一致 |
| 面试 | 基于**已投递材料归档**做 prep + mock | ✅ 对齐 `coach-mock` + 飞轮 |
| 闭环 | `/outcome` 归档 → 校准 fit 框架 | ✅ 对齐 `interview_save` + Campaign |

作者案例 **69 投 → 20 面 → 1 offer** 证明的是**质量漏斗**，不是海投工具——与 JobCome 战略一致。

---

## 3. 为什么不整仓集成

1. **产品形态**：开发者终端 vs 国内非开发者 Web 用户  
2. **数据模型**：文件夹 + LaTeX vs MySQL Profile JSON  
3. **合规**：Fork 默认 public，简历写进 git tracked 文件；我们是加密存储 + 可删除  
4. **市场**：`.agents/skills/*-search` 绑丹麦站 + LinkedIn，国内需 BOSS/粘贴 JD  
5. **技术栈**：Bun CLI + LaTeX vs Playwright PDF + python-docx  
6. **品牌风险**：媒体标题常写「automate 90% applications」——我们需严格剥离 scrape/auto 叙事  

---

## 4. 命令 → JobCome 映射表

| ai-job-search | JobCome 能力 | 状态 | 缺口 |
|---------------|-------------|------|------|
| `/setup` | 上传简历 + Profile 编辑 + confirm | ✅ API 已有 | UX 引导「建档访谈」可加强 |
| `/scrape` | **不做同款爬虫**；M2 可选 boss-agent 只读 / 用户粘贴 JD | ⏸ | Scout 页、岗位列表 UI |
| `/apply`（fit） | `POST /jobs/.../parse` + `.../fit` | ✅ | 前端 JD 页 |
| `/apply`（drafter） | `resume-writer` Skill + elevate | ✅ | 按 JD 定向拔高 |
| `/apply`（reviewer） | `resume-reviewer` + `ResumeReviewer` | ✅ | 双 Agent 串行可显式化 |
| `/apply`（ATS check） | 导出前 reviewer + 可选 ATS MCP | ⚠️ | 从 PDF 抽文本层对标关键词 |
| `/interview` | `coach-mock` + 绑定 job_id / draft_id | ⚠️ | prep pack 需关联「已投递版本」 |
| `/outcome` | `interview_save` + Job fit 回写 | ✅ | Application 状态机 UI |
| outcome → 校准 fit | Campaign + fit 历史统计 | ⏸ | P2 数据分析 |

---

## 5. 分阶段集成计划

### Phase 0 — 现在（0 外部依赖）

**目标：** 跑通 ai-job-search 同构漏斗，全靠自研。

```
上传/建档 → 粘贴 JD → fit 打分 → 拔高 → reviewer → 导出
                ↓
         模拟面 / 记真题 → 题库 → 再模拟
```

交付：
- [x] 7 Skill + 7 MCP Tool
- [ ] 前端 `/jobs` 页（粘贴 JD、看 fit、保存岗位）
- [ ] 导出链路显式 **Drafter → Reviewer** 两步（可先串行 API）

### Phase 1 — 吸收 ai-job-search「剧本」（2–3 周）

**目标：** fork **流程文档与 rubric**，不是 fork 仓库。

| 来源文件（ai-job-search） | 落到 JobCome |
|---------------------------|--------------|
| Drafter-Reviewer 分离协议 | `skills/custom/apply-pipeline/SKILL.md` |
| `07-interview-prep.md` mock 协议 | 增强 `coach-mock/SKILL.md` |
| Fit 评估维度 / stretch 定义 | 增强 `prompts/ingest/fit_score.md` |
| Outcome 归档字段 | 对齐 `InterviewSaveRequest` + Job 状态 |
| ATS 文本层检查清单 | 增强 `prompts/export/reviewer.md` |

**不做：** LaTeX 模板、丹麦 scrape CLI、Claude Code slash commands。

### Phase 2 — 定向申请（4–6 周）

**目标：** 实现 ai-job-search `/apply` 的产品化等价物。

1. **Job 战役实体**：`jc_job` + `ResumeDraft.job_id` 绑定定向稿  
2. **按 JD 拔高**：`elevate?job_id=` 读 JD keywords 加权  
3. **材料归档**：每次 export 存 `storage_key` 到 Application（仿 `documents/applications/`）  
4. **Interview prep pack**：mock 时自动注入「该岗 JD + 已导出简历摘要」

API 草案：
- `POST /jobs/profiles/{id}/apply-pipeline` → fit → elevate → review → export（异步 job）

### Phase 3 — Scout -lite（可选，用户显式开启）

**目标：** 对应 `/scrape` 的**国内安全子集**。

| 能力 | 方案 |
|------|------|
| 粘贴招聘链接 | 开 `server-fetch` MCP 拉正文 → `job_parse` |
| 公司调研 | 开 `tavily` / Brave（需同意隐私） |
| BOSS/智联发现 | `boss-agent-cli` **只读 assist**，无自动投递 |

**永远不做：** 无人值守批量 apply、LinkedIn 自动搜投一体。

### Phase 4 — 飞轮校准（Q2）

**目标：** 对应 `/outcome` → 回写 `/setup` 校准 fit。

- 统计：哪些 fit 分段真实进了面试  
- 调整 `fit_score` prompt 阈值或展示文案  
- Campaign：`warmup` → `target` 解锁（产品设计已有）

---

## 6. 与「其他火热项目」的优先级

在 ai-job-search **之后**：

| 项目 | 关系 | 优先级 |
|------|------|--------|
| noamseg/interview-coach-skill | 加强 `/interview` 评分 | P1 |
| yanliudesign/offer-toolkit-skill | 全漏斗中文 rubric | P2 |
| boss-agent-cli | Scout 国内源 | P3（只读） |
| Auto_Jobs_Applier / AIHawk | **禁止** | — |

---

## 7. 验收标准（对齐 69→20→1 哲学）

| 指标 | 含义 |
|------|------|
| 用户可针对 **1 个 JD** 完成 fit → 定向稿 → 导出 | 等价 `/apply` 核心价值 |
| 每次真面后可 **归档** 并进入题库 | 等价 `/outcome` + 飞轮 |
| 模拟面可抽到 **本岗位/本公司** 历史题 | 等价 `/interview` 差异化 |
| 全链路 **无自动投递按钮** | 产品红线 |
| 档案修改可 **溯源到 tool 调用** | 胜过本地 markdown |

---

## 8. 相关文档

- [产品设计.md](./产品设计.md) §7.4
- [开源集成指南.md](./开源集成指南.md)
- [模型与流程设计.md](./模型与流程设计.md)
