# Hermes 文档分类与合订本映射

> **合订本（按章合并）**：[`volumes/MANIFEST.md`](volumes/MANIFEST.md)  
> **维护核对**：2026-10-15 · 现行分卷直接编辑；不要用归档覆盖手工增补。

---

## 九卷结构

| 卷 | 合订本 | 章（原独立文档） |
|----|--------|------------------|
| **一** | [01-platform-and-architecture.md](volumes/01-platform-and-architecture.md) | ARCHITECTURE · WORKSPACE_VS_WEBUI · HERMES_ATLAS_TRENDING |
| **二** | [02-surface-and-presentation.md](volumes/02-surface-and-presentation.md) | SURFACE_ARCHITECTURE |
| **三** | [03-runtime-session-and-loop.md](volumes/03-runtime-session-and-loop.md) | AGENT_LOOP · STATE_AND_AUXILIARY · EXECUTION_FLOW（考古全文） |
| **四** | [04-prompt-and-context.md](volumes/04-prompt-and-context.md) | PROMPT_SYSTEM · SUBAGENT_RUNTIME_PROMPT_EXAMPLE |
| **五** | [05-capabilities-extensions.md](volumes/05-capabilities-extensions.md) | MEMORY · TOOLS · SKILLS · MCP · PLUGINS |
| **六** | [06-gateways-channels-and-hitl.md](volumes/06-gateways-channels-and-hitl.md) | CLI_GATEWAY · HITL · TELEGRAM · Gateway 附录 |
| **七** | [07-multi-agent-and-kanban.md](volumes/07-multi-agent-and-kanban.md) | MULTI_AGENT · KANBAN 深潜 |
| **八** | [08-security-and-governance.md](volumes/08-security-and-governance.md) | SECURITY（早期合卷含 Background Review；legacy 正文现归 Skills 篇） |
| **九** | [09-reference-history-and-versions.md](volumes/09-reference-history-and-versions.md) | VERSION_HISTORY · DOC_MAINTENANCE · LANGGRAPH · VIDEO |

**现行正文**：`volumes/*.md`。**独立教程与历史脉络**：`archive/legacy/*.md`（已开始按源码校订，不是自动回填分卷的唯一编辑源）。

---

## 图表保全

合订本每卷 §「图表统计」列出各章 **Mermaid 块数** 与 **表格行数**。重建后应满足：

- 卷内 Mermaid 总数 ≈ 各章 `_merge/sources` 之和（卷三含考古 9 块 + Agent Loop 10 块等）  
- 勿手工删 ` ```mermaid ` 或表格行；叙述去重只通过「去重说明」与卷序优先级，**不删图**

---

## 维护流程

1. 日常更新直接修改对应 `volumes/` 分卷，按文末维护规范执行校验。
2. 校订旧教程时修改 `archive/legacy/`，同步其目录与核对记录；需要同步分卷的结论单独人工审阅。
3. `_merge/build_volumes.py` 只保留早期合卷用途，**不要作为日常维护步骤**，以免覆盖现有增补。
4. 版本史只记录已核实的版本身份，不把旧 tag 或 `__release_date__` 当成当前安装版本。

---

## 与 AgentScope

| Hermes | AgentScope |
|--------|------------|
| `docs/hermes/docs/volumes/` | `docs/agentscope/AGENTSCOPE.md` |
| Gateway + delivery_ledger | Channel + MessageBus |


---

<a id="source-supplement"></a>

## 增补：手工扩写后的维护流程（优先采用）

以上重建流程用于早期合卷，**不能再作为日常增补操作**。当前 `volumes/` 含有不在 legacy 中的手工章节、新卷和审计文件；常规改动应直接编辑分卷并保留既有内容。

1. 从 [全书大纲](volumes/README.md) 选择对应卷；新横切专题优先建专卷并双向链接。
2. 核对源码，写清职责、状态归属、成功/失败路径；按 [写作标准](volumes/VOLUME_STANDARD.md) 标注事实、示意和未验证边界。
3. 更新该卷目录和 [覆盖审计](volumes/SOURCE_AUDIT.md)，再核对 `SOURCE_EVIDENCE.json` 的引用。
4. 在 docs 仓库根执行 `python3 hermes/docs/_merge/audit_source.py --check` 与 `python3 hermes/docs/_merge/verify_volumes.py`；源码/精确引用确实变动后先审阅，再使用 audit 的 `--write` 更新清单。
5. 人工渲染检查 Mermaid；文本验收不等于图形验收，也不等于 Hermes 运行测试。

`_merge/build_volumes.py` 已有覆盖保护，需显式设置 `HERMES_REBUILD_VOLUMES=1` 才会重建旧卷。**本轮没有执行覆盖式重建，也不要为了更新清单打开该开关。** 若未来确实需要重建，先保存手写增补并审阅重建 diff。

扩写文件对应关系及本轮保留策略见 [CHANGES](volumes/CHANGES.md)。
