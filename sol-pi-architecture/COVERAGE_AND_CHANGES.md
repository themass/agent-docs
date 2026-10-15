# SoL-Pi 文档覆盖、缺口与改动记录

## 1. 范围和基线

- 日期：2026-10-15。
- 源码：`SoL-Pi` HEAD `06b3ee358ddc5cebc5fb21a8e7493fab2db508ce`；package `0.1.0`。
- 本轮仅编辑本架构文档目录；源码及 Pi 上游不改动。
- “自己的部分”按 SoL-Pi 实现 owner 解释，同时补充源码 README 的项目自我介绍；不是对技术发明或用户产权作结论。

## 2. 覆盖矩阵和文件改动

| 文件 | 原有内容 | 本轮补充 |
|---|---|---|
| README.md | 文档入口 | 自有能力入口、版本边界、按目的阅读路线 |
| ARCHITECTURE.md | 四机制长篇深读 | owner 图、状态恢复矩阵、fail-open 作用域校准、运维与计费合同 |
| DESIGN_THINKING_SERIES.md | 九幕导读 | 第十幕：独立扩展的设计价值、代价与改进归属 |
| OWN_IMPLEMENTATION_DEEP_DIVE.md（新增） | 无 | 10 章项目介绍、能力归属、四机制后端、图示、代码注释和验收清单 |
| COVERAGE_AND_CHANGES.md（新增） | 无 | 覆盖、验证结果、限制与改动摘要 |

既有 diagrams 文件未改动。原有三个顶层 Markdown 只追加，未删减原文。

## 3. 重点发现：不是泛化“缺少后端”

1. SoL-Pi 已有 canonical file queue、secure OP object handling、EPR quote verifier、OCC branch-aware state 和 continuation barrier，不应误报这些缺失。
2. 真正需校准的是 contract：同进程 queue 不是跨进程锁；receipt 引用真实不是诊断完整；sidecar 可回读不是掉电强持久；TUI savings 不是金额结算。
3. 原文“fail-open 全链路”过强。OP root 初始化在循环 catch 外，EPR archive/journal 在 provider catch 外；磁盘错误怎样影响 Pi 应通过真实 host 测试明确。
4. AF 不复制 bash details，完整 fused 输出依赖 text readback path 等桥接；记录为待验收的集成边界，不宣称已复现故障。
5. 归档 GC/配额/备份、schema 演进、其他 extension 的 async lifecycle 组合，以及实际成本质量消融仍需工程合同。

## 4. 本轮检查结果

### 源码与环境

- 源码 HEAD 与 git status 只读记录，工作区 clean。
- 读取源码 AGENTS 和完整 agents-install.md；未安装或配置 Pi/SoL-Pi，未更改有效配置或密钥。
- Node `v26.11.1`；源码 checkout 无 `node_modules`。
- 未运行 npm ci、typecheck、Vitest、pack 或 live-provider benchmark；未申请网络/依赖安装。本轮不是安装任务，不宣称完成安装协议。

### 两个预检查：失败如实保留

```sh
node ../SoL-Pi/scripts/check-sol-pi-config.mjs --config ../SoL-Pi/sol-pi.example.json --require-all-enabled
# exit 1: actionFusion must be true

node ../SoL-Pi/scripts/check-pi-compat.mjs
# exit 1: ERR_MODULE_NOT_FOUND @earendil-works/pi-coding-agent
```

第一项说明示例文件不是 all-enabled profile，不代表示例 schema 一定无效；第二项受缺失依赖阻断，不能推断 Pi API 不兼容。失败后未继续安装/启动验证，没有绕过检查。Compatibility 文档内的既往测试数量与通过记录是仓库声明，不作为本轮运行结果。

### 文档验收

检查原始三个文件的 byte-prefix 保留、本轮新增本地链接、代码围栏配对及 scoped `git diff --check`。Mermaid 未实际逐图渲染，静态围栏检查不等于渲染或运行验证。

## 5. 总结与下一步

本轮把“介绍四机制”升级为“谁拥有能力、数据如何流转、失败如何传播、状态如何恢复、哪些保证仍需实测”。新增图涵盖能力架构、时序、流程、接口关系与状态机；原文保留，注释放在文档摘录而非修改源码。

建议经授权安装锁定依赖后，先跑现有 full suite 和 real AgentSession tests，再增加 ENOSPC/journal failure、超长 fused logs、第三方 async settled handler、archive 备份清理场景。最后以质量/时延/主模型与 reducer 总成本的联合指标衡量收益。
