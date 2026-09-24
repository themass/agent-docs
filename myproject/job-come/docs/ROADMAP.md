# JobCome 产品路线图

| 更新 | 2026-09-04 |

## 已完成（MVP + 3 周计划）

### 第 1 周 — 验收打穿 ✅
- 回归集：3 简历 + 6 JD（`tests/regression_assets/`）
- `scripts/e2e_smoke.sh` 联调脚本
- `docs/RUNBOOK.md`
- OpenAPI / fixture 自动化测试

### 第 2 周 — 体验闭环 ✅
- `/jobs` → `/coach-agent?job_id=` 模拟面串联
- `/applications` 投递记录页
- `/auth/change-password` 改密页
- `coach-mock` 五维评分 rubric
- `GET /jobs/.../applications` API

### 第 3 周 — 增强 ✅
- Fit 校准可视化（jobs 页 bands 卡片）
- `docs/DEPLOY.md` 生产部署要点
- Scout-lite：`parse-url` 已实现

---

## 第 4–6 周 — Agent 打穿（优先于 Scout）

详见 [Agent核心能力规划.md](./Agent核心能力规划.md)。

| 周 | 主题 | 交付 |
|----|------|------|
| **W4a** | Agent P0 | tools 透传到 LLM；会话消息持久化 |
| **W4b** | Agent P1 | 流式 + tool UI；custom skill；写库确认 |
| **W5** | 一岗编排 | `jobcome_apply_pipeline` MCP；coach 强制记 attempt |
| **W6** | 内容 + Scout | noamseg rubric；boss-agent 只读评估 | ✅ rubric/观测已落地；Scout 待 Phase 3 |

**Phase 2+ 详见 [PHASE2_ROADMAP.md](./PHASE2_ROADMAP.md)**

**完成标准：** 内测用户无需文档可完成「一岗定向申请 + 模拟面」。

---

## 第 7–10 周 — 增长准备

| 主题 | 内容 |
|------|------|
| **战役看板** | Campaign UI：warmup / target 岗位列表、解锁条件 |
| **简历版本** | 同 profile 多 `ResumeDraft` 对比（Teal 式） |
| **社区题库** | 脱敏贡献、可撤回（产品设计 Q2） |
| **中英双轨** | `locale` 导出模板 + 拔高 prompt 分支 |
| **观测** | Langfuse / 结构化日志；apply-pipeline 漏斗指标 |

---

## 第 11–12 周 — 商业化预备（可选）

| 主题 | 内容 |
|------|------|
| 付费 | 导出次数 / LLM 额度；Stripe 或国内支付 |
| B 端试点 | 高校就业中心 / 猎头顾问席位 |
| 合规 | 个保法审计、数据删除 SLA、隐私政策页 |

---

## 技术债（持续）

| 项 | 优先级 |
|----|--------|
| 真 DeerFlow 包接入（可选替换 in-process harness） | **进行中** — 默认 `harness`，见 [DeerFlow接入.md](./DeerFlow接入.md) |
| markitdown / tavily MCP 运行时接线 | P3 |
| Playwright 集成测试（导出 PDF） | P2 |
| Alembic migration 与空库一键初始化 | P1 |

---

## 原则（不变）

1. **不代投** — 无自动表单提交、无批量海投
2. **真相源** — Profile / Job / Interview 只经 `jobcome` MCP 或 Service 写库
3. **少而精** — 对齐 ai-job-search 69→20→1 质量漏斗，非 AIHawk 量
