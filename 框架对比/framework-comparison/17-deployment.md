# 部署 · 远端 · 多实例

> **设计导读** · Tier 1 完整矩阵与拓扑：[_archive/17-deployment.md](./_archive/17-deployment.md)  
> **关联**：[02-harness-blueprint](./02-harness-blueprint.md) · [09-channels](./09-channels.md) · [06-memory](./06-memory.md)

---

## 1. 三个问题不要混谈

| 问题 | 问什么 | 典型误判 |
|------|--------|----------|
| **远端部署** | Agent 进程在哪 | 本地脚本 ≠ 服务 |
| **多实例** | 多副本扛流量 | 副本 + 本地 SQLite → 失忆 |
| **多用户并发** | 多 session 同时跑 | 多线程 ≠ 隔离 |

```text
远端部署  →  Gateway/Agent 在机房
多实例    →  外置 Session + 无状态 Worker
多用户    →  session_key + 并发语义（14）
```

---

## 2. 部署形态（D14）

| 代码 | 形态 | 代表 |
|------|------|------|
| **P0** | 库/脚本 | smolagents |
| **P1** | 本地 CLI/TUI | Pi、deepagents-code |
| **P2** | 本地 Gateway | nanobot 单机 |
| **P3** | 远端 Gateway | deer-flow、ohmo |
| **P4** | 托管 Agent API | LangGraph Platform |
| **P5** | 控制面+执行面 | OpenHands、K8s 沙箱 |

---

## 3. Tier 1 速览

| 项目 | 远端 | 多实例 | Session 外置 | 并发模型 |
|------|------|--------|--------------|----------|
| deer-flow | ✅ Gateway | ✅ Postgres | 必须 PG | IM reject |
| OpenHarness/ohmo | ✅ gateway | ⚠️ 自建共享 | 文件/DB | RuntimePool |
| nanobot | ✅ | ⚠️ | JSONL | session 串行 |
| Codex | ✅ 远端 CLI | ✅ | Rollout B | 按 client |
| OpenHands | ✅ agent-server | ✅ FileStore | 事件存储 | 会话 Lease |
| deepagents | 自托管 | 依 checkpointer | PG 可选 | 调用方 |
| OpenManus | ❌ | ❌ | 内存 | 单用户 |

---

## 4. Codex 式远端 CLI（参考）

```mermaid
flowchart LR
    CLI["薄 CLI 客户端"] --> GW["远端 Gateway"]
    GW --> POOL["Session / Rollout 池"]
    POOL --> WORK["Worker Loop"]
    WORK --> SB["远端沙箱"]
```

| 设计点 | 说明 |
|--------|------|
| **认证在 Gateway** | CLI 仅持 token |
| **session 粘性或外置** | 多副本要共享真源 |
| **执行在远端** | 本机不持 repo |

---

## 5. 档位 B 检查清单

- [ ] session_key 与串行语义定义  
- [ ] Session 存 PG/Redis/共享 FS  
- [ ] Gateway 无状态或可恢复  
- [ ] 沙箱与 Loop 可分机  
- [ ] 观测：trace 含 session_id  
- [ ] 密钥在 L1，不进 L  

---

## 6. 设计法则

1. **先外置真源再水平扩展**。  
2. **Gateway 与 Worker 可拆** — P5 可演进。  
3. **同 session 不跨副本乱漂** — sticky 或分布式锁。  
4. **远端 ≠ 多租户** — 还需 authZ。  
5. **部署形态写进架构图** — 避免「能跑 demo」当生产。

---

## 7. 深潜

逐项目拓扑、环境变量、K8s 示例 → [_archive/17-deployment.md](./_archive/17-deployment.md)
