# OpenHands 文档覆盖与改动记录（2026）

## 1. 核对范围

本轮只修改 `docs/openhands/` 文档，源码只读核对 `OpenHands` Canvas 与 `software-agent-sdk` Agent Server/SDK。原有文档不删除；旧版 Python App Server 内容保留并在新文档中标注历史/当前边界。

## 2. 证据矩阵

| ID | 源码证据 | 本轮结论 |
|---|---|---|
| A1 | `backend-registry/*` | local/cloud/org/health/revision 是产品级后端身份 |
| A2 | `agent-server-adapter.ts` | UI 配置编译为 StartConversationRequest |
| A3 | `event-service.api.ts` | history/search/confirmation 与 live runtime 分层 |
| A4 | `conversation-websocket-context.tsx` | 主/规划 socket、held message、typed client fallback |
| A5 | `session-seq-cursor.ts` + server `session_socket.py` | cursor 按无缺口序列恢复，服务端先订阅再 replay |
| A6 | `use-event-store.ts` / WS hooks | durable event、delta、错误与 UI projection 分离 |
| A7 | `config/defaults.json` + dev scripts | 版本、端口、ingress、Automation 的运行时契约 |

## 3. 现有内容与补充

- 保留旧版架构、实体和自托管内容，避免丢失历史决策。
- 新增 `SOURCE_DEEP_DIVE_2026.md`：当前 Canvas 全景、类/模块职责、事件时序、游标算法、云/本地双路径、启动拓扑和后端缺口。
- 新增多张 Mermaid 架构图、时序图、状态图和流程图。
- 追加导航与当前源码校准，避免把旧 App Server 误认成当前 Canvas 唯一入口。

## 4. 真正缺口

重点不是“没有 WebSocket/Lease/Replay”，这些能力已经存在；缺口在 schema version、跨后端缓存隔离、held message 生命周期、lease 与外部副作用关联、双 host 故障模型、优雅关闭和端到端送达确认。

另定位到一个具体异常路径：Agent Server 初次订阅注册后非 TimeoutError 未回滚，可能占用订阅容量；详见 [SDK 深读 §13](../openhands-sdk/SOURCE_DEEP_DIVE_2026.md#13-静态可定位的订阅异常清理缺口)。此为静态分析，不声称已运行复现。

## 5. 验证与限制

- `session-seq-cursor.test.ts`：**6 tests passed**。
- SDK Python 定向测试未执行：当前 SDK `.venv` 没有安装 `pytest`，未安装新依赖。
- Canvas 首次 Vitest 尝试因沙箱禁止写 `node_modules/.vite-temp` 失败；在获得一次性执行权限后，游标测试通过。
- Mermaid 未在本轮渲染器中逐图渲染；文档只确认代码围栏和源码路径，不能宣称视觉渲染已验收。
- 未运行真实 LLM、Cloud、MCP、ACP、Docker 或生产 WebSocket。

### 最终静态验证记录

- 10 份原始应用文档逐字节保留为现文件前缀，没有改写或移除原内容。
- 新增相对文件链接本地路径存在；代码围栏配对与 `git diff --check` 通过。
- Canvas 与 SDK 兄弟仓库的既有业务源码 Git 状态保持不变；没有恢复已有的 docs 删除或 package-lock 修改。
