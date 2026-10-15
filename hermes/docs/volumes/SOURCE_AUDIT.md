# Hermes 模块覆盖审计与缺口清单

> 本轮不是一次“文档字数审计”，而是把仓库清点、阅读导航、源码专题与运行验证分开。以本地快照 `60d00c5633ad76f3dd8e3ecd79f77f1c6f8e6fdd` 为依据；核对时源码工作区干净。

## 目录

- [1. 结论与阅读边界](#audit-findings)
- [2. 完整模块族地图](#audit-map)
- [3. 本轮补齐的高价值缺口](#audit-filled)
- [4. 仍需继续深潜的缺口](#audit-next)
- [5. 可复查证据与机械检查](#audit-proof)

<a id="audit-findings"></a>
## 1. 结论与阅读边界

现有文档的主干优势是回合、Prompt、Surface、Gateway 和记忆；主要问题不是没有总架构图，而是**后端、运行支撑、生命周期的状态与失败边界没有展开**。旧“达标”表示当时的写作结构评价，不能推导为所有源码已读、所有故障已验证。

本轮机械清点 **5389 个受 Git 管理的代码文件**：运行类 4732、构建/评测/网站类 420、技能内代码 237。这不是 5389 个文件逐行审计；它们默认标为 L0。扩展名、排除测试/vendor 的规则和具体记录见 [SOURCE_INVENTORY.json](SOURCE_INVENTORY.json)。

清单不含二进制素材、纯配置目录清单、未跟踪文件；测试按路径/文件名机械排除，分类并不保证语义上每个文件都是生产逻辑。配置式的 optional MCP、plugin catalog 等仍应通过专题导航继续核对。

<a id="audit-map"></a>
## 2. 完整模块族地图

文件数只是定位规模；链接是 L1 导航，不声称整包已达到 L2。根目录文件族包含 facade、state、logging、bootstrap 等横切模块。

| 模块族 | 清点代码文件数 | 阅读入口 | 本轮核对边界 |
|---|---:|---|---|
| `(root)` | 60 | [01](01-platform-and-architecture.md) · [03](03-runtime-session-and-loop.md) | 既有核心/state说明；新增 bootstrap/logging/profile 归属导航 |
| `.github` | 2 | 构建/资产清单（待建立专节） | 资产/构建/评测导航；未逐项解释执行配方 |
| `acp_adapter` | 14 | [02](02-surface-and-presentation.md) | 已有 ACP 专节；未逐 IDE/协议交互验证 |
| `agent` | 346 | [03](03-runtime-session-and-loop.md) · [04](04-prompt-and-context.md) · [10](10-model-backends-and-resilience.md) | 原书讲回合/上下文；新卷补后端、凭据、registry、secret、观测等核心边界 |
| `apps` | 2142 | [02](02-surface-and-presentation.md) | Surface 既有深潜；尚未逐个核对所有桌面组件、安装器与共享库 |
| `contributors` | 2 | 构建/资产清单（待建立专节） | 资产/构建/评测导航；未逐项解释执行配方 |
| `cron` | 40 | [12](12-automation-and-package-runtime.md) | 补 tick、execution、delivery 与 unknown；script/blueprint/配额等仍需扩写 |
| `docker` | 8 | [09](09-reference-history-and-versions.md) | 资产/构建/评测导航；未逐项解释执行配方 |
| `evals` | 163 | [03](03-runtime-session-and-loop.md) | 资产/构建/评测导航；未逐项解释执行配方 |
| `gateway` | 184 | [06](06-gateways-channels-and-hitl.md) · [07](07-multi-agent-and-kanban.md) | 沿用原书入口/出站设计；本轮未逐个平台重做适配器审计 |
| `hermes_cli` | 675 | [02](02-surface-and-presentation.md) · [13](13-config-secrets-and-observability.md) | 配置/身份与管理入口；每个子命令仍是主要缺口 |
| `hermes_platform` | 13 | [13](13-config-secrets-and-observability.md) | 补事实/解析与 PM 的边界；未实测全部 OS |
| `native` | 2 | [01](01-platform-and-architecture.md) | 原生实现、构建与 IPC 细节尚未深潜 |
| `nix` | 21 | [09](09-reference-history-and-versions.md) | 资产/构建/评测导航；未逐项解释执行配方 |
| `optional-skills` | 183 | [05](05-capabilities-extensions.md) | 资产/构建/评测导航；未逐项解释执行配方 |
| `plugins` | 229 | [05](05-capabilities-extensions.md) · [05](05-memory-system-reference.md) | 补管理器、loader、所有权；229 个文件不等于229份插件行为已解释 |
| `pm` | 51 | [12](12-automation-and-package-runtime.md) | 补 worker、安装/发布/receipt；各平台构建与全部 recovery 分支仍未穷尽 |
| `providers` | 2 | [10](10-model-backends-and-resilience.md) | 补 ProviderProfile 的声明契约，不把所有服务商声明都当已实测 |
| `scripts` | 202 | [09](09-reference-history-and-versions.md) | 资产/构建/评测导航；未逐项解释执行配方 |
| `skills` | 54 | [05](05-capabilities-extensions.md) | 资产/构建/评测导航；未逐项解释执行配方 |
| `tools` | 348 | [05](05-capabilities-extensions.md) · [11](11-terminal-execution-backends.md) | 补执行 backend，其他 browser/media/搜索等具体工具仍需各自深潜 |
| `tui_gateway` | 106 | [02](02-surface-and-presentation.md) | 沿用原书 RPC/compute host 设计；新文件以清单可发现 |
| `ui-tui` | 358 | [02](02-surface-and-presentation.md) | 已有事件与 UI 说明；没有复核所有组件与状态切换 |
| `web` | 162 | [01](01-platform-and-architecture.md) · [02](02-surface-and-presentation.md) | 页面/API 链路仍需逐路由审计 |
| `website` | 22 | 构建/资产清单（待建立专节） | 资产/构建/评测导航；未逐项解释执行配方 |

<a id="audit-filled"></a>
## 3. 本轮补齐的高价值缺口

| 原先薄弱处 | 这次补的内容 | 位置 |
|---|---|---|
| 压缩与请求投影混为一谈 | 轻量整理两条路径、工作历史/请求副本、DB 恢复、coverage/水位/租约、归档与搬运旧副本 | [卷三 §4.7–4.10](03-runtime-session-and-loop.md#sec-4-lightweight) |
| 工作消息生命周期缺少闭环 | 字段/身份、CLI 双历史恢复、增量 flush、原地压缩代际切换、并发刷新与崩溃边界 | [卷三 §4.11–4.15](03-runtime-session-and-loop.md#sec-4-working-object) |
| 思考后端被简化成 SDK | 声明/协议/客户端/凭据分层；redirect 竞争；fallback 运行时重绑；回放字段 | [卷十](10-model-backends-and-resilience.md) |
| 执行后端只列厂商 | spawn-per-call、shell snapshot、cwd、task identity、前后台、安全检查与 exit fence | [卷十一](11-terminal-execution-backends.md) |
| 插件只讲 register | scope overlay、所有权代次、任意顺序卸载、并发 import、权限接缝 | [卷五第7节](05-capabilities-extensions.md#cap-plugin-lifecycle) |
| 多 Agent 几种机制混讲 | delegate 预算/继承、background batch、capability handle、内存 reconnect、MoA 边界 | [卷七第6节](07-multi-agent-and-kanban.md#multi-runtime-boundaries) |
| Cron 只讲出站 | tick gate/锁、先落账、owner/progress、unknown 不重播、tombstone 幂等记忆 | [卷十二](12-automation-and-package-runtime.md) |
| PM 被当安装脚本 | 独立 worker、工件发布、配置快照检查、恢复 journal 与 receipt | [卷十二](12-automation-and-package-runtime.md#ops-pm) |
| 支撑状态隐形 | profile home、multiplex secret scope、resolver、日志与 monitoring 的不同证据强度 | [卷十三](13-config-secrets-and-observability.md) |
| 维护入口冲突 | 缺失标准补齐；旧重建说明澄清；新总目录与机械审计 | [标准](VOLUME_STANDARD.md) · [入口](README.md) |

这里“补齐”指表中专题的核心说明，不指整包全分支覆盖。源码符号解析验证也不是运行正确性的证明。

<a id="audit-next"></a>
## 4. 仍需继续深潜的缺口

以下是后续最有价值的工作单，不隐藏在“全部完成”的结论里。每项应按标准补输入/输出、状态、主链、失败、恢复与图。

| 优先级 | 待补专题 | 需要讲清的真实问题 |
|---|---|---|
| P1 | SessionDB 文件族的运维/恢复全表 | `hermes_state_*` 的 WAL、readpool、锁 owner、repair、migration、rewind 各自负责哪些故障；当前卷三不是所有文件逐分支复核 |
| P1 | CLI 命令与配置迁移地图 | 大量 `hermes_cli/` 模块如何路由；设置修改何时生效、哪些会延迟到下轮/新会话 |
| P1 | Browser 能力完整链 | provider → browser tool → 页面会话 → 下载/上传 → 权限 → 异常与销毁；不是只有 MCP 名字 |
| P1 | 媒体与语音完整链 | IM 附件抓取、图片 token/eviction、转写/TTS、缓存与 provider 错误路径 |
| P1 | Dashboard / Desktop 页面/API | RPC/HTTP 路由与 UI state、账号/连接器/MCP OAuth；现有卷二不是所有页面的契约 |
| P2 | 每个 IM adapter 的差异矩阵 | auth、thread/topic identity、编辑/流式、附件上限、限流、重连、审批回传 |
| P2 | Hosted rooms / relay / rendezvous | 成员活动、peer HTTP/WS、信任、断线重连和跨 host ownership |
| P2 | MoA 全分支与费用 | presets、alternation、prepared request、late usage、reference 隐私与缓存 |
| P2 | Cron 周边 | quota hold、incident、blueprint、建议、script、bot chat 交付与失败 copy 的完整关系 |
| P2 | 插件能力族矩阵 | 每类 provider 的 setup/availability/gate/unload；外部 memory 提供商的快照更新核对 |
| P2 | 安装、原生构建与 CI | Nix/Windows/Termux、native、bootstrap installer、发布签名、更新恢复的逐场景证据 |
| P3 | Skill / catalog 单项资产 | 每个技能/MCP 配方的目的、外部依赖、风险、可用性；不得以目录清点冒充运行验证 |
| P3 | Batch / eval / trajectory 数据契约 | 数据格式、断点恢复、评分与成本汇总；不是 Agent 交互循环的简单循环调用 |

优先级是文档增补建议，不是源码缺陷的严重度。某能力的文件存在但没深潜，不代表能力缺失。

<a id="audit-proof"></a>
## 5. 可复查证据与机械检查

[SOURCE_EVIDENCE.json](SOURCE_EVIDENCE.json) 当前记录 **103 条精确 `文件:符号` 引用**（同一符号在不同文档出现会分别记录）。它验证存在与行号，不能证明所有图边或设计动机正确。手工阅读涵盖的其他方法在正文中给出入口，但不计为机械解析成绩。

每个 Python 文件的 AST 类/顶层函数/类方法用于后续定位，不 import 应用；其他语言只记路径、hash、行数和卷导航，不声称做了 TypeScript/Rust 语义分析。

```sh
# docs 仓库根；只读源码。
python3 hermes/docs/_merge/audit_source.py --check
python3 hermes/docs/_merge/verify_volumes.py
```

首次验收使用编辑前副本，确认 74 份原 Markdown 保持未改前缀；卷三后续按用户要求在第4章和目录内插入标记明确的增补，剥离这两个限定增补块后仍恢复原文。其他文件继续按追加保全检查。这是不依赖 legacy 重建的保全证据。运行时测试和 Mermaid 视觉渲染没有在此被偷偷算成通过。

### 审计总结

原书主线保留，补充的重心从“组件清单”推进到“状态、所有权、失败与恢复”。现在可以检查哪些专题已深入、哪些仅有导航；距离每个模块全分支解释仍有明确工作单。

### 工作消息生命周期补充的本次检查说明

本次新增 §4.11–4.15，源码引用总数为 81，新增片段总计 30 个 Mermaid 围栏；13 项审计工具测试通过。仅去除本次章内与目录插入，可逐字节恢复本次编辑前的卷三（包括此前已补的 §4.7–4.10）。

旧 `/tmp/hermes-docs-before` 的 74 文档基线此次检查未通过：卷一、MANIFEST、卷三存在该历史基线之外的正文变化；卷三在本次编辑前的副本中就已经存在这一差异。本次没有回退这些其他编辑，也未放宽保全脚本，因此不能将历史 74 文档保全重新报告为全部通过。结构检查不带该历史基线时通过；仍未执行 Mermaid 渲染或 Hermes 运行时测试。

### 外部上下文注入补充

卷三 §4.16 补充 Memory 与插件包装差异、字符串侧车与多模态 live part、请求投影及落库回放，增加一张流程图。当前共 90 条精确源码引用、32 个 Mermaid 围栏；结构检查和 13 项工具测试通过。本次插入可剥离并逐字节恢复本次编辑前卷三；不改变前述历史基线限制，未做 Mermaid 渲染或 Hermes 运行测试。

### Steer 交付链补充

卷四 §4.10 区分两处本轮 user 消息注入与 finalizer 原始文本转交，补充队列、位置、包装、flush 与下一轮边界。该有界专题加入源码符号审计；当前 103 条引用、18 份片段、33 个 Mermaid 围栏。13 项工具测试通过，未运行 Hermes / Mermaid 渲染。
