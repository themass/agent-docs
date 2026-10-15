# Pi 文档中心

> monorepo 路径：`pi/` · 源码级架构整理
> **源码基线补充**：当前本地 Pi commit `1729ff447841e7666159a6f8bf70fbd6bac05642`（2026-10-15，workspace 版本 1.2.0）。先阅读 [PI_SOURCE_DEEP_DIVE_2026.md](./PI_SOURCE_DEEP_DIVE_2026.md)，它补充了 Durable、Chord、MCP、Code Mode、远程环境和版本边界。

## 推荐阅读路径

```text
① DESIGN_THINKING_SERIES（九幕图解导读，~30min）
② JSONL_TREE_GUIDE（会话树 + 持久化）
③ ARCHITECTURE Part I（图表权威）
④ 专题：EXTENSIONS · SKILLS · RUNTIME_PROMPT
⑤ ARCHITECTURE Part II（改代码时深潜）
```


### 当前源码补充的阅读顺序

全景补充 → 后端深潜 → 运行时支撑 → 各旧专题的当前版本补充 → 源码导航。旧阅读路径继续保留；涉及版本冲突时，优先按顶部基线和当前版本补充理解。

## 文档索引

| 文档 | 说明 |
|------|------|
| [**PI_SOURCE_DEEP_DIVE_2026.md**](./PI_SOURCE_DEEP_DIVE_2026.md) | **最新源码级全景补充**：11 包地图、两条执行路径、Durable 后端/恢复、MCP/Code Mode/Chord/env |
| [**BACKEND_RUNTIME.md**](./BACKEND_RUNTIME.md) | **后端深潜**：提交协议、任务 phase、工具副作用、恢复和 JSONL/SQLite |
| [**RUNTIME_SERVICES.md**](./RUNTIME_SERVICES.md) | **运行时支撑**：cwd 重绑定、设置、资源/包发现、模型认证与诊断 |
| [**SOURCE_MAP.md**](./SOURCE_MAP.md) | **源码导航**：按问题定位入口、测试和阅读顺序 |
| [**COVERAGE_AND_CHANGES.md**](./COVERAGE_AND_CHANGES.md) | **覆盖审计与改动摘要**：模块覆盖、校验边界和未覆盖项 |
| [**DESIGN_THINKING_SERIES.md**](./DESIGN_THINKING_SERIES.md) | **九幕设计导读**（Agent/Loop、双循环、steer/follow-up、Harness） |
| [**diagrams/design-thinking-series.html**](./diagrams/design-thinking-series.html) | **九幕图解页**（蓝白速览，可浏览器打开） |
| [**JSONL_TREE_GUIDE.md**](./JSONL_TREE_GUIDE.md) | Entry 树、JSONL 行类型、三存储 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Part I/II 完整架构（3000+ 行，深潜权威） |
| [EXTENSIONS.md](./EXTENSIONS.md) | 扩展、多 Agent、Plan |
| [SKILLS_LIFECYCLE.md](./SKILLS_LIFECYCLE.md) | Skills 生命周期 |
| [RUNTIME_PROMPT.md](./RUNTIME_PROMPT.md) | 运行时 Prompt |
| [pi-plugins-design.md](./pi-plugins-design.md) | 插件设计 |

## 跨项目

- [pi-architecture/README.md](../pi-architecture/README.md)（Pi 文档总入口）
- [CROSS_AGENT_DESIGN_INDEX.md](../CROSS_AGENT_DESIGN_INDEX.md)
- [CROSS_AGENT_CONCEPT_MAP.md](../agent-doc-template/CROSS_AGENT_CONCEPT_MAP.md)

## 外部参考

- [Pi 设计思想图解](https://mp.weixin.qq.com/s/WB24MCub0fosrhZOlEiSAQ)（微信公众号；以本仓库源码为准）

## 路径迁移后的本地导航补充

上面的跨项目链接保留原文；其中部分对应旧目录。当前 Pi 栈入口位于 [pi-agent/pi-architecture/README.md](./pi-architecture/README.md)。跨项目索引若已移动，请通过仓库目录定位，不把历史失效链接视为源码不存在。
