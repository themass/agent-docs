# 文档维护基准（源码锚点）

<!-- legacy-review:start -->
> **2026-10-15 校订导航**：怎样维护教程而不覆盖现行分卷。\
> **核对范围**：废止 legacy 自动覆盖分卷的操作建议，旧地图和规模表降为历史记录。\
> **适用基线**：本地源码 `60d00c5633ad`；不是最新发布版本声明。原稿版本、行号、性能数字与长代码块若未在校订范围内，仍按历史示例阅读。
> **先读当前结论**：[当前实现导读](CURRENT_IMPLEMENTATION.md#current-evidence) · **现行分卷**：[09-reference-history-and-versions.md](../../volumes/09-reference-history-and-versions.md) · [具体改动与未验证项](REVIEW_AND_CHANGES.md) · [返回全目录](README.md)

<!-- legacy-review:end -->
<a id="目录"></a>
## 目录

<!-- visible-toc:start -->
- [1. 现行维护规则：分卷与教程分别校订](#section-1)
- [2. 历史维护地图（2026-10-14 原稿，非当前操作规范）](#section-2)
- [3. Canonical 地图（按 CATALOG 类）](#section-3)
  - [3.1 2026-10-14 整理](#section-3-1)
- [4. 模块规模（2026-10 `wc -l` 快照）](#section-4)
- [5. Memory 叙事](#section-5)
- [6. 刷新检查清单](#section-6)
- [7. 相关](#section-7)
<!-- visible-toc:end -->




> **工作区**: `hermes-dev/hermes-agent/` · `__release_date__` **2026.9.24**  
> **核对日期**: 2026-10-14  
> **分类目录**: [CATALOG.md](../../CATALOG.md)

---

<a id="现行维护规则分卷与教程分别校订"></a>
<a id="section-1"></a>
## 1. 现行维护规则：分卷与教程分别校订

1. **先选读者问题和职责边界**，再写模块、实体、状态、流程、失败分支；不要按源码文件名无层次堆砌。
2. 当前设计正文在 `volumes/`，这里是单篇教程；两边有各自的手写增补，**不运行旧构建器互相覆盖**。
3. 校订结论记录源码 commit、文件与符号。源码注释、旧图和旧示例有冲突时，以实际函数体/调用参数为依据；行号仅作该版本定位。
4. 图中用真实类名、函数名或模块名，并标清区别。简化时序要说明未覆盖的分支，不把辅助函数画成源码中不存在的对象。
5. 历史段落可以保留；错误事实在原位置修正，不能只在文首加一句“以源码为准”而让核心流程继续误导读者。
6. 旧版本身份、星数、性能数字和外部产品比较，未经重新查验不升级为当前事实。不要把 `__release_date__` 当成安装版本。
7. 修改后检查实际章节目录、内部锚点、本地链接和代码围栏；文本检查、Mermaid 渲染与运行测试分别报告。

**目录与主题归属维护**：

- 每篇保留一个展开的 `## 目录`，同步全部二级、三级标题；代码/Prompt 示例里的 `#` 不属于章节。
- 章节移动时保留完整代码与图表，在原位置说明调用边界并链接到新位置；旧锚点继续兼容，避免把既有引用变成死链接。
- 工具篇解释注册/分发，Skills/Memory/多 Agent 篇解释对应领域逻辑；运行时负责压缩，Surface 负责展示与入口。完整 Hook 约定集中在插件篇。
- 执行 `python3 hermes/docs/_merge/audit_legacy.py` 和 `python3 -m unittest discover -s hermes/docs/_merge -p 'test_legacy_outline.py'` 检查可见目录、章节层级、链接与重复锚点。
- 纯重排时先保存快照，再用 `audit_legacy.py --baseline <快照目录> --preserve-diagrams` 对照图表内容；若本次本来就在按源码修图，不应把修图前快照当作“不许变图”的验收基线。

本轮范围与逐篇状态见 [REVIEW_AND_CHANGES](REVIEW_AND_CHANGES.md)，推荐读法见 [README](README.md)。

<a id="历史维护地图2026-10-14-原稿非当前操作规范"></a>
<a id="section-2"></a>
## 2. 历史维护地图（2026-10-14 原稿，非当前操作规范）

以下保留旧编排/合卷脉络。表中 Canonical、文件规模和附录位置是当时的描述；不要据此重建或恢复已删除文件。

<a id="canonical-地图按-catalog-类"></a>
<a id="section-3"></a>
## 3. Canonical 地图（按 CATALOG 类）

| 类 | Canonical | 新结论写哪里 |
|----|-----------|--------------|
| B | `ARCHITECTURE.md` | §0 / §4 / §11 |
| C | `SURFACE_ARCHITECTURE.md` | 全文 |
| D | `AGENT_LOOP_ARCHITECTURE.md` · `STATE_AND_AUXILIARY.md` | 循环 vs SessionDB/auxiliary |
| E | `PROMPT_SYSTEM_ARCHITECTURE.md` | §1–§17 |
| F | `MEMORY_*` · `TOOLS_*` · `SKILLS_*` · `MCP_*` · `PLUGINS_*` | 各单文件 |
| G | `CLI_GATEWAY_SYSTEM.md` · `HITL_APPROVAL_FLOW.md` | §4 网关；附录不写新结论 |
| H | `MULTI_AGENT_ARCHITECTURE.md` | §1–§16；Kanban 深潜单独 `KANBAN_*` |
| I | `SECURITY_SCAN_DEEP_ANALYSIS.md` | Part A 安全 · Part B Background Review |
| A | `VERSION_HISTORY.md` | 发版表 |

<a id="2026-10-14-整理"></a>
<a id="section-3-1"></a>
### 3.1 2026-10-14 整理

| 动作 | 说明 |
|------|------|
| `EXECUTION_FLOW` | → `archive/`；stub 在根目录 |
| `BACKGROUND_REVIEW` | → `SECURITY` Part B |
| `CLI_GATEWAY` 文末重复 | → `appendices/GATEWAY_RUNNER_WALKTHROUGH.md`（摘要） |
| 新增 | `CATALOG.md` · `STATE_AND_AUXILIARY.md` |

勿再 fork `*_DEEP*` / `*_COMPLETE*` / `*_OVERVIEW*`。

---

<a id="模块规模2026-10-wc--l-快照"></a>
<a id="section-4"></a>
## 4. 模块规模（2026-10 `wc -l` 快照）

| 模块 | 路径 | 约行数 |
|------|------|--------|
| `AIAgent` 壳 | `run_agent.py` | ~1550 |
| **对话主循环** | `agent/conversation_loop.py` | ~1860 |
| SessionDB 包 | `hermes_state*.py`（34 文件） | 见 STATE_AND_AUXILIARY |
| Auxiliary | `agent/auxiliary_*.py` | ~17 文件 |
| CLI | `hermes_cli/` | 500+ 模块文件 |
| TUI 桥 | `tui_gateway/` | ~86 py |
| 投递账本 | `gateway/delivery_ledger.py` | ~340 |

```text
run_agent.AIAgent.run_conversation  →  conversation_loop.run_conversation
publish_session_event（AgentScope）≠ Hermes；Hermes 用 SessionDB + gateway delivery
```

---

<a id="memory-叙事"></a>
<a id="section-5"></a>
## 5. Memory 叙事

主模型仍为 **三层**：Persistent Memory · Session Search · Optional External Provider。  
「六层」= AGENT_LOOP 扩展分析视角。见 `MEMORY_SYSTEM.md` §1。

---

<a id="刷新检查清单"></a>
<a id="section-6"></a>
## 6. 刷新检查清单

- [ ] 文首版本 + 核对日期
- [ ] 新 Surface → `SURFACE_ARCHITECTURE.md`
- [ ] 新循环/SessionDB → `AGENT_LOOP` + `STATE_AND_AUXILIARY`
- [ ] 新 IM/投递 → `CLI_GATEWAY` §4
- [ ] 发版 → `VERSION_HISTORY.md`
- [ ] 更新本表行数（`wc -l`）
- [ ] `website/docs/` 英文是否需同步

---

<a id="相关"></a>
<a id="section-7"></a>
## 7. 相关

- [README.md](README.md)
- [CATALOG.md](../../CATALOG.md)
