# Agent Canvas — Testing Matrix

**Priority key:** P0 = must pass before any release · P1 = must pass before GA · P2 = best-effort

---

## Install × OS × Agent

Each cell = smoke test: install → onboard → start conversation → agent replies.

| | **macOS** | **Linux** | **Windows** |
|---|:---:|:---:|:---:|
| **npm — OpenHands** | ☐ | ☐ | ☐ |
| **npm — Claude Code** | ☐ | ☐ | ☐ |
| **npm — Codex** | ☐ | ☐ | ☐ |
| **npm — Gemini CLI** | ☐ | ☐ | ☐ |
| **npm — Custom ACP** | ☐ | ☐ | ☐ |
| **Docker — OpenHands** | ☐ | ☐ | ☐ |
| **Docker — Claude Code** | ☐ | ☐ | ☐ |
| **Docker — Codex** | ☐ | ☐ | ☐ |
| **Docker — Gemini CLI** | ☐ | ☐ | ☐ |
| **Docker — Custom ACP** | ☐ | ☐ | ☐ |

---

## Automations × Install × Agent

Requires full stack (automation backend running).

| | **npm** | **Docker** |
|---|:---:|:---:|
| **OpenHands** | ✅ P0 | ✅ P0 |
| **Claude Code** | ✅ P1 | ✅ P1 |
| **Codex** | ✅ P1 | ✅ P1 |
| **Gemini CLI** | ✅ P2 | ✅ P2 |

Each cell = create automation → dispatch run → run reaches COMPLETED → conversation link works.

---

## Auth Modes

| | **npm** | **Docker** |
|---|:---:|:---:|
| **Local (auto-generated key)** | ✅ P0 | ✅ P0 |
| **Public (`--public` + user key)** | ✅ P1 | ✅ P1 |

---

## Feature Checklist

### npm

| Feature | OpenHands | Claude Code | Codex | Gemini CLI |
|---|:---:|:---:|:---:|:---:|
| Onboarding | ☐ | ☐ | ☐ | ☐ |
| Conversation — start, resume, history | ☐ | ☐ | ☐ | ☐ |
| Terminal tool | ☐ | ☐ | ☐ | ☐ |
| File editor tool | ☐ | ☐ | ☐ | ☐ |
| Browser tool | ☐ | ☐ | ☐ | ☐ |
| LLM profiles — create / switch | ☐ | — | — | — |
| Secrets — add / delete / forwarded | ☐ | ☐ | ☐ | ☐ |
| Automations — create, dispatch, COMPLETED | ☐ | ☐ | ☐ | ☐ |
| Files tab + Changes/diff tab | ☐ | ☐ | ☐ | ☐ |
| MCP server install | ☐ | ☐ | ☐ | ☐ |
| Image upload in chat | ☐ | ☐ | ☐ | ☐ |
| Key rotation | ☐ | ☐ | ☐ | ☐ |

### Docker

| Feature | OpenHands | Claude Code | Codex | Gemini CLI |
|---|:---:|:---:|:---:|:---:|
| Onboarding | ☐ | ☐ | ☐ | ☐ |
| Conversation — start, resume, history | ☐ | ☐ | ☐ | ☐ |
| Terminal tool | ☐ | ☐ | ☐ | ☐ |
| File editor tool | ☐ | ☐ | ☐ | ☐ |
| Browser tool | ☐ | ☐ | ☐ | ☐ |
| LLM profiles — create / switch | ☐ | — | — | — |
| Secrets — add / delete / forwarded | ☐ | ☐ | ☐ | ☐ |
| Automations — create, dispatch, COMPLETED | ☐ | ☐ | ☐ | ☐ |
| Files tab + Changes/diff tab | ☐ | ☐ | ☐ | ☐ |
| MCP server install | ☐ | ☐ | ☐ | ☐ |
| Image upload in chat | ☐ | ☐ | ☐ | ☐ |
| Key rotation | ☐ | ☐ | ☐ | ☐ |

---

## Automated Coverage

| Suite | Install | OS | Agents | Automations |
|---|---|---|---|---|
| `vitest` (unit) | — | Linux | — | partial |
| `test:e2e:mock-llm` | npm | Linux | OpenHands, ACP (mock) | ✅ full |
| `test:e2e:mock-llm:docker` | Docker | Linux | OpenHands, ACP (mock) | ✅ full |
| `test:e2e:live` | npm | Linux | OpenHands | ❌ |

**Not yet covered by CI:** real ACP credentials (Claude Code / Codex / Gemini), macOS, public auth mode, subscription login paths, Windows.


---

## 追加：源码驱动的恢复与身份测试矩阵

[源码证据索引](SOURCE_DEEP_DIVE_2026.md) · [本轮实际结果](COVERAGE_AND_CHANGES.md)

| 场景 | 不变量 | 层级 |
|---|---|---|
| seq 乱序/重复/缺口 | cursor 不因最高 seq 跳过未到达事件 | unit |
| 主 socket 与 planning 切换 | 游标/消息不串会话 | context integration |
| cloud 无 runtime URL | held 而非向 parent 错投 | unit + integration |
| REST fallback 投递 | queued 与 delivered/finished 区分 | client contract |
| backend/org/key 切换 | 缓存和凭据无跨身份泄漏 | integration |
| subscribe/replay 并发写 | 历史/live 边界无遗漏 | server integration |
| worker 等待者取消 | permit 不早于真实执行结束释放 | server unit |
| lease takeover | 旧 generation 受保护写失败 | server integration |
| 慢 subscriber | 有界内存 + 可 replay 恢复 | stress |
| 版本不满足/版本未知 | 拒绝启动并给可诊断错误 | compatibility |

本轮仅执行 Canvas seq cursor 的 6 项单元测试并通过；其它条目是建议矩阵，不是已通过报告。
