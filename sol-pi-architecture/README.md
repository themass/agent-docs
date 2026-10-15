# SoL-Pi — 文档

| 文件 | 用途 |
|------|------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 主文档：宿主边界、四机制、设计说明与模块走读 |
| [diagrams/AGENT_MODULE_DIAGRAMS.md](./diagrams/AGENT_MODULE_DIAGRAMS.md) | 逐模块图 SP-01…SP-20 |
| [diagrams/DIAGRAM_ATLAS.md](./diagrams/DIAGRAM_ATLAS.md) | 全局图 |
| [DESIGN_THINKING_SERIES.md](./DESIGN_THINKING_SERIES.md) | 九幕导读 |

宿主源码：`pi/packages/coding-agent`（本 monorepo `pi/`）。

---

## 2026 补充：先读 SoL-Pi 自己的部分

- [自有能力与源码深读](OWN_IMPLEMENTATION_DEEP_DIVE.md)：项目如何介绍自己、Pi/SoL-Pi 责任矩阵、四机制自己的实现、后端状态合同和缺口。
- [覆盖与验证记录](COVERAGE_AND_CHANGES.md)：源码基线、修改摘要、测试限制。

### 新增阅读路线

| 目的 | 路线 |
|---|---|
| 找项目自己的介绍 | 深读第 1 章 → 第 2 章能力归属 |
| 理解核心实现 | 深读第 4–7 章 → 原架构文档模块详解 |
| 后端/运维评审 | 深读第 8 章状态矩阵 → 第 9 章缺口与验收 |
| 理解设计取舍 | DESIGN_THINKING_SERIES → 新增第十幕 |

SoL-Pi 是独立 Pi 扩展，不是独立 daemon 或沙箱；它自己的特色是 canonical file queue、可回读 observation、可验证 receipt、缓存债务与压缩续跑调度。模型循环、原生工具、认证和 session compaction 仍由 Pi 提供。

当前 package 的测试基线 pin 为 Pi 0.85.1，peer `*` 不等于所有版本兼容。本地 `pi/` 源码是 API 对照材料，不自动代表实际运行的 npm package 版本。
