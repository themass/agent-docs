# 虚拟开发团队 · 图解

可点击打开 HTML（暗/亮色、缩放、路径追踪）。正文流程见 [PROCESS.md](../PROCESS.md)，选型见 [SURVEY.md](../SURVEY.md)，**今晚怎么装**见 [SETUP.md](../SETUP.md)。

| 图 | 看什么 |
|---|---|
| [系统架构](./virtual-dev-team-stack.architecture.html) | 集成了哪些开源件、各在哪一层、三个真源如何分开 |
| [主循环设计](./virtual-dev-team-loop.workflow.html) | G1 / G1.5 / G2 → Multica 领卡 → Codex → Review → QA → archive |

## 集成件与作用（架构图节点）

| 件 | 作用 |
|---|---|
| 你 | G1 产品、G1.5 视觉、G2 架构签字 |
| Cursor | 人机入口：产品、架构、签字发生在这里 |
| OpenDesign | 有 UI 的卡出原型和 `DESIGN.md` |
| teamai-cli | 把 skills / rules / MCP 同步到 Cursor 与 Codex |
| Multica | 唯一看板；Agent 上板认领；拉起工人 |
| Headroom | wrap 两边工人，压缩工具输出 |
| Codex + Superpowers | 领卡实现：TDD、worktree、自检 |
| OpenSpec | Git 里的规格合同；archive 才更新真相 |
| CodeGraph | live callers / impact，少盲搜 |
| Playwright | QA 新会话，只跑 OpenSpec 场景 |
| Buzz | 可选人机房间；**不当板** |

不进栈（图中卡片）：ECC、deer-flow、eigent、oh-my-codex 默认安装。
