# LongHorizon-Harness 文档

保留两篇入口：设计讲“为何这样设计、保证什么”；源码走读讲“在哪里实现、如何验证”。旧文件在 `archive/legacy/`。

| 读什么 | 文件 |
|--------|------|
| **设计总览与历史架构**（MEA、公理、门禁、Adapter、Web） | [LONGHORIZON.md](LONGHORIZON.md) |
| **设计深化与工程边界**（缺口优先级、信任模型、证据时效、恢复对账、预算、安全、评测、路线） | [LONGHORIZON.md · 深化章节](LONGHORIZON.md#设计深化与工程边界) |
| **源码走读**（Manager 循环、Adapter、Supervisor） | [SOURCE.md](SOURCE.md) |
| **当前源码校准**（版本定位、resume、Final response、完成门禁与测试覆盖） | [SOURCE.md · 校准章节](SOURCE.md#当前源码校准与验证索引) |

## 本次补充的结论

现有文档已解释运行骨架；更需要深化的不是角色数量，而是**当前契约与当前产物的证据绑定、执行副作用与账本间的恢复协议、可控的资源收敛**。

2026-10-15 的静态核对基线为本地源码提交 `b498162fc1b96ff469146f04a698c829c89e3eab`。新增章节分别标明现有行为、推论和建议；建议不代表已实现。本次未执行项目测试、真实 GUI 任务或论文评测。

源码根：`/Users/gqli/work/deepagents/LongHorizon-Harness`。权威行为以该仓库源码和测试为准；历史代码引用行号可能已漂移。论文链接保留用于背景：[arXiv:2608.01964](https://arxiv.org/abs/2608.01964)，本次未核验其在线内容或复现成绩。


## 推荐阅读路径

1. 先读 [LONGHORIZON.md](LONGHORIZON.md) 的总览、历史架构和 D1–D13，建立“目标保证”与“工程边界”的区别。
2. 再读 [源码还原：整体架构与模块设计](LONGHORIZON.md#源码还原整体架构与模块设计)，按 A1–A14 对照实际模块、进程、状态和数据流。
3. 最后读 [SOURCE.md](SOURCE.md) 的 S1–S6 与 [模块源码精读与注释](SOURCE.md#模块源码精读与注释)，从具体函数、代码片段和测试落点验证结论。

## 本轮改动记录

本轮在不删除原有正文的前提下，继续补充两篇主文档：

- `LONGHORIZON.md` 新增 A1–A14“源码还原：整体架构与模块设计”，把配置组装、四类后端、Environment、日志归一化、Auditor、Supervisor、ControlBus、Web 事件、插件和轨迹产物串成完整后端架构；新增 17 个 Mermaid 图，覆盖分层/部署、类关系、时序、流程、状态和影响矩阵。
- `SOURCE.md` 新增 C1–C12“模块源码精读与注释”，增加带解释性注释的代码节选、错误与清理流程、快照完成谓词、幂等与 revision、resume identity、前端合并、截图物化和缺口—源码—测试矩阵；新增 3 个 Mermaid 图。
- 所有新增判断均区分“源码已实现”“从源码推论”“建议建设”；尤其没有把 `EventTailer` 重同步、`ControlBus` 幂等或 `Supervisor` resume 误写成不存在。

## 本轮验证记录

本轮对本地源码提交 `b498162fc1b96ff469146f04a698c829c89e3eab` 执行了两批后端自动测试，使用 `PYTHONDONTWRITEBYTECODE=1`、`PYTHONPATH=/Users/gqli/work/deepagents/LongHorizon-Harness/src` 和 `python3 -m pytest -q -p no:cacheprovider`：

- 第一批：resume、manager loop、role prompts、runtime signals、ControlBus close，共 **102 passed**。
- 第二批：agent registry、Codex/DeepSeek/OpenCode adapters、provider errors、local environment hardening、trajectory artifacts、`tests/webapi`、`tests/supervisor`，共 **201 passed, 1 skipped**。
- 合计：**303 passed, 1 skipped**。测试结果支持文档中所引用的这些路径，但不等价于真实模型账户、桌面 GUI、插件安装、远程 Environment 或全仓库所有测试均已验证。
- Mermaid 图做了代码块、链接和结构性检查；本环境未安装 Mermaid 渲染器，因此未宣称完成浏览器/渲染级图形校验。
- 本轮只修改文档；源码仓库的既有 `doc-sn/ARCHITECTURE_PART1.md` 修改保持不动。

## 仍需后续确认

文档已把剩余风险定位到源码落点，但没有把建议伪装成实现。优先级较高的后续工作是：统一不同 Adapter 的角色权限策略；将任务/产物/报告绑定到明确版本；为外部副作用增加 intent、receipt 和恢复对账；补充累计资源与真实进度收敛策略；统一原始日志和截图的敏感信息治理。

### 验证复现说明

测试使用 pyenv Python 3.12.11（`/Users/gqli/.pyenv/versions/3.12.11/bin/python3`）。当前登录 shell 的 Homebrew Python 没有 pytest，因此复现时建议显式使用上述解释器，不要仅凭 `python3` 名称假定依赖一致。第二批另以 `-rs` 复跑，仍为 201 passed、1 skipped；跳过原因是 `tests/webapi/test_webapi.py:282` 需要已构建的 Web bundle，本地未构建。前端构建与前端测试未执行。

本轮相对开始时的备份，设计文档增加 **735 行**、源码走读增加 **461 行**（含总目录新增入口），合计新增 **20 个 Mermaid 图**。原有正文逐行顺序保留，全部相对文档链接与锚点已通过检查；没有修改项目运行时源码。
