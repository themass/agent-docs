
## 18. Agent 治理修补（2026-11-11）

| 你提的 | 处理 | 结果 |
|---|---|---|
| 1. evaluator.md / reviewer.md 是死文件 | 移到 `souls/_unused/`，并写了 README 说明为什么它们不需要 soul（评估与审校都是纯规则，不调模型） | 已改 |
| 2. MCP 白名单要服务端强制 | **这条其实已经修过**（A-12 之后的代码）：`server.py:exposed_tool_names()` 让 `/mcp` 默认只暴露两个只读工具，未知工具名直接启动失败。我实测确认：默认 `['get_work_snapshot','get_integrity_gap_report']`，`POETRY_MCP_EXPOSED_TOOLS=get_work_snapshot,nope` 被拒绝 | 已核验，无需再改 |
| 3. 两份策略配置语义不一致 | `mcp-policy.yaml` 重写为 version 3：**只写 allow，不写 deny**。原因写进文件头：DeerFlow 的 AllowlistProvider 只做精确名匹配，旧版的 `"*publish*"` 这类通配从来就没生效过。同时 `check_profile.py` 新增「role → skill → allowed-tools」闭环校验 | 已改 |
| 4. 角色差异不在权限上 | 权限本来就该相同（最小权限）。真正缺的是**绑定可校验**，所以加了上面那条闭环：四个任务 skill 声明了 `read_file` 而它们绑定的角色没有该权限，**校验当场抓出 4 处不一致**，已从 skill 里删掉 `read_file`（它只用于 lead 加载 skill） | 已改，profile check 通过 |

`make test-all` 18/18 PASS。
