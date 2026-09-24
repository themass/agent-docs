# MCP（模型上下文协议）配置

DeerFlow 支持通过专用的 `extensions_config.json` 配置文件（位于项目根目录）来配置 MCP 服务器和技能，以扩展其能力。

## 架构：加载 → 绑定 → 执行

完整 mermaid 时序图、源码路径表、`tool_search` deferred 说明见英文版 **[MCP_SERVER.md](MCP_SERVER.md#architecture-mcp-load--bind--execute)**（内容与代码对齐，本节不重复缩写）。

要点：

1. `get_cached_mcp_tools()` 按 `extensions_config.json` **mtime** 失效缓存并重连 `MultiServerMCPClient`
2. `get_available_tools()` 将 MCP `BaseTool` 与内置/config 工具合并；**ToolNode 始终持有全量可执行工具**
3. `tool_search` 开启时，`DeferredToolFilterMiddleware` 在 **`wrap_model_call`** 从绑给模型的 `tools` 中移除 deferred MCP schema（执行不变）

---

## 设置步骤

1. 将 `extensions_config.example.json` 复制到项目根目录下的 `extensions_config.json`。
   ```bash
   # 复制示例配置
   cp extensions_config.example.json extensions_config.json
   ```
   
2. 通过将 `"enabled"` 设置为 `true` 来启用所需的 MCP 服务器或技能。
3. 根据需要配置每个服务器的命令、参数和环境变量。
4. 保存配置后，运行时会在 **下一次加载 MCP 工具时** 自动拾取变更（**通常无需重启**）：
   - 直接编辑 `extensions_config.json` 后，Harness 的 **`get_cached_mcp_tools`** 会对比配置 **mtime** 并失效缓存；
   - 通过 Gateway **`PUT /api/mcp/config`** 写盘并 **`reload_extensions_config`**，效果相同。

## OAuth 支持（HTTP/SSE MCP 服务器）

对于 `http` 和 `sse` 类型的 MCP 服务器，DeerFlow 支持 OAuth 令牌获取和自动令牌刷新。

- 支持的授权类型：`client_credentials`、`refresh_token`
- 在 `extensions_config.json` 中为每个服务器配置 `oauth` 块
- 密钥应通过环境变量提供（例如：`$MCP_OAUTH_CLIENT_SECRET`）

示例：

```json
{
   "mcpServers": {
      "secure-http-server": {
         "enabled": true,
         "type": "http",
         "url": "https://api.example.com/mcp",
         "oauth": {
            "enabled": true,
            "token_url": "https://auth.example.com/oauth/token",
            "grant_type": "client_credentials",
            "client_id": "$MCP_OAUTH_CLIENT_ID",
            "client_secret": "$MCP_OAUTH_CLIENT_SECRET",
            "scope": "mcp.read",
            "refresh_skew_seconds": 60
         }
      }
   }
}
```

## 工作原理

MCP 服务器暴露的工具会在运行时自动发现并集成到 DeerFlow 的 agent 系统中。一旦启用，这些工具即可供 agent 使用，无需额外的代码更改。

### 与 `tool_search` / deferred 加载

当 `config.yaml` 中 **`tool_search.enabled: true`** 时，MCP 工具 schema **不会** 在首轮全部绑定给模型；模型需先调用内置 **`tool_search`** 发现工具，晋升状态写入 **`ThreadState.promoted`**。**`DeferredToolFilterMiddleware`** 在 **`wrap_model_call`** 阶段隐藏尚未晋升的 deferred schema（ToolNode 仍保留完整工具列表供执行）。

### 运行时更新（无需重启）

| 方式 | 行为 |
|------|------|
| 编辑 `extensions_config.json` | 下次 agent 加载工具时按 **mtime** 重载 MCP 缓存 |
| `PUT /api/mcp/config`（Gateway） | 写盘 + reload 配置缓存 + 重置 MCP 工具缓存 |
| 手动 | 调用 `reset_mcp_tools_cache()`（测试/排障） |

## 示例能力

MCP 服务器可以提供对以下资源的访问：

- **文件系统**
- **数据库**（例如 PostgreSQL）
- **外部 API**（例如 GitHub、Brave Search）
- **浏览器自动化**（例如 Puppeteer）
- **自定义 MCP 服务器实现**

## 了解更多

有关模型上下文协议的详细文档，请访问：  
https://modelcontextprotocol.io
