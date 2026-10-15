# LongHorizon-Harness 文档

LongHorizon-Harness 在外部 Agent CLI 之上，通过 Manager、Executor、Auditor 构成可审计的长程执行外环。本文档集分为**架构设计**与**源码走读**：前者解释系统责任、协议和边界，后者提供具体实现与验证落点。

## 文档入口与阅读路线

| 目的 | 入口 | 推荐阅读 |
|---|---|---|
| 建立整体架构认识 | [LONGHORIZON.md](LONGHORIZON.md) | 第1–3章：目标、系统上下文、领域模型 |
| 理解后端如何执行和验收 | [组装与编排](LONGHORIZON.md#assembly) | 第4–7章：依赖组装、Round、后端、完成授权 |
| 理解恢复、运行托管与人工控制 | [持久化与恢复](LONGHORIZON.md#persistence) | 第8–11章：账本、Supervisor、ControlBus、Web |
| 评审工程边界和后续建设 | [信任与安全](LONGHORIZON.md#security) | 第12–15章：安全、预算、评测、演进 |
| 对照函数和代码节选 | [SOURCE.md](SOURCE.md) | [当前源码校准](SOURCE.md#当前源码校准与验证索引)、[模块源码精读与注释](SOURCE.md#模块源码精读与注释) |
| 查阅早期分卷 | [历史归档](archive/legacy/README.md) | 仅作历史参考，不是当前目录 |

## 本次结构重组：从合并材料到统一架构

本次不是继续向文件末尾追加章节，而是对 `LONGHORIZON.md` 进行主题归并、重复消除和章节重排：

- **统一主线：** 目标与约束 → 系统/领域模型 → 组装和编排 → 执行与验收 → 持久化和运行控制 → 质量属性与演进。
- **统一主题归属：** 完成门禁只在审计章详解；轮级恢复归持久化章，worker 所有权归 Supervisor 章，事件投影归 Web 章。跨主题使用引用，不再保留几套重叠总览。
- **统一事实层级：** 当前实现、实现边界和演进建议分开。已有 ControlBus 幂等/revision、EventTailer 重同步和 Supervisor resume 不再被未来方案遮蔽；证据版本绑定与外部副作用对账仍明确为建议。
- **保留独有深度：** 领域类图、部署图、时序/流程/状态图、代码节选、契约示例、权限矩阵和崩溃窗口分析均纳入相应主题。保留20个 Mermaid 图块，不以堆叠图数代替结构。
- **清理编辑遗留：** 移除卷序言、重复总结、A/D 两套附加章节编号及漂移行号式代码围栏；增加统一目录、读者路线和源码导航。

`SOURCE.md` 本次只更新架构回链，不重排其正文；早期分卷继续保存在 `archive/legacy/`，不改写历史归档。

### 主题迁移导航

| 原材料中的主题 | 现在的主要位置 |
|---|---|
| 总览、公理、重复的模块与部署图 | 第1–2章 |
| 领域类型、任务契约、配置与模型发现 | 第3–4章 |
| 角色可见性、Manager 路由、Adapter、Environment、插件 | 第5–6章 |
| Auditor、完成门禁、Final response、证据适用性 | 第7章 |
| Run 目录、轨迹截图、resume 和副作用对账 | 第8章 |
| Supervisor 生命周期、人工门禁、控制总线、Web 投影 | 第9–11章 |
| 信任模型、后端安全、累计预算、评测方法 | 第12–14章 |
| 缺口优先级、变更影响、ADR 和贯穿案例 | 第15章 |

## 源码基线与验证范围

- 核对日期：**2026-10-15**。
- 本地源码根：`/Users/gqli/work/deepagents/LongHorizon-Harness`。
- 源码提交：`b498162fc1b96ff469146f04a698c829c89e3eab`。
- 本次只修改文档，检查标题层级、目录锚点、本地链接、代码围栏、重复图块与 diff；**不重跑后端测试、不构建前端、不执行真实模型/GUI 或论文评测，也不宣称 Mermaid 渲染通过**。
- 源码仓库原有 `doc-sn/ARCHITECTURE_PART1.md` 修改保留，不属于本次改动。

### 历史自动测试记录（不是本次重跑）

此前源码核对在上述提交上记录了两批后端测试：

| 范围 | 当时记录的结果 |
|---|---|
| resume、manager loop、role prompts、runtime signals、ControlBus close | 102 passed |
| agent registry、Codex/DeepSeek/OpenCode adapters、provider errors、local environment hardening、trajectory artifacts、`tests/webapi`、`tests/supervisor` | 201 passed, 1 skipped |
| 合计 | **303 passed, 1 skipped** |

当时使用 pyenv Python 3.12.11（`/Users/gqli/.pyenv/versions/3.12.11/bin/python3`），设置 `PYTHONDONTWRITEBYTECODE=1`、`PYTHONPATH=/Users/gqli/work/deepagents/LongHorizon-Harness/src`，运行 `python3 -m pytest -q -p no:cacheprovider`，后接对应测试路径。第二批另以 `-rs` 复跑，结果相同；跳过项为 `tests/webapi/test_webapi.py:282`，原因是需要已构建的 Web bundle。

这份历史记录不代表全仓库测试、真实模型账户、桌面 GUI、插件安装或远程 Environment 均已验证。复现需显式选择具备 pytest 的解释器和对应测试路径，不能假定当前 shell 的 `python3` 与当时环境一致。

## 下一阶段的设计重点

优先事项是证据与任务/产物版本绑定、外部动作 intent—receipt—reconcile、各 Adapter 的权限语义契约，以及跨 resume 的累计预算和停滞治理。各项建议的现有基础、失效模式与关联章节见 [第15章](LONGHORIZON.md#evolution)；它们不是已经实现的能力或已复现的漏洞结论。
