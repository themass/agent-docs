# Hermes Agent 文档

**先读：[HERMES.md](HERMES.md)**  
正文说人话。架构图、类图、时序图里写 **类名和方法名**（`AIAgent.run_conversation` 这种），旁边用一句话说明它在干什么。主文：[HERMES.md](HERMES.md)。

| 还要什么 | 去哪 |
|----------|------|
| 某一模块的长文、原有 Mermaid、大表 | [archive/legacy/](archive/legacy/) |
| 按卷拼起来的全文（不作为主入口） | [volumes/MANIFEST.md](volumes/MANIFEST.md) |
| 卷和旧文件名对照 | [CATALOG.md](CATALOG.md) |
| Content Studio 产品栈 | [../content-studio-agent/README.md](../content-studio-agent/README.md) |

源码：`hermes-dev/hermes-agent/`。


---

<a id="source-supplement"></a>

## 增补：当前分卷阅读入口与维护边界

本轮按读者需求把分卷升级为可独立阅读的设计书；上面的“分卷不作为主入口”保留为历史说明，**新读者请从 [分卷总览与大纲](volumes/README.md) 开始**。`HERMES.md` 仍是短版全景，归档仍用于追溯，不必一次读完。

- 想先看全貌：[卷一](volumes/01-platform-and-architecture.md#source-supplement) → [全书阅读路线](volumes/README.md)。
- 想深入后端：[模型](volumes/10-model-backends-and-resilience.md) → [执行环境](volumes/11-terminal-execution-backends.md) → [长期任务/包发布](volumes/12-automation-and-package-runtime.md) → [配置/秘密/观测](volumes/13-config-secrets-and-observability.md)。
- 想判断是否覆盖：[源码覆盖审计](volumes/SOURCE_AUDIT.md)，不要用篇幅代替理解深度。
- 想维护：[写作与验收标准](volumes/VOLUME_STANDARD.md) · [本轮变更](volumes/CHANGES.md)。

本轮依据本地提交 `60d00c5633ad76f3dd8e3ecd79f77f1c6f8e6fdd`，未把它冒充远端最新版本。新增内容直接维护在 `volumes/`，不要通过重建旧归档覆盖手写章节。
