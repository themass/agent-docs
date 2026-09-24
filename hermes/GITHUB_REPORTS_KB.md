# GitHub 报告库：普通用户怎么用

报告目录：`~/.hermes/profiles/github/reports/`

**不需要** Obsidian、**不需要** 记终端命令。

---

## 方式一：浏览器（推荐，最好看）

一条命令，自动打开网页：左侧按日期选报告，右侧阅读 Markdown / 看视频。

```bash
~/.hermes/profiles/github/scripts/github-analyst.sh browse
```

或（若已配置别名）：

```bash
github-reports
```

浏览器地址：<http://127.0.0.1:18765/index.html>

停止后台小服务（可选）：

```bash
~/.hermes/profiles/github/scripts/github-analyst.sh stop-browse
```

Cron / SOP 跑完后也会更新 `index.html`；随时再执行一次 `browse` 即可看到最新内容。

---

## 方式二：Workspace / Chat（不用离开对话）

确保 Profile 为 `github`，Gateway 已启动。在 Chat 里直接说：

| 你说 | 效果 |
|------|------|
| `打开报告库网页` | Agent 执行 `browse`，浏览器打开 |
| `报告库` | 列出最近报告摘要 |
| `打开最新日报` | 读出全文 |
| `打开最新视频` | 打开 mp4 |
| `总结 2026-06-01 的日报` | 读指定日期文件 |

---

## 已配置的能力（给进阶用户）

| 组件 | 用途 |
|------|------|
| `obsidian` skill | Agent 读写报告库 Markdown |
| `markitdown` MCP | Chat 里把 PDF/Word 转成 MD |
| `report-library` skill | 报告库路径与话术 |

环境变量：`OBSIDIAN_VAULT_PATH` → 报告目录（见 `~/.hermes/profiles/github/.env`）。

改 MCP 配置后：`cd hermes-dev && ./stop-dev.sh && ./start-dev.sh`

---

## 高级：终端（仅调试）

一般用户可跳过本节。

```bash
# 仅当 browse 不可用时
open ~/.hermes/profiles/github/reports
```

---

## 故障排查

| 现象 | 处理 |
|------|------|
| 浏览器空白或无法加载正文 | 必须用 `browse` 启动本地服务，不要双击 `index.html` |
| 端口占用 | `stop-browse` 后重试，或 `REPORT_VIEWER_PORT=18766 browse` |
| Chat 没有 markitdown | 重启 Gateway，检查 `~/.hermes/config.yaml` 中 `mcp_servers.markitdown` |

相关：[MULTI_AGENT_PROFILES.md](./MULTI_AGENT_PROFILES.md)
