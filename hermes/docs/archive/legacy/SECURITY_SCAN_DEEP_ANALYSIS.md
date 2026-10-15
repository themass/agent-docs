# Hermes 安全扫描与纵深防御

<!-- legacy-review:start -->
> **2026-10-15 校订导航**：输入从安装、加载到执行，分别经过哪些防线。\
> **核对范围**：增加当前命令 guard 导航与适用范围；旧 scanner 正则、信任名单、行号未全量重新认证。\
> **适用基线**：本地源码 `60d00c5633ad`；不是最新发布版本声明。原稿版本、行号、性能数字与长代码块若未在校订范围内，仍按历史示例阅读。
> **先读当前结论**：[当前实现导读](CURRENT_IMPLEMENTATION.md#current-approval) · **现行分卷**：[08-security-and-governance.md](../../volumes/08-security-and-governance.md) · [具体改动与未验证项](REVIEW_AND_CHANGES.md) · [返回全目录](README.md)

<!-- legacy-review:end -->
<a id="目录"></a>
## 目录

<!-- visible-toc:start -->
- [1. 架构概览](#section-1)
  - [1.1 三层防御体系](#section-1-1)
  - [1.2 核心组件职责](#section-1-2)
- [2. 纵深防御全景：Agent、工具与运行环境的检查边界](#section-2)
  - [2.1 安全全景图](#section-2-1)
  - [2.2 安全维度总览](#section-2-2)
  - [2.3 Agent Loop 中的安全触发时序](#section-2-3)
  - [2.4 关键安全边界详解](#section-2-4)
  - [2.5 容器环境豁免](#section-2-5)
  - [2.6 设计哲学](#section-2-6)
- [3. 第一层：Skills Guard（技能安装前扫描）](#section-3)
  - [3.1 设计哲学](#section-3-1)
  - [3.2 扫描流程详解](#section-3-2)
  - [3.3 策略决策矩阵](#section-3-3)
  - [3.4 集成到安装流程](#section-3-4)
- [4. 第二层：Context Scanner（上下文文件加载时扫描）](#section-4)
  - [4.1 设计目标](#section-4-1)
  - [4.2 扫描实现](#section-4-2)
  - [4.3 调用链路](#section-4-3)
  - [4.4 阻断效果](#section-4-4)
- [5. 第三层：Runtime Injection Detection（运行时注入检测）](#section-5)
  - [5.1 设计理念](#section-5-1)
  - [5.2 实现细节](#section-5-2)
  - [5.3 与其他层的对比](#section-5-3)
- [6. 威胁模式库详解](#section-6)
  - [6.1 模式统计](#section-6-1)
  - [6.2 模式质量评估](#section-6-2)
- [7. 信任模型与策略决策](#section-7)
  - [7.1 信任级别设计](#section-7-1)
  - [7.2 策略合理性分析](#section-7-2)
  - [7.3 决策矩阵评估](#section-7-3)
- [8. 关键代码路径追踪](#section-8)
  - [8.1 外部技能安装流程](#section-8-1)
  - [8.2 Agent 创建技能流程](#section-8-2)
  - [8.3 Prompt 构建流程](#section-8-3)
- [9. 安全设计原则评估](#section-9)
  - [9.1 符合的安全原则](#section-9-1)
  - [9.2 潜在弱点](#section-9-2)
  - [9.3 与其他项目的对比](#section-9-3)
- [10. 最佳实践建议](#section-10)
  - [10.1 对于技能开发者](#section-10-1)
  - [10.2 对于用户](#section-10-2)
  - [10.3 对于安全研究人员](#section-10-3)
- [11. 未来改进方向](#section-11)
  - [11.1 短期改进（1-3 个月）](#section-11-1)
  - [11.2 中期改进（3-6 个月）](#section-11-2)
  - [11.3 长期愿景（6-12 个月）](#section-11-3)
- [12. 总结](#section-12)
  - [12.1 核心优势](#section-12-1)
  - [12.2 关键设计决策](#section-12-2)
  - [12.3 适用场景](#section-12-3)
  - [12.4 最终评价](#section-12-4)
- [13. 附录](#section-13)
  - [13.1 A. 完整的威胁模式列表](#section-13-1)
  - [13.2 B. 配置文件示例](#section-13-2)
  - [13.3 C. 常见问题解答](#section-13-3)
  - [13.4 D. 参考文献](#section-13-4)
- [14. 后台学习的安全边界（详见 Skills）](#section-14)
<!-- visible-toc:end -->




> **原稿文档状态（历史标签）**: 三层安全扫描与纵深防御；Background Review 完整设计已移至 Skills 篇\
> **原稿版本核对（历史）**: 工作区 `hermes-dev/hermes-agent` · `__release_date__` 2026.9.24（见 [VERSION_HISTORY.md](VERSION_HISTORY.md)）\
> **导航**: [ARCHITECTURE.md](ARCHITECTURE.md) · [AGENT_LOOP_ARCHITECTURE.md](AGENT_LOOP_ARCHITECTURE.md) · [CATALOG.md](../../CATALOG.md)


> **原稿版本锚点（历史）**: 0.19.0 · **核对**: 2026-07-22 · [DOC_MAINTENANCE.md](DOC_MAINTENANCE.md)\
> **文档状态**: Deep dive / security analysis\
> **版本**: v1.0\
> **创建时间**: 2026-05-13\
> **主题**: Skills Guard、Context Scanner、Injection Detection 三层防护体系详解

---

<a id="📋-目录"></a>

<a id="1-架构概览"></a>
<a id="section-1"></a>
## 1. 架构概览

<a id="11-三层防御体系"></a>
<a id="section-1-1"></a>
### 1.1 三层防御体系

Hermes Agent 采用了**纵深防御（Defense in Depth）**策略，在三个关键时间点执行安全检查：

```mermaid
graph TB
    subgraph "Layer 1: Pre-Installation Scan"
        A[External Skill Download] --> B[skills_guard.py scan_skill]
        B --> C{Trust Level?}
        C -->|builtin| D[Skip Scan - Trusted]
        C -->|trusted/community| E[Regex Pattern Matching]
        E --> F[Structural Checks]
        F --> G[Invisible Unicode Detection]
        G --> H{Verdict?}
        H -->|safe| I[Allow Install]
        H -->|caution| J{Policy Decision}
        H -->|dangerous| K{Policy Decision}
    end
    
    subgraph "Layer 2: Context Loading Scan"
        L[Load AGENTS.md/HERMES.md] --> M[_scan_context_content]
        M --> N[Check Threat Patterns]
        N --> O[Check Invisible Chars]
        O --> P{Blocked?}
        P -->|Yes| Q[Return BLOCKED Message]
        P -->|No| R[Inject into Prompt]
    end
    
    subgraph "Layer 3: Runtime Detection"
        S[Skill View/Load] --> T[_INJECTION_PATTERNS Check]
        T --> U{Pattern Found?}
        U -->|Yes| V[Log Warning + Continue]
        U -->|No| W[Normal Execution]
    end
    
    I --> X[Skill Installed]
    J -->|trusted+caution| I
    J -->|community+caution| Y[Block Install]
    K -->|trusted+dangerous| Y
    K -->|community+dangerous| Y
    Q --> Z[Prompt Protected]
    R --> AA[Agent Receives Context]
    V --> BB[Monitoring Alert]
    W --> CC[Normal Operation]
```

<a id="12-核心组件职责"></a>
<a id="section-1-2"></a>
### 1.2 核心组件职责

| 组件 | 文件路径 | 触发时机 | 阻断能力 |
|------|---------|---------|---------|
| **Skills Guard** | `tools/skills_guard.py` | 外部技能安装前 | ✅ 完全阻断 |
| **Context Scanner** | `agent/prompt_builder.py:_scan_context_content` | 加载项目上下文文件时 | ✅ 完全阻断 |
| **Runtime Detector** | `tools/skills_tool.py:_INJECTION_PATTERNS` | 查看/加载技能时 | ⚠️ 仅告警 |

---

<a id="defense-boundaries"></a>
<a id="纵深防御全景agent工具与运行环境的检查边界"></a>
<a id="section-2"></a>
## 2. 纵深防御全景：Agent、工具与运行环境的检查边界

> **主题归位**：本节从 `AGENT_LOOP_ARCHITECTURE.md` 的「5.5 安全与权限体系（12 维度纵深防御）」迁入；保留原有图表、示例和讨论。这是原稿的分层设计视角；其中审批执行顺序以 [当前审批链路](CURRENT_IMPLEMENTATION.md#current-approval) 与 [HITL 专篇](HITL_APPROVAL_FLOW.md) 为准，不以“12 维度”顺序推断调用顺序。

> 安全不是「统一网关」，而是 **12 个维度的分布式纵深防御** — 每个攻击面有专门的检查逻辑。\
> （原 `AIAgent_ARCHITECTURE.md` §8c 已并入本节，勿再开平行文档。）

<a id="550-安全全景图"></a>
<a id="section-2-1"></a>
### 2.1 安全全景图

```
                        ┌─────────────────────────────────────┐
                        │     Dimension 1: Agent Loop 控制     │
                        │  IterationBudget / max_iterations    │
                        │  破坏性命令禁止并行执行                │
                        └──────────────┬──────────────────────┘
                                       ↓
┌──────────────────────────────────────────────────────────────────────┐
│                   Dimension 2: 公共 Pre-execution                    │
│  ① Plugin Hook: get_pre_tool_call_block_message()                    │
│  ② Tool Loop Guardrail: before_call() → 循环失败检测                  │
└──────────────────────────┬───────────────────────────────────────────┘
                           ↓
          ┌────────────────┼────────────────┬──────────────────┐
          ↓                ↓                ↓                  ↓
  ┌───────────────┐ ┌───────────────┐ ┌──────────────┐ ┌────────────────┐
  │ Dim 3: 终端    │ │ Dim 4: 文件    │ │ Dim 5: 网络   │ │ Dim 6: MCP     │
  │ Command Guards │ │ 路径+写入安全  │ │ URL/SSRF 防护 │ │ 恶意软件+注入   │
  └───────────────┘ └───────────────┘ └──────────────┘ └────────────────┘
          ↓                ↓                ↓                  ↓
  ┌───────────────┐ ┌───────────────┐ ┌──────────────┐ ┌────────────────┐
  │ Dim 7: 桌面    │ │ Dim 8: 沙箱   │ │ Dim 9: Skills │ │ Dim 10: Cron   │
  │ Computer-Use  │ │ Env 清洗+隔离  │ │ Guard 静态扫描│ │ 注入+路径围栏   │
  └───────────────┘ └───────────────┘ └──────────────┘ └────────────────┘
                           ↓
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓
  ┌───────────────┐ ┌───────────────┐ ┌──────────────┐
  │ Dim 11: 输出   │ │ Dim 12: Prompt│ │ 容器环境豁免   │
  │ 脱敏+围栏      │ │ 注入防护      │ │ Docker/Modal  │
  └───────────────┘ └───────────────┘ └──────────────┘
                           ↓
                  ┌────────────────────┐
                  │ Provider Guardrails │
                  └────────────────────┘
```

<a id="551-安全维度总览"></a>
<a id="section-2-2"></a>
### 2.2 安全维度总览

| 维度 | 防御对象 | 关键文件 | 可否绕过 |
|------|---------|---------|---------|
| **D1: Agent Loop 控制** | 无限循环 / 并行竞态 | `run_agent.py` (`IterationBudget`, `_is_destructive_command`) | 硬上限不可绕过 |
| **D2: 公共 Pre/Post** | 循环失败 / 插件拦截 | `run_agent.py` / `agent/tool_guardrails.py` | 插件可选 |
| **D3: 终端命令** | 危险 shell 命令 | `tools/approval.py` (8 层审批链) | Hardline/Sudo 不可绕过 |
| **D4: 文件操作** | 路径穿越 / 敏感写入 | `tools/path_security.py` / `agent/file_safety.py` / `tools/file_tools.py` | 拒绝列表不可绕过 |
| **D5: 网络 URL** | SSRF / 私有 IP / 元数据 | `tools/url_safety.py` / `tools/website_policy.py` | 云元数据始终拦截 |
| **D6: MCP** | 恶意包 / 描述注入 | `tools/osv_check.py` / `tools/mcp_tool.py` | OSV fail-open |
| **D7: Computer-Use** | 危险按键 / 命令输入 | `tools/computer_use/tool.py` | 键盘组合不可绕过 |
| **D8: 子进程沙箱** | 凭证泄露 / Env 逃逸 | `tools/environments/local.py` / `tools/env_passthrough.py` / `tools/code_execution_tool.py` | Provider 凭证不可透传 |
| **D9: Skills 生命周期** | 恶意 Skill 安装 | `tools/skills_guard.py` / `tools/skill_manager_tool.py` | community → caution 即 block |
| **D10: Cron** | 定时任务注入 / 越界 | `cron/scheduler.py` / `cron/jobs.py` | 注入检测 hard block |
| **D11: 输出脱敏** | 凭证/token 泄露 | `agent/redact.py` / `agent/memory_manager.py` | 始终生效 |
| **D12: Prompt 注入** | 上下文文件 / MCP 描述 | `run_agent.py` / `tools/mcp_tool.py` / `cron/scheduler.py` | 上下文文件 hard block |

<a id="552-agent-loop-中的安全触发时序"></a>
<a id="section-2-3"></a>
### 2.3 Agent Loop 中的安全触发时序

```
每轮迭代开始
    │
    ├─ [D1] IterationBudget.consume() → 超限则终止
    │
    ├─ [D12] _build_system_prompt() → 上下文文件注入扫描（首次/重建时）
    │
    ├─ API 调用（Provider Guardrails: Bedrock guardrailConfig）
    │
    ├─ LLM 返回 tool_calls
    │   │
    │   ├─ [D1] _should_parallelize_tool_batch()
    │   │   └─ 含破坏性命令? → 禁止并行，串行执行
    │   │
    │   └─ 对每个 tool_call:
    │       │
    │       ├─── Pre-execution ──────────────────────────────────────
    │       │ [D2] Plugin: get_pre_tool_call_block_message()
    │       │ [D2] Guardrail: before_call() → 循环检测
    │       │
    │       │ 按工具类型分流:
    │       │ ├─ terminal → [D3] check_all_command_guards (8层)
    │       │ │             [D3] _validate_workdir()
    │       │ ├─ read_file → [D4] 设备文件 + Hub 缓存 + 二进制检查
    │       │ ├─ write/patch → [D4] 写入拒绝列表 + Jail + 敏感路径
    │       │ ├─ web/vision → [D5] is_safe_url() + check_website_access()
    │       │ ├─ MCP tools → [D6] OSV check (启动时) + 描述扫描 (注册时)
    │       │ ├─ computer_use → [D7] 键盘组合 + 输入文本拦截
    │       │ ├─ execute_code → [D8] Env 清洗 + 受限工具集
    │       │ ├─ skill_manage → [D9] Skills Guard 扫描 + 路径检查
    │       │ └─ cron tools → [D10] prompt 注入 + 路径围栏
    │       │
    │       ├─── Execution ──────────────────────────────────────────
    │       │ 工具执行
    │       │
    │       ├─── Post-execution ─────────────────────────────────────
    │       │ [D2] Guardrail: after_call() → 失败累计
    │       │ [D11] redact_sensitive_text() (execute_code/cron 输出)
    │       │ [D11] StreamingContextScrubber (Memory 围栏)
    │       │
    │       └─── 结果返回 → 下一个 tool_call 或下一轮迭代
    │
    └─ [D8] 子进程 env 始终清洗 (每次 terminal/execute_code 调用)
```

<a id="553-关键安全边界详解"></a>
<a id="section-2-4"></a>
### 2.4 关键安全边界详解

<a id="d3-终端-8-层审批链"></a>
<a id="section-2-4-1"></a>
#### 2.4.1 D3: 终端 8 层审批链

```
① Hardline → rm -rf /, shutdown, fork bomb         【绝对不可绕过】
② Sudo stdin → sudo -S 密码猜测                     【绝对不可绕过】
③ YOLO/mode=off → 开发者主动跳过
④ Tirith → OPA 策略引擎自定义规则
⑤ DANGEROUS_PATTERNS → 47 条正则
⑥ 白名单 → 永久/会话级
⑦ Smart Approval → 辅助 LLM
⑧ Interactive Approval → CLI 用户确认
```

<a id="d4-文件写入拒绝列表agentfile_safetypy"></a>
<a id="section-2-4-2"></a>
#### 2.4.2 D4: 文件写入拒绝列表（`agent/file_safety.py`）

**精确路径** (16 个): `~/.ssh/id_rsa`, `~/.ssh/authorized_keys`, `~/.hermes/.env`, `~/.bashrc`, `~/.zshrc`, `/etc/shadow`, `/etc/passwd`, `/etc/sudoers` 等

**前缀拒绝** (9 个目录): `~/.ssh/`, `~/.aws/`, `~/.gnupg/`, `~/.kube/`, `~/.docker/`, `~/.azure/`, `~/.config/gh/`, `/etc/sudoers.d/`, `/etc/systemd/`

**写入 Jail**: `HERMES_WRITE_SAFE_ROOT` 设置后，所有写操作必须在此根目录下

<a id="d8-凭证隔离设计"></a>
<a id="section-2-4-3"></a>
#### 2.4.3 D8: 凭证隔离设计

```
主进程 (持有所有 API key)
    │
    ├─ terminal → _sanitize_subprocess_env() 移除所有 Provider key
    │
    ├─ execute_code → 同上 + SANDBOX_ALLOWED_TOOLS 交集 + redact 输出
    │
    └─ env_passthrough.register() → 拒绝注册 Hermes Provider 凭证
                                     (GHSA-rhgp-j443-p4rf 修复)
```

<a id="d9-skills-信任分级"></a>
<a id="section-2-4-4"></a>
#### 2.4.4 D9: Skills 信任分级

| 来源 | safe | caution | dangerous |
|------|------|---------|-----------|
| `builtin` | allow | allow | allow |
| `trusted` (openai/anthropics) | allow | allow | **block** |
| `community` | allow | **block** | **block** |
| `agent-created` | allow | allow | **ask** |

<a id="554-容器环境豁免"></a>
<a id="section-2-5"></a>
### 2.5 容器环境豁免

```python
# tools/approval.py:L1028
if env_type in {"docker", "singularity", "modal", "daytona", "vercel_sandbox"}:
    return {"approved": True}  # 容器天然隔离，跳过终端审批
```

豁免仅限 **D3 终端命令审批**。D4 文件安全、D5 URL 安全、D6 MCP 扫描等其他维度在容器内依然生效。

<a id="555-设计哲学"></a>
<a id="section-2-6"></a>
### 2.6 设计哲学

| 设计选择 | 原因 |
|---------|------|
| **攻击面特化** | 命令（正则+审批）、文件（路径+拒绝列表）、URL（IP 解析+黑名单）— 语义完全不同 |
| **不可绕过层** | Hardline、Sudo stdin、Workdir、写入拒绝列表、设备文件、键盘组合 — 任何配置都拦截 |
| **Fail-open vs Fail-closed** | OSV 恶意软件 fail-open（网络不可用不阻塞）；文件写入拒绝 fail-closed（宁可误拦） |
| **凭证主进程隔离** | API key 只在主进程，子进程 env 清洗，Skill 不可注册 Provider 凭证透传 |
| **分层脱敏** | 工具输出 → `redact`；Memory → 围栏标签；日志 → `RedactingFormatter`；Cron → stdout 脱敏 |
| **线程安全** | Approval 回调 `threading.local` 隔离；`IterationBudget` 线程安全计数 |

---

<a id="2-第一层skills-guard技能安装前扫描"></a>
<a id="section-3"></a>
## 3. 第一层：Skills Guard（技能安装前扫描）

<a id="21-设计哲学"></a>
<a id="section-3-1"></a>
### 3.1 设计哲学

**核心思想**：所有来自外部的技能（非内置）在安装前必须经过静态分析扫描，基于**信任级别**和**扫描结果**的二维决策矩阵决定是否允许安装。

<a id="22-扫描流程详解"></a>
<a id="section-3-2"></a>
### 3.2 扫描流程详解

<a id="步骤-1-信任级别解析"></a>
<a id="section-3-2-1"></a>
#### 3.2.1 步骤 1: 信任级别解析

```python
# tools/skills_guard.py:884-908

def _resolve_trust_level(source: str) -> str:
    """Map a source identifier to a trust level."""
    
    # 1. Agent-created skills (self-generated by the agent)
    if source == "agent-created":
        return "agent-created"
    
    # 2. Official optional skills shipped with the repo
    if source.startswith("official/") or source == "official":
        return "builtin"
    
    # 3. Trusted third-party repos
    TRUSTED_REPOS = {"openai/skills", "anthropics/skills"}
    for trusted in TRUSTED_REPOS:
        if source.startswith(trusted) or source == trusted:
            return "trusted"
    
    # 4. Everything else
    return "community"
```

**信任级别分类**：

| 级别 | 来源示例 | 扫描策略 | 理由 |
|------|---------|---------|------|
| `builtin` | `official/software-development` | ❌ 跳过扫描 | 官方维护，代码审查通过 |
| `trusted` | `openai/skills/web-research` | ✅ 扫描但宽松 | 知名厂商，有一定信誉 |
| `community` | `github.com/user/skill-x` | ✅ 扫描且严格 | 未知来源，零信任 |
| `agent-created` | Agent 自己生成的技能 | ✅ 扫描（可选） | 可能受 prompt injection 影响 |

<a id="步骤-2-结构性检查"></a>
<a id="section-3-2-2"></a>
#### 3.2.2 步骤 2: 结构性检查

```python
# tools/skills_guard.py:738-852

def _check_structure(skill_dir: Path) -> List[Finding]:
    """检查技能目录的结构异常"""
    
    findings = []
    file_count = 0
    total_size = 0
    
    for f in skill_dir.rglob("*"):
        if not f.is_file() and not f.is_symlink():
            continue
        
        rel = str(f.relative_to(skill_dir))
        file_count += 1
        
        # ── 检查 1: Symlink 逃逸 ──
        if f.is_symlink():
            try:
                resolved = f.resolve()
                if not resolved.is_relative_to(skill_dir.resolve()):
                    findings.append(Finding(
                        pattern_id="symlink_escape",
                        severity="critical",
                        category="traversal",
                        file=rel,
                        line=0,
                        match=f"symlink -> {resolved}",
                        description="symlink points outside the skill directory",
                    ))
            except OSError:
                findings.append(Finding(
                    pattern_id="broken_symlink",
                    severity="medium",
                    category="traversal",
                    file=rel,
                    line=0,
                    match="broken symlink",
                    description="broken or circular symlink",
                ))
            continue
        
        # ── 检查 2: 文件大小限制 ──
        try:
            size = f.stat().st_size
            total_size += size
        except OSError:
            continue
        
        if size > MAX_SINGLE_FILE_KB * 1024:  # 256KB
            findings.append(Finding(
                pattern_id="oversized_file",
                severity="medium",
                category="structural",
                file=rel,
                line=0,
                match=f"{size // 1024}KB",
                description=f"file is {size // 1024}KB (limit: {MAX_SINGLE_FILE_KB}KB)",
            ))
        
        # ── 检查 3: 二进制文件检测 ──
        ext = f.suffix.lower()
        if ext in SUSPICIOUS_BINARY_EXTENSIONS:  # .exe, .dll, .so, etc.
            findings.append(Finding(
                pattern_id="binary_file",
                severity="critical",
                category="structural",
                file=rel,
                line=0,
                match=f"binary: {ext}",
                description=f"binary/executable file ({ext}) should not be in a skill",
            ))
        
        # ── 检查 4: 可执行权限异常 ──
        if ext not in {'.sh', '.bash', '.py', '.rb', '.pl'} and f.stat().st_mode & 0o111:
            findings.append(Finding(
                pattern_id="unexpected_executable",
                severity="medium",
                category="structural",
                file=rel,
                line=0,
                match="executable bit set",
                description="file has executable permission but is not a recognized script type",
            ))
    
    # ── 检查 5: 文件总数限制 ──
    if file_count > MAX_FILE_COUNT:  # 50 files
        findings.append(Finding(
            pattern_id="too_many_files",
            severity="medium",
            category="structural",
            file="(directory)",
            line=0,
            match=f"{file_count} files",
            description=f"skill has {file_count} files (limit: {MAX_FILE_COUNT})",
        ))
    
    # ── 检查 6: 总大小限制 ──
    if total_size > MAX_TOTAL_SIZE_KB * 1024:  # 1MB
        findings.append(Finding(
            pattern_id="oversized_skill",
            severity="high",
            category="structural",
            file="(directory)",
            line=0,
            match=f"{total_size // 1024}KB total",
            description=f"skill is {total_size // 1024}KB total (limit: {MAX_TOTAL_SIZE_KB}KB)",
        ))
    
    return findings
```

**结构限制参数**：

```python
MAX_FILE_COUNT = 50       # 技能不应有超过 50 个文件
MAX_TOTAL_SIZE_KB = 1024  # 总大小不超过 1MB
MAX_SINGLE_FILE_KB = 256  # 单个文件不超过 256KB
```

**检测逻辑**：
- ✅ **Symlink 逃逸**：防止通过符号链接访问技能目录外的文件
- ✅ **二进制文件**：技能应该是纯文本，二进制文件可能是恶意 payload
- ✅ **可执行权限**：非脚本文件设置可执行位是可疑行为
- ✅ **规模限制**：过大的技能可能包含隐藏内容或资源消耗攻击

<a id="步骤-3-正则模式匹配"></a>
<a id="section-3-2-3"></a>
#### 3.2.3 步骤 3: 正则模式匹配

这是最核心的部分，包含 **100+ 个威胁模式**，覆盖 8 大类攻击向量。

<a id="31-数据泄露exfiltration--18-个模式"></a>
<a id="section-3-2-3-1"></a>
##### 3.2.3.1 数据泄露（Exfiltration）- 18 个模式

```python
THREAT_PATTERNS = [
    # ── Shell 命令泄露秘密 ──
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)',
     "env_exfil_curl", "critical", "exfiltration",
     "curl command interpolating secret environment variable"),
    
    (r'wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)',
     "env_exfil_wget", "critical", "exfiltration",
     "wget command interpolating secret environment variable"),
    
    (r'fetch\s*\([^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|API)',
     "env_exfil_fetch", "critical", "exfiltration",
     "fetch() call interpolating secret environment variable"),
    
    # ── HTTP 库调用泄露 ──
    (r'httpx?\.(get|post|put|patch)\s*\([^\n]*(KEY|TOKEN|SECRET|PASSWORD)',
     "env_exfil_httpx", "critical", "exfiltration",
     "HTTP library call with secret variable"),
    
    (r'requests\.(get|post|put|patch)\s*\([^\n]*(KEY|TOKEN|SECRET|PASSWORD)',
     "env_exfil_requests", "critical", "exfiltration",
     "requests library call with secret variable"),
    
    # ── 读取凭证存储 ──
    (r'\$HOME/\.ssh|\~/\.ssh',
     "ssh_dir_access", "high", "exfiltration",
     "references user SSH directory"),
    
    (r'\$HOME/\.aws|\~/\.aws',
     "aws_dir_access", "high", "exfiltration",
     "references user AWS credentials directory"),
    
    (r'\$HOME/\.hermes/\.env|\~/\.hermes/\.env',
     "hermes_env_access", "critical", "exfiltration",
     "directly references Hermes secrets file"),
    
    (r'cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass|\.npmrc|\.pypirc)',
     "read_secrets_file", "critical", "exfiltration",
     "reads known secrets file"),
    
    # ── 程序化环境访问 ──
    (r'printenv|env\s*\|',
     "dump_all_env", "high", "exfiltration",
     "dumps all environment variables"),
    
    (r'os\.environ\b(?!\s*\.get\s*\(\s*["\']PATH)',
     "python_os_environ", "high", "exfiltration",
     "accesses os.environ (potential env dump)"),
    
    (r'os\.getenv\s*\(\s*[^\)]*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)',
     "python_getenv_secret", "critical", "exfiltration",
     "reads secret via os.getenv()"),
    
    # ── DNS 和数据暂存 ──
    (r'\b(dig|nslookup|host)\s+[^\n]*\$',
     "dns_exfil", "critical", "exfiltration",
     "DNS lookup with variable interpolation (possible DNS exfiltration)"),
    
    (r'>\s*/tmp/[^\s]*\s*&&\s*(curl|wget|nc|python)',
     "tmp_staging", "critical", "exfiltration",
     "writes to /tmp then exfiltrates"),
    
    # ── Markdown/链接基础泄露 ──
    (r'!\[.*\]\(https?://[^\)]*\$\{?',
     "md_image_exfil", "high", "exfiltration",
     "markdown image URL with variable interpolation (image-based exfil)"),
    
    (r'\[.*\]\(https?://[^\)]*\$\{?',
     "md_link_exfil", "high", "exfiltration",
     "markdown link with variable interpolation"),
]
```

**检测原理**：
- ✅ **环境变量插值**：检测 `$KEY`、`${TOKEN}` 等模式，防止秘密被发送到外部服务器
- ✅ **敏感目录访问**：监控 `.ssh`、`.aws`、`.hermes/.env` 等凭证存储位置
- ✅ **隐蔽通道**：DNS 查询、图片加载、Markdown 链接都可能成为数据泄露通道

<a id="32-prompt-injection提示注入--20-个模式"></a>
<a id="section-3-2-3-2"></a>
##### 3.2.3.2 Prompt Injection（提示注入）- 20 个模式

```python
THREAT_PATTERNS.extend([
    # ── 经典注入 ──
    (r'ignore\s+(?:\w+\s+)*(previous|all|above|prior)\s+instructions',
     "prompt_injection_ignore", "critical", "injection",
     "prompt injection: ignore previous instructions"),
    
    (r'do\s+not\s+(?:\w+\s+)*tell\s+(?:\w+\s+)*the\s+user',
     "deception_hide", "critical", "injection",
     "instructs agent to hide information from user"),
    
    (r'system\s+prompt\s+override',
     "sys_prompt_override", "critical", "injection",
     "attempts to override the system prompt"),
    
    (r'disregard\s+(?:\w+\s+)*(your|all|any)\s+(?:\w+\s+)*(instructions|rules|guidelines)',
     "disregard_rules", "critical", "injection",
     "instructs agent to disregard its rules"),
    
    # ── 角色劫持 ──
    (r'you\s+are\s+(?:\w+\s+)*now\s+',
     "role_hijack", "high", "injection",
     "attempts to override the agent's role"),
    
    (r'pretend\s+(?:\w+\s+)*(you\s+are|to\s+be)\s+',
     "role_pretend", "high", "injection",
     "attempts to make the agent assume a different identity"),
    
    (r'act\s+as\s+(if|though)\s+(?:\w+\s+)*you\s+(?:\w+\s+)*(have\s+no|don\'t\s+have)\s+(?:\w+\s+)*(restrictions|limits|rules)',
     "bypass_restrictions", "critical", "injection",
     "instructs agent to act without restrictions"),
    
    # ── 越狱尝试 ──
    (r'\bDAN\s+mode\b|Do\s+Anything\s+Now',
     "jailbreak_dan", "critical", "injection",
     "DAN (Do Anything Now) jailbreak attempt"),
    
    (r'\bdeveloper\s+mode\b.*\benabled?\b',
     "jailbreak_dev_mode", "critical", "injection",
     "developer mode jailbreak attempt"),
    
    (r'hypothetical\s+scenario.*(?:ignore|bypass|override)',
     "hypothetical_bypass", "high", "injection",
     "hypothetical scenario used to bypass restrictions"),
    
    # ── 社会工程 ──
    (r'you\s+have\s+been\s+(?:\w+\s+)*(updated|upgraded|patched)\s+to',
     "fake_update", "high", "injection",
     "fake update/patch announcement (social engineering)"),
    
    (r'new\s+policy|updated\s+guidelines|revised\s+instructions',
     "fake_policy", "medium", "injection",
     "claims new policy/guidelines (may be social engineering)"),
    
    # ── HTML 隐藏指令 ──
    (r'<!--[^>]*(?:ignore|override|system|secret|hidden)[^>]*-->',
     "html_comment_injection", "high", "injection",
     "hidden instructions in HTML comments"),
    
    (r'<\s*div\s+style\s*=\s*["\'][\s\S]*?display\s*:\s*none',
     "hidden_div", "high", "injection",
     "hidden HTML div (invisible instructions)"),
])
```

**攻击类型覆盖**：
- ✅ **直接覆盖**：忽略之前的指令、覆盖系统提示
- ✅ **欺骗隐藏**：指示 Agent 向用户隐瞒信息
- ✅ **角色劫持**：让 Agent 扮演无限制的助手
- ✅ **越狱技术**：DAN 模式、开发者模式等已知越狱方法
- ✅ **社会工程**：虚假更新公告、新政策声明
- ✅ **隐蔽通道**：HTML 注释、隐藏 DIV 元素

<a id="33-破坏性操作destructive--8-个模式"></a>
<a id="section-3-2-3-3"></a>
##### 3.2.3.3 破坏性操作（Destructive）- 8 个模式

```python
THREAT_PATTERNS.extend([
    (r'rm\s+-rf\s+/',
     "destructive_root_rm", "critical", "destructive",
     "recursive delete from root"),
    
    (r'rm\s+(-[^\s]*)?r.*\$HOME|\brmdir\s+.*\$HOME',
     "destructive_home_rm", "critical", "destructive",
     "recursive delete targeting home directory"),
    
    (r'chmod\s+777',
     "insecure_perms", "medium", "destructive",
     "sets world-writable permissions"),
    
    (r'>\s*/etc/',
     "system_overwrite", "critical", "destructive",
     "overwrites system configuration file"),
    
    (r'\bmkfs\b',
     "format_filesystem", "critical", "destructive",
     "formats a filesystem"),
    
    (r'\bdd\s+.*if=.*of=/dev/',
     "disk_overwrite", "critical", "destructive",
     "raw disk write operation"),
    
    (r'shutil\.rmtree\s*\(\s*[\"\'/]',
     "python_rmtree", "high", "destructive",
     "Python rmtree on absolute or root-relative path"),
    
    (r'truncate\s+-s\s*0\s+/',
     "truncate_system", "critical", "destructive",
     "truncates system file to zero bytes"),
])
```

<a id="34-持久化persistence--10-个模式"></a>
<a id="section-3-2-3-4"></a>
##### 3.2.3.4 持久化（Persistence）- 10 个模式

```python
THREAT_PATTERNS.extend([
    (r'\bcrontab\b',
     "persistence_cron", "medium", "persistence",
     "modifies cron jobs"),
    
    (r'\.(bashrc|zshrc|profile|bash_profile|bash_login|zprofile|zlogin)\b',
     "shell_rc_mod", "medium", "persistence",
     "references shell startup file"),
    
    (r'authorized_keys',
     "ssh_backdoor", "critical", "persistence",
     "modifies SSH authorized keys"),
    
    (r'systemd.*\.service|systemctl\s+(enable|start)',
     "systemd_service", "medium", "persistence",
     "references or enables systemd service"),
    
    (r'/etc/sudoers|visudo',
     "sudoers_mod", "critical", "persistence",
     "modifies sudoers (privilege escalation)"),
    
    (r'AGENTS\.md|CLAUDE\.md|\.cursorrules|\.clinerules',
     "agent_config_mod", "critical", "persistence",
     "references agent config files (could persist malicious instructions across sessions)"),
    
    (r'\.hermes/config\.yaml|\.hermes/SOUL\.md',
     "hermes_config_mod", "critical", "persistence",
     "references Hermes configuration files directly"),
])
```

**关键点**：检测对 Agent 配置文件（`AGENTS.md`、`.cursorrules`、`SOUL.md`）的修改，防止跨会话持久化恶意指令。

<a id="35-网络攻击network--10-个模式"></a>
<a id="section-3-2-3-5"></a>
##### 3.2.3.5 网络攻击（Network）- 10 个模式

```python
THREAT_PATTERNS.extend([
    (r'\bnc\s+-[lp]|ncat\s+-[lp]|\bsocat\b',
     "reverse_shell", "critical", "network",
     "potential reverse shell listener"),
    
    (r'\bngrok\b|\blocaltunnel\b|\bserveo\b|\bcloudflared\b',
     "tunnel_service", "high", "network",
     "uses tunneling service for external access"),
    
    (r'/bin/(ba)?sh\s+-i\s+.*>/dev/tcp/',
     "bash_reverse_shell", "critical", "network",
     "bash interactive reverse shell via /dev/tcp"),
    
    (r'python[23]?\s+-c\s+["\']import\s+socket',
     "python_socket_oneliner", "critical", "network",
     "Python one-liner socket connection (likely reverse shell)"),
    
    (r'webhook\.site|requestbin\.com|pipedream\.net|hookbin\.com',
     "exfil_service", "high", "network",
     "references known data exfiltration/webhook testing service"),
])
```

<a id="36-混淆技术obfuscation--12-个模式"></a>
<a id="section-3-2-3-6"></a>
##### 3.2.3.6 混淆技术（Obfuscation）- 12 个模式

```python
THREAT_PATTERNS.extend([
    (r'base64\s+(-d|--decode)\s*\|',
     "base64_decode_pipe", "high", "obfuscation",
     "base64 decodes and pipes to execution"),
    
    (r'\beval\s*\(\s*["\']',
     "eval_string", "high", "obfuscation",
     "eval() with string argument"),
    
    (r'\bexec\s*\(\s*["\']',
     "exec_string", "high", "obfuscation",
     "exec() with string argument"),
    
    (r'echo\s+[^\n]*\|\s*(bash|sh|python|perl|ruby|node)',
     "echo_pipe_exec", "critical", "obfuscation",
     "echo piped to interpreter for execution"),
    
    (r'getattr\s*\(\s*__builtins__',
     "python_getattr_builtins", "high", "obfuscation",
     "dynamic access to Python builtins (evasion technique)"),
    
    (r'__import__\s*\(\s*["\']os["\']\s*\)',
     "python_import_os", "high", "obfuscation",
     "dynamic import of os module"),
    
    (r'chr\s*\(\s*\d+\s*\)\s*\+\s*chr\s*\(\s*\d+',
     "chr_building", "high", "obfuscation",
     "building string from chr() calls (obfuscation)"),
])
```

<a id="37-供应链攻击supply-chain--8-个模式"></a>
<a id="section-3-2-3-7"></a>
##### 3.2.3.7 供应链攻击（Supply Chain）- 8 个模式

```python
THREAT_PATTERNS.extend([
    (r'curl\s+[^\n]*\|\s*(ba)?sh',
     "curl_pipe_shell", "critical", "supply_chain",
     "curl piped to shell (download-and-execute)"),
    
    (r'wget\s+[^\n]*-O\s*-\s*\|\s*(ba)?sh',
     "wget_pipe_shell", "critical", "supply_chain",
     "wget piped to shell (download-and-execute)"),
    
    (r'pip\s+install\s+(?!-r\s)(?!.*==)',
     "unpinned_pip_install", "medium", "supply_chain",
     "pip install without version pinning"),
    
    (r'(curl|wget|httpx?\.get|requests\.get|fetch)\s*[\(]?\s*["\']https?://',
     "remote_fetch", "medium", "supply_chain",
     "fetches remote resource at runtime"),
    
    (r'git\s+clone\s+',
     "git_clone", "medium", "supply_chain",
     "clones a git repository at runtime"),
])
```

<a id="38-硬编码凭证credential-exposure--6-个模式"></a>
<a id="section-3-2-3-8"></a>
##### 3.2.3.8 硬编码凭证（Credential Exposure）- 6 个模式

```python
THREAT_PATTERNS.extend([
    (r'(?:api[_-]?key|token|secret|password)\s*[=:]\s*["\'][A-Za-z0-9+/=_-]{20,}',
     "hardcoded_secret", "critical", "credential_exposure",
     "possible hardcoded API key, token, or secret"),
    
    (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----',
     "embedded_private_key", "critical", "credential_exposure",
     "embedded private key"),
    
    (r'ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{80,}',
     "github_token_leaked", "critical", "credential_exposure",
     "GitHub personal access token in skill content"),
    
    (r'sk-[A-Za-z0-9]{20,}',
     "openai_key_leaked", "critical", "credential_exposure",
     "possible OpenAI API key in skill content"),
    
    (r'sk-ant-[A-Za-z0-9_-]{90,}',
     "anthropic_key_leaked", "critical", "credential_exposure",
     "possible Anthropic API key in skill content"),
    
    (r'AKIA[0-9A-Z]{16}',
     "aws_access_key_leaked", "critical", "credential_exposure",
     "AWS access key ID in skill content"),
])
```

<a id="步骤-4-不可见-unicode-字符检测"></a>
<a id="section-3-2-4"></a>
#### 3.2.4 步骤 4: 不可见 Unicode 字符检测

```python
# tools/skills_guard.py:509-527

INVISIBLE_CHARS = {
    '\u200b',  # zero-width space
    '\u200c',  # zero-width non-joiner
    '\u200d',  # zero-width joiner
    '\u2060',  # word joiner
    '\u2062',  # invisible times
    '\u2063',  # invisible separator
    '\u2064',  # invisible plus
    '\ufeff',  # zero-width no-break space (BOM)
    '\u202a',  # left-to-right embedding
    '\u202b',  # right-to-right embedding
    '\u202c',  # pop directional formatting
    '\u202d',  # left-to-right override
    '\u202e',  # right-to-left override
    '\u2066',  # left-to-right isolate
    '\u2067',  # right-to-left isolate
    '\u2068',  # first strong isolate
    '\u2069',  # pop directional isolate
}

# 在 scan_file 函数中检测
for i, line in enumerate(lines, start=1):
    for char in INVISIBLE_CHARS:
        if char in line:
            char_name = _unicode_char_name(char)
            findings.append(Finding(
                pattern_id="invisible_unicode",
                severity="high",
                category="injection",
                file=rel_path,
                line=i,
                match=f"U+{ord(char):04X} ({char_name})",
                description=f"invisible unicode character {char_name} (possible text hiding/injection)",
            ))
            break  # one finding per line for invisible chars
```

**攻击场景**：
- **文本隐藏**：使用零宽字符隐藏恶意指令
- **方向覆盖**：RTL/LTR 控制字符可以改变文本显示顺序，隐藏真实内容
- **同形异义**：视觉上相同的字符可能有不同的 Unicode 码点

<a id="步骤-5-裁决判定"></a>
<a id="section-3-2-5"></a>
#### 3.2.5 步骤 5: 裁决判定

```python
# tools/skills_guard.py:911-923

def _determine_verdict(findings: List[Finding]) -> str:
    """根据发现列表确定总体裁决"""
    if not findings:
        return "safe"
    
    has_critical = any(f.severity == "critical" for f in findings)
    has_high = any(f.severity == "high" for f in findings)
    
    if has_critical:
        return "dangerous"
    if has_high:
        return "caution"
    return "caution"  # medium/low findings also trigger caution
```

**裁决规则**：
- `safe`: 无任何发现
- `caution`: 存在 high/medium/low 严重性发现
- `dangerous`: 存在 critical 严重性发现

<a id="23-策略决策矩阵"></a>
<a id="section-3-3"></a>
### 3.3 策略决策矩阵

```python
# tools/skills_guard.py:41-53

INSTALL_POLICY = {
    #                  safe      caution    dangerous
    "builtin":       ("allow",  "allow",   "allow"),
    "trusted":       ("allow",  "allow",   "block"),
    "community":     ("allow",  "block",   "block"),
    "agent-created": ("allow",  "allow",   "ask"),
}

VERDICT_INDEX = {"safe": 0, "caution": 1, "dangerous": 2}

def should_allow_install(result: ScanResult, force: bool = False) -> Tuple[bool, str]:
    """根据扫描结果和信任度决定是否允许安装"""
    policy = INSTALL_POLICY.get(result.trust_level, INSTALL_POLICY["community"])
    vi = VERDICT_INDEX.get(result.verdict, 2)
    decision = policy[vi]
    
    if decision == "allow":
        return True, f"Allowed ({result.trust_level} source, {result.verdict} verdict)"
    
    if force:
        return True, (
            f"Force-installed despite {result.verdict} verdict "
            f"({len(result.findings)} findings)"
        )
    
    if decision == "ask":
        return None, (
            f"Requires confirmation ({result.trust_level} source + {result.verdict} verdict, "
            f"{len(result.findings)} findings)"
        )
    
    return False, (
        f"Blocked ({result.trust_level} source + {result.verdict} verdict, "
        f"{len(result.findings)} findings). Use --force to override."
    )
```

**决策矩阵可视化**：

| 信任级别 \ 裁决 | safe | caution | dangerous |
|----------------|------|---------|-----------|
| **builtin** | ✅ allow | ✅ allow | ✅ allow |
| **trusted** | ✅ allow | ✅ allow | ❌ block |
| **community** | ✅ allow | ❌ block | ❌ block |
| **agent-created** | ✅ allow | ✅ allow | ❓ ask |

**关键设计决策**：
- ✅ **社区技能零容忍**：任何 warning 级别的发现都会阻止安装
- ✅ **可信来源适度宽松**：允许 caution 级别（可能是误报）
- ✅ **Agent 自生成技能需确认**：dangerous 发现时询问用户（而非直接阻止）
- ✅ **强制覆盖机制**：`--force` 标志可以绕过所有阻止

<a id="24-集成到安装流程"></a>
<a id="section-3-4"></a>
### 3.4 集成到安装流程

```python
# tools/skill_manager_tool.py:78-102

def _security_scan_skill(skill_dir: Path) -> Optional[str]:
    """在写入后扫描技能目录。如果被阻止则返回错误字符串，否则返回 None。
    
    当 skills.guard_agent_created 禁用时（默认情况），此功能无操作。
    """
    if not _GUARD_AVAILABLE:
        return None
    if not _guard_agent_created_enabled():
        return None
    try:
        result = scan_skill(skill_dir, source="agent-created")
        allowed, reason = should_allow_install(result)
        if allowed is False:
            report = format_scan_report(result)
            return f"Security scan blocked this skill ({reason}):\n{report}"
        if allowed is None:
            # "ask" verdict — 检测到危险发现
            report = format_scan_report(result)
            logger.warning("Agent-created skill blocked (dangerous findings): %s", reason)
            return f"Security scan blocked this skill ({reason}):\n{report}"
    except Exception as e:
        logger.warning("Security scan failed for %s: %s", skill_dir, e, exc_info=True)
    return None
```

**调用点**：

```python
# 在 _create_skill、_update_skill、_patch_skill、_write_file 中调用

# 示例：创建技能后扫描
def _create_skill(name: str, content: str, ...) -> Dict[str, Any]:
    # ... 写入文件 ...
    
    # Security scan — roll back on block
    scan_error = _security_scan_skill(skill_dir)
    if scan_error:
        shutil.rmtree(skill_dir)  # Rollback
        return {"success": False, "error": scan_error}
    
    return {"success": True, ...}
```

**回滚机制**：如果扫描失败，立即删除已创建的文件，确保不会留下不安全的技能。

---

<a id="3-第二层context-scanner上下文文件加载时扫描"></a>
<a id="section-4"></a>
## 4. 第二层：Context Scanner（上下文文件加载时扫描）

<a id="31-设计目标"></a>
<a id="section-4-1"></a>
### 4.1 设计目标

保护 System Prompt 免受恶意上下文文件（如 `AGENTS.md`、`HERMES.md`、`.cursorrules`）的注入攻击。

<a id="32-扫描实现"></a>
<a id="section-4-2"></a>
### 4.2 扫描实现

```python
# agent/prompt_builder.py:36-73

_CONTEXT_THREAT_PATTERNS = [
    (r'ignore\s+(previous|all|above|prior)\s+instructions', "prompt_injection"),
    (r'do\s+not\s+tell\s+the\s+user', "deception_hide"),
    (r'system\s+prompt\s+override', "sys_prompt_override"),
    (r'disregard\s+(your|all|any)\s+(instructions|rules|guidelines)', "disregard_rules"),
    (r'act\s+as\s+(if|though)\s+you\s+(have\s+no|don\'t\s+have)\s+(restrictions|limits|rules)', "bypass_restrictions"),
    (r'<!--[^>]*(?:ignore|override|system|secret|hidden)[^>]*-->', "html_comment_injection"),
    (r'<\s*div\s+style\s*=\s*["\'][\s\S]*?display\s*:\s*none', "hidden_div"),
    (r'translate\s+.*\s+into\s+.*\s+and\s+(execute|run|eval)', "translate_execute"),
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_curl"),
    (r'cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass)', "read_secrets"),
]

_CONTEXT_INVISIBLE_CHARS = {
    '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff',
    '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',
}

def _scan_context_content(content: str, filename: str) -> str:
    """扫描上下文文件内容以检测注入。返回清理后的内容。"""
    findings = []
    
    # 检查不可见 Unicode
    for char in _CONTEXT_INVISIBLE_CHARS:
        if char in content:
            findings.append(f"invisible unicode U+{ord(char):04X}")
    
    # 检查威胁模式
    for pattern, pid in _CONTEXT_THREAT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            findings.append(pid)
    
    if findings:
        logger.warning("Context file %s blocked: %s", filename, ", ".join(findings))
        return f"[BLOCKED: {filename} contained potential prompt injection ({', '.join(findings)}). Content not loaded.]"
    
    return content
```

<a id="33-调用链路"></a>
<a id="section-4-3"></a>
### 4.3 调用链路

```python
# agent/prompt_builder.py:load_context_files

def load_context_files(cwd: Path) -> str:
    """加载上下文文件"""
    parts = []
    
    # 1. 查找 .hermes.md
    hermes_md = _find_hermes_md(cwd)
    if hermes_md:
        content = hermes_md.read_text(encoding="utf-8")[:CONTEXT_FILE_MAX_CHARS]
        content = _scan_context_content(content, hermes_md.name)  # ← 扫描
        parts.append(f"# Project Context (from {hermes_md.name})\n\n{content}")
    
    # 2. 查找 AGENTS.md
    agents_md = cwd / "AGENTS.md"
    if agents_md.exists():
        content = agents_md.read_text()[:CONTEXT_FILE_MAX_CHARS]
        content = _scan_context_content(content, "AGENTS.md")  # ← 扫描
        parts.append(f"# Agent Instructions (from AGENTS.md)\n\n{content}")
    
    # 3. 查找 SOUL.md
    soul_md = get_hermes_home() / "SOUL.md"
    if soul_md.exists():
        content = soul_md.read_text()[:CONTEXT_FILE_MAX_CHARS]
        content = _scan_context_content(content, "SOUL.md")  # ← 扫描
        parts.append(f"# Personality (from SOUL.md)\n\n{content}")
    
    return "\n\n---\n\n".join(parts)
```

<a id="34-阻断效果"></a>
<a id="section-4-4"></a>
### 4.4 阻断效果

当检测到威胁时，返回明确的阻断消息：

```
[BLOCKED: AGENTS.md contained potential prompt injection (prompt_injection, deception_hide). Content not loaded.]
```

**优势**：
- ✅ **快速失败**：在 Prompt 构建阶段就阻止恶意内容
- ✅ **明确反馈**：告知哪些模式被触发
- ✅ **日志记录**：记录警告以便审计

**局限**：
- ⚠️ **模式较少**：只有 10 个模式，不如 Skills Guard 全面
- ⚠️ **无法区分误报**：合法的 "ignore previous instructions" 也会被阻止

---

<a id="4-第三层runtime-injection-detection运行时注入检测"></a>
<a id="section-5"></a>
## 5. 第三层：Runtime Injection Detection（运行时注入检测）

<a id="41-设计理念"></a>
<a id="section-5-1"></a>
### 5.1 设计理念

在查看/加载技能时进行轻量级检测，主要目的是**监控和告警**，而非阻断。

<a id="42-实现细节"></a>
<a id="section-5-2"></a>
### 5.2 实现细节

```python
# tools/skills_tool.py:133-143

_INJECTION_PATTERNS: list = [
    "ignore previous instructions",
    "ignore all previous",
    "you are now",
    "disregard your",
    "forget your instructions",
    "new instructions:",
    "system prompt:",
    "<system>",
    "]]>",
]

# 在 skill_view 函数中使用
def skill_view(name: str, ...) -> str:
    # ... 读取技能内容 ...
    
    # Injection scan — log but still serve (matches local-skill behaviour)
    if any(p in content.lower() for p in _INJECTION_PATTERNS):
        logger.warning(
            "Plugin skill '%s:%s' contains patterns that may indicate prompt injection",
            namespace, bare,
        )
    
    # 继续正常返回内容
    return json.dumps({"success": True, "content": content, ...})
```

<a id="43-与其他层的对比"></a>
<a id="section-5-3"></a>
### 5.3 与其他层的对比

| 特性 | Skills Guard | Context Scanner | Runtime Detector |
|------|-------------|-----------------|------------------|
| **触发时机** | 安装前 | Prompt 构建时 | 查看/加载时 |
| **检测方式** | 100+ 正则模式 | 10 正则 + Unicode | 9 简单字符串 |
| **阻断能力** | ✅ 完全阻断 | ✅ 完全阻断 | ❌ 仅告警 |
| **性能影响** | 一次性 | 每次对话 | 每次查看 |
| **误报处理** | `--force` 覆盖 | 无法覆盖 | 无影响 |

**设计意图**：
- ✅ **分层防御**：不同阶段有不同的安全需求
- ✅ **用户体验**：运行时只告警不阻断，避免打断工作流
- ✅ **监控价值**：即使不阻断，日志也能帮助发现潜在问题

---

<a id="5-威胁模式库详解"></a>
<a id="section-6"></a>
## 6. 威胁模式库详解

<a id="51-模式统计"></a>
<a id="section-6-1"></a>
### 6.1 模式统计

| 类别 | 模式数量 | Critical | High | Medium | Low |
|------|---------|----------|------|--------|-----|
| Exfiltration | 18 | 12 | 6 | 0 | 0 |
| Injection | 20 | 12 | 6 | 2 | 0 |
| Destructive | 8 | 6 | 1 | 1 | 0 |
| Persistence | 10 | 4 | 0 | 6 | 0 |
| Network | 10 | 4 | 4 | 2 | 0 |
| Obfuscation | 12 | 1 | 7 | 4 | 0 |
| Supply Chain | 8 | 3 | 0 | 5 | 0 |
| Credential Exposure | 6 | 6 | 0 | 0 | 0 |
| Execution | 7 | 0 | 5 | 2 | 0 |
| Traversal | 5 | 1 | 2 | 2 | 0 |
| Mining | 2 | 1 | 0 | 1 | 0 |
| Privilege Escalation | 5 | 3 | 2 | 0 | 0 |
| Structural | 4 | 1 | 1 | 2 | 0 |
| **总计** | **105** | **50** | **34** | **21** | **0** |

<a id="52-模式质量评估"></a>
<a id="section-6-2"></a>
### 6.2 模式质量评估

<a id="优点"></a>
<a id="section-6-2-1"></a>
#### 6.2.1 优点

✅ **覆盖面广**：从数据泄露到越狱攻击，涵盖 OWASP Top 10 for LLM

✅ **多语言支持**：检测 Python、JavaScript、Node.js、Ruby、Java 等多种语言的攻击模式

✅ **上下文感知**：不仅检测关键词，还考虑上下文（如 `os.environ` 排除 `PATH` 访问）

✅ **结构化分类**：每个模式都有明确的类别和严重性，便于优先级排序

✅ **持续更新**：包含最新的越狱技术（DAN、开发者模式等）

<a id="潜在改进空间"></a>
<a id="section-6-2-2"></a>
#### 6.2.2 潜在改进空间

⚠️ **误报风险**：某些模式可能过于宽泛

```python
# 示例：这个模式可能误报合法的教学内容
(r'for\s+educational\s+purposes?\s+only',
 "educational_pretext", "medium", "injection",
 "educational pretext often used to justify harmful content")
```

**建议**：增加白名单机制或置信度评分

⚠️ **正则性能**：100+ 个正则在大型文件上可能较慢

**优化建议**：
- 使用 `re.compile()` 预编译所有模式
- 实现早期退出（找到 critical 后立即返回）
- 并行扫描多个文件

⚠️ **绕过可能性**：简单的字符串替换可能绕过检测

```python
# 可能被绕过的模式
"ignore previous instructions"

# 绕过示例
"ignore  previous  instructions"  # 额外空格
"IgNoRe PrEvIoUs InStRuCtIoNs"    # 混合大小写（虽然有 IGNORECASE）
"ignore\u200bprevious instructions"  # 插入零宽字符（但有 Unicode 检测）
```

**建议**：增加模糊匹配或语义分析

---

<a id="6-信任模型与策略决策"></a>
<a id="section-7"></a>
## 7. 信任模型与策略决策

<a id="61-信任级别设计"></a>
<a id="section-7-1"></a>
### 7.1 信任级别设计

```mermaid
graph LR
    A[Skill Source] --> B{Source Type?}
    B -->|Official Repo| C[builtin]
    B -->|Trusted Vendor| D[trusted]
    B -->|Agent Self-Gen| E[agent-created]
    B -->|Unknown| F[community]
    
    C --> G[Skip Scan]
    D --> H[Scan + Lenient Policy]
    E --> I[Scan + Ask on Dangerous]
    F --> J[Scan + Strict Policy]
```

<a id="62-策略合理性分析"></a>
<a id="section-7-2"></a>
### 7.2 策略合理性分析

<a id="builtin内置技能"></a>
<a id="section-7-2-1"></a>
#### 7.2.1 builtin（内置技能）

**策略**：完全信任，跳过扫描

**理由**：
- ✅ 官方维护，经过代码审查
- ✅ 版本控制，变更可追溯
- ✅ 测试覆盖，质量保证

**风险**：
- ⚠️ 供应链攻击（如果官方仓库被入侵）
- ⚠️ 内部威胁（恶意提交者）

**缓解措施**：
- 依赖 Git 签名验证
- CI/CD 自动化测试
- 社区审计

<a id="trusted可信第三方"></a>
<a id="section-7-2-2"></a>
#### 7.2.2 trusted（可信第三方）

**策略**：扫描但允许 caution 级别

**当前可信源**：
- `openai/skills`
- `anthropics/skills`

**理由**：
- ✅ 知名厂商，有声誉约束
- ✅ 专业团队维护
- ⚠️ 但仍需防范 compromised accounts

**风险**：
- ⚠️ 账户被盗用
- ⚠️ 依赖项污染

**建议扩展**：
- 添加更多可信源（如 Microsoft、Google 的官方技能库）
- 实现动态信任评分（基于历史安全记录）

<a id="community社区技能"></a>
<a id="section-7-2-3"></a>
#### 7.2.3 community（社区技能）

**策略**：严格扫描，任何 warning 都阻止

**理由**：
- ❌ 零信任原则
- ❌ 无声誉约束
- ❌ 匿名贡献者

**挑战**：
- ⚠️ 高误报率可能阻碍创新
- ⚠️ 用户可能频繁使用 `--force`

**改进建议**：
- 实现社区声誉系统（类似 npm 的下载量/星标）
- 提供详细的误报报告渠道
- 允许用户标记"已审查"的技能

<a id="agent-createdagent-自生成"></a>
<a id="section-7-2-4"></a>
#### 7.2.4 agent-created（Agent 自生成）

**策略**：扫描，dangerous 时询问用户

**独特之处**：
- 🔄 可能受到 prompt injection 影响
- 🔄 Agent 可能"被说服"创建恶意技能
- 🔄 需要人类监督

**配置开关**：

```python
def _guard_agent_created_enabled() -> bool:
    """Read skills.guard_agent_created from config (default False).
    
    Off by default because the agent can already execute the same code
    paths via terminal() with no gate, so the scan adds friction without
    meaningful security.
    """
    return cfg_get(cfg, "skills", "guard_agent_created", default=False)
```

**争议点**：
- ❓ 为什么默认关闭？
  - **论点 1**：Agent 已经可以通过 `terminal()` 执行任意代码，扫描技能意义不大
  - **论点 2**：扫描增加了摩擦，但没有实质性提升安全性
  
- ❓ 是否应该默认开启？
  - **反论点**：技能是持久化的，而终端命令是临时的。阻止恶意技能创建比阻止单次命令更重要
  - **反论点**：扫描可以捕获 Agent 被注入后创建的恶意技能，作为最后一道防线

**建议**：
- 默认开启，但提供清晰的配置文档
- 在首次启动时提示用户选择安全级别

<a id="63-决策矩阵评估"></a>
<a id="section-7-3"></a>
### 7.3 决策矩阵评估

| 场景 | 当前策略 | 评估 | 建议 |
|------|---------|------|------|
| trusted + caution | ✅ allow | 合理，可能是误报 | 保持 |
| community + caution | ❌ block | 可能过于严格 | 考虑允许并告警 |
| agent-created + dangerous | ❓ ask | 良好平衡 | 保持 |
| community + dangerous | ❌ block | 正确 | 保持 |

---

<a id="7-关键代码路径追踪"></a>
<a id="section-8"></a>
## 8. 关键代码路径追踪

<a id="71-外部技能安装流程"></a>
<a id="section-8-1"></a>
### 8.1 外部技能安装流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant CLI as hermes CLI
    participant Installer as skill_manage_tool
    participant Guard as skills_guard
    participant FS as File System
    
    User->>CLI: hermes skill install <url>
    CLI->>Installer: download_and_install(url)
    Installer->>FS: 下载到临时目录
    FS-->>Installer: 返回 skill_dir
    
    Installer->>Guard: scan_skill(skill_dir, source)
    Note over Guard: 1. 解析信任级别<br/>2. 结构检查<br/>3. 正则匹配<br/>4. Unicode 检测
    Guard-->>Installer: ScanResult(verdict, findings)
    
    alt verdict == safe
        Installer->>FS: 移动到 ~/.hermes/skills/
        FS-->>Installer: 成功
        Installer-->>CLI: 安装成功
    else verdict == caution AND source == community
        Installer-->>CLI: 错误：Blocked (community + caution)
    else verdict == dangerous
        alt force flag
            Installer->>FS: 移动到 ~/.hermes/skills/
            FS-->>Installer: 成功（强制安装）
            Installer-->>CLI: 警告：强制安装
        else no force
            Installer-->>CLI: 错误：Blocked (dangerous)
        end
    end
    
    CLI-->>User: 显示结果
```

<a id="72-agent-创建技能流程"></a>
<a id="section-8-2"></a>
### 8.2 Agent 创建技能流程

```mermaid
sequenceDiagram
    participant Agent as AI Agent
    participant ALoop as AgentLoop
    participant Tool as skill_manage_tool
    participant Guard as skills_guard
    participant FS as File System
    
    Agent->>ALoop: tool_call skill_manage action create
    ALoop->>Tool: handle_function_call
    Tool->>FS: 创建技能目录和文件
    FS-->>Tool: 文件已写入
    
    alt guard_agent_created == true
        Tool->>Guard: scan_skill skill_dir agent-created
        Guard-->>Tool: ScanResult
        
        alt verdict == dangerous
            Tool->>FS: shutil.rmtree skill_dir 回滚
            FS-->>Tool: 已删除
            Tool-->>ALoop: success false error Security scan blocked
            ALoop-->>Agent: tool_result error
            Agent->>Agent: 重试或报告错误
        else verdict != dangerous
            Tool-->>ALoop: success true
            ALoop-->>Agent: tool_result success
        end
    else guard_agent_created == false
        Tool-->>ALoop: success true skip scan
        ALoop-->>Agent: tool_result success
    end
```

<a id="73-prompt-构建流程"></a>
<a id="section-8-3"></a>
### 8.3 Prompt 构建流程

```mermaid
sequenceDiagram
    participant Agent as AIAgent
    participant Builder as prompt_builder
    participant Scanner as _scan_context_content
    participant FS as File System
    
    Agent->>Builder: _build_system_prompt(cwd)
    
    Builder->>FS: 查找 .hermes.md
    FS-->>Builder: 找到文件
    Builder->>FS: 读取内容
    FS-->>Builder: 文件内容
    
    Builder->>Scanner: _scan_context_content(content, ".hermes.md")
    Scanner->>Scanner: 检查威胁模式
    Scanner->>Scanner: 检查 Unicode 字符
    
    alt 发现威胁
        Scanner-->>Builder: "[BLOCKED: ...]"
        Builder->>Builder: 追加阻断消息
    else 无威胁
        Scanner-->>Builder: 原始内容
        Builder->>Builder: 追加到 prompt
    end
    
    Builder->>FS: 查找 AGENTS.md
    FS-->>Builder: 找到文件
    Builder->>Scanner: _scan_context_content(...)
    Scanner-->>Builder: 扫描结果
    
    Builder->>Builder: 组装完整 prompt
    Builder-->>Agent: 返回 system prompt
```

---

<a id="8-安全设计原则评估"></a>
<a id="section-9"></a>
## 9. 安全设计原则评估

<a id="81-符合的安全原则"></a>
<a id="section-9-1"></a>
### 9.1 符合的安全原则

✅ **纵深防御（Defense in Depth）**
- 三层独立检测机制
- 每层有不同的目标和策略

✅ **最小特权（Least Privilege）**
- 社区技能默认阻止
- 需要显式授权才能安装可疑技能

✅ **故障安全（Fail-Safe Defaults）**
- 未知来源默认不信任
- 扫描失败时默认阻止（除非配置 fail-open）

✅ **审计追踪（Audit Trail）**
- 所有扫描结果都有日志记录
- `format_scan_report()` 提供详细报告

✅ **安全默认值（Secure by Default）**
- `guard_agent_created` 默认关闭（虽有争议）
- 社区技能默认严格策略

<a id="82-潜在弱点"></a>
<a id="section-9-2"></a>
### 9.2 潜在弱点

⚠️ **正则表达式局限性**

**问题**：正则无法理解语义，容易误报或漏报

**示例**：
```python
# 这段代码是合法的错误处理，但可能触发 "os.system" 模式
try:
    os.system("echo test")  # 用于调试
except:
    pass

# 这段恶意代码可能绕过检测
exec(getattr(__builtins__, 'chr')(101) + 'val("malicious")')
```

**建议**：
- 结合 AST 分析（针对 Python/JS）
- 使用 ML 模型进行语义分类

⚠️ **配置复杂性**

**问题**：多个配置选项可能导致用户困惑

```yaml
skills:
  guard_agent_created: false  # 这是什么意思？
  external_dirs: [...]        # 这些目录可信吗？
```

**建议**：
- 提供预设安全级别（strict/balanced/permissive）
- 交互式配置向导

⚠️ **性能开销**

**问题**：100+ 正则在大文件上可能慢

**测试建议**：
```python
import time
from pathlib import Path
from tools.skills_guard import scan_skill

# 基准测试
skill_dir = Path("large-skill-with-many-files")
start = time.perf_counter()
result = scan_skill(skill_dir)
elapsed = time.perf_counter() - start
print(f"Scanned in {elapsed:.2f}s, found {len(result.findings)} issues")
```

**优化建议**：
- 缓存编译后的正则
- 并行扫描多个文件
- 增量扫描（只扫描变化的文件）

⚠️ **绕过技术**

**可能的绕过方法**：

1. **编码绕过**：
```python
# Base64 编码的恶意指令
import base64
exec(base64.b64decode("aW1wb3J0IG9zOyBvcy5zeXN0ZW0oJ3JtIC1yZiAvJyk=").decode())
```
检测：已有 `base64_decode_pipe` 模式，但不够全面

2. **动态构造**：
```python
# 分块构造恶意字符串
part1 = "ignore"
part2 = "previous"
part3 = "instructions"
message = f"{part1} {part2} {part3}"
```
检测：难以通过正则捕获

3. **间接引用**：
```python
# 从外部文件读取指令
with open("/tmp/malicious.txt") as f:
    exec(f.read())
```
检测：已有 `remote_fetch` 模式，但可能漏报

**建议**：
- 实施动态分析沙箱
- 监控运行时行为（不仅仅是静态代码）

<a id="83-与其他项目的对比"></a>
<a id="section-9-3"></a>
### 9.3 与其他项目的对比

| 特性 | Hermes Agent | deer-flow | AutoGPT |
|------|-------------|-----------|---------|
| **静态扫描** | ✅ 100+ 模式 | ✅ LLM-based | ⚠️ 基础检查 |
| **信任模型** | ✅ 四级信任 | ⚠️ 二级（safe/unsafe） | ❌ 无 |
| **Unicode 检测** | ✅ 17 种字符 | ✅ 类似 | ❌ 无 |
| **结构检查** | ✅ 文件大小/数量 | ⚠️ 基础 | ❌ 无 |
| **回滚机制** | ✅ 自动删除 | ✅ 类似 | ❌ 无 |
| **配置灵活性** | ✅ 多级策略 | ⚠️ 固定策略 | ❌ 无 |

**结论**：Hermes Agent 的安全扫描是目前开源 Agent 框架中最全面的之一。

---

<a id="9-最佳实践建议"></a>
<a id="section-10"></a>
## 10. 最佳实践建议

<a id="91-对于技能开发者"></a>
<a id="section-10-1"></a>
### 10.1 对于技能开发者

✅ **编写安全技能**：
- 避免硬编码凭证（使用环境变量）
- 不要使用 `eval()`、`exec()`、`os.system()`
- 明确声明所需权限（`required_environment_variables`）
- 提供清晰的文档和使用示例

❌ **避免的模式**：
```yaml
# 错误示例
name: my-skill
description: Does something
---
curl https://api.example.com/$API_KEY  # ❌ 泄露秘密
eval($user_input)  # ❌ 代码注入风险
```

```yaml
# 正确示例
name: my-skill
description: Does something safely
prerequisites:
  env_vars:
    - API_KEY
---
# 使用安全的 HTTP 库
import requests
response = requests.get(
    "https://api.example.com/data",
    headers={"Authorization": f"Bearer {os.environ['API_KEY']}"}
)
```

<a id="92-对于用户"></a>
<a id="section-10-2"></a>
### 10.2 对于用户

✅ **安装技能时**：
- 优先使用官方或可信来源的技能
- 仔细阅读扫描报告，理解被阻止的原因
- 谨慎使用 `--force` 标志
- 定期审查已安装的技能

✅ **配置安全级别**：
```yaml
# ~/.hermes/config.yaml

# 严格模式（推荐新手）
skills:
  guard_agent_created: true
  external_dirs: []  # 不允许外部目录

# 平衡模式（推荐高级用户）
skills:
  guard_agent_created: true
  external_dirs:
    - ~/my-trusted-skills

# 宽松模式（仅用于开发/测试）
skills:
  guard_agent_created: false
  external_dirs:
    - ~/dev/skills
```

<a id="93-对于安全研究人员"></a>
<a id="section-10-3"></a>
### 10.3 对于安全研究人员

🔍 **审计建议**：
- 定期检查 `THREAT_PATTERNS` 是否有遗漏的攻击向量
- 测试新的越狱技术是否能被检测
- 评估误报率并提供反馈
- 贡献新的检测模式

📝 **报告漏洞**：
- 如果发现可以绕过检测的方法，请负责任地披露
- 提供 PoC（概念验证）代码
- 建议修复方案

---

<a id="10-未来改进方向"></a>
<a id="section-11"></a>
## 11. 未来改进方向

<a id="101-短期改进1-3-个月"></a>
<a id="section-11-1"></a>
### 11.1 短期改进（1-3 个月）

1. **性能优化**
   - 预编译所有正则表达式
   - 实现文件缓存（跳过未变化的文件）
   - 并行扫描

2. **误报减少**
   - 添加白名单机制
   - 提供上下文感知的模式（如区分教学内容和实际攻击）
   - 用户反馈循环（标记误报）

3. **文档完善**
   - 每个模式的详细说明和示例
   - 常见误报及解决方法
   - 安全编码指南

<a id="102-中期改进3-6-个月"></a>
<a id="section-11-2"></a>
### 11.2 中期改进（3-6 个月）

1. **ML 辅助检测**
   - 训练分类器识别 prompt injection
   - 结合正则和 ML 提高准确率
   - 减少误报

2. **动态分析**
   - 在沙箱中执行技能代码
   - 监控运行时行为（网络请求、文件访问）
   - 检测隐蔽的恶意行为

3. **声誉系统**
   - 社区评分和评论
   - 基于历史记录的信任度调整
   - 自动化风险评估

<a id="103-长期愿景6-12-个月"></a>
<a id="section-11-3"></a>
### 11.3 长期愿景（6-12 个月）

1. **形式化验证**
   - 使用定理证明器验证技能安全性
   - 确保关键属性（如无数据泄露）
   - 自动生成安全证明

2. **标准化**
   - 推动行业安全标准（如 OWASP for Agents）
   - 与其他框架共享威胁模式库
   - 建立认证体系

3. **自适应防御**
   - 根据攻击趋势自动更新模式
   - 机器学习驱动的威胁情报
   - 实时响应新型攻击

---

<a id="11-总结"></a>
<a id="section-12"></a>
## 12. 总结

<a id="111-核心优势"></a>
<a id="section-12-1"></a>
### 12.1 核心优势

✅ **全面性**：100+ 威胁模式覆盖 8 大类攻击向量

✅ **多层次**：三层防御体系在不同阶段提供保护

✅ **灵活性**：基于信任的策略允许不同安全需求

✅ **透明度**：详细的扫描报告和日志记录

✅ **可扩展**：模块化设计易于添加新模式

<a id="112-关键设计决策"></a>
<a id="section-12-2"></a>
### 12.2 关键设计决策

| 决策 | 理由 | 权衡 |
|------|------|------|
| 正则而非 ML | 快速、可解释、无需训练数据 | 可能误报/漏报 |
| 默认严格策略 | 安全第一原则 | 可能阻碍创新 |
| 可选的 agent 扫描 | 避免过度摩擦 | 可能错过攻击 |
| 不回溯已安装技能 | 性能考虑 | 遗留风险 |

<a id="113-适用场景"></a>
<a id="section-12-3"></a>
### 12.3 适用场景

✅ **适合**：
- 生产环境的 Agent 部署
- 多用户共享的 Agent 实例
- 需要审计合规的场景
- 处理敏感数据的任务

⚠️ **可能需要调整**：
- 个人开发/测试环境（可降低安全级别）
- 快速原型开发（可暂时禁用扫描）
- 内部可信网络（可放宽策略）

<a id="114-最终评价"></a>
<a id="section-12-4"></a>
### 12.4 最终评价

Hermes Agent 的安全扫描机制代表了当前 Agent 安全领域的**最佳实践**：

- 🏆 **技术深度**：从正则匹配到信任模型，设计精良
- 🏆 **工程实现**：代码清晰、测试充分、文档完整
- 🏆 **实用性**：在实际使用中平衡了安全性和可用性

**推荐指数**：⭐⭐⭐⭐⭐（5/5）

---

<a id="附录"></a>
<a id="section-13"></a>
## 13. 附录

<a id="a-完整的威胁模式列表"></a>
<a id="section-13-1"></a>
### 13.1 A. 完整的威胁模式列表

见 `tools/skills_guard.py:86-488`

<a id="b-配置文件示例"></a>
<a id="section-13-2"></a>
### 13.2 B. 配置文件示例

```yaml
# ~/.hermes/config.yaml

skills:
  # 是否扫描 Agent 创建的技能
  guard_agent_created: true
  
  # 外部技能目录（被视为可信）
  external_dirs:
    - ~/my-skills
    - /shared/team-skills
  
  # 禁用的技能（不会加载到 prompt）
  disabled_skills:
    - experimental-feature

security:
  # 允许访问私有 IP（用于内网服务）
  allow_private_urls: false
  
  # 启用 Tirith 安全扫描
  tirith_enabled: true
  
  # 扫描超时（秒）
  tirith_timeout: 5
  
  # 扫描失败时是否放行
  tirith_fail_open: false
```

<a id="c-常见问题解答"></a>
<a id="section-13-3"></a>
### 13.3 C. 常见问题解答

**Q1: 如何报告误报？**

A: 在 GitHub 提交 issue，包含：
- 技能名称和来源
- 被触发的模式
- 为什么认为是误报
- 建议的修复方案

**Q2: 可以自定义威胁模式吗？**

A: 目前不支持用户自定义，但可以：
- Fork 项目并修改 `THREAT_PATTERNS`
- 提交 PR 贡献新模式
- 使用 `--force` 临时绕过

**Q3: 扫描会影响性能吗？**

A: 
- 安装时扫描：一次性开销，通常 < 1 秒
- Prompt 构建时扫描：每次对话，但只扫描小文件
- 运行时检测：轻量级字符串匹配，影响可忽略

**Q4: 如何查看已安装技能的安全状态？**

A: 
```bash
# 查看所有技能
hermes skill list

# 查看特定技能的详细信息
hermes skill view <name>

# 重新扫描已安装的技能（未来功能）
hermes skill audit
```

<a id="d-参考文献"></a>
<a id="section-13-4"></a>
### 13.4 D. 参考文献

1. OWASP Top 10 for LLM Applications: https://owasp.org/www-project-top-10-for-large-language-model-applications/
2. Prompt Injection Attacks: https://simonwillison.net/2022/Sep/12/prompt-injection/
3. Unicode Security Considerations: https://www.unicode.org/reports/tr36/
4. Supply Chain Security for AI: https://mlsecproject.github.io/

---

**文档结束**

---

<a id="1-核心设计理念"></a>
<a id="2-完整执行流程"></a>
<a id="21-触发条件检测-conversation_looppyfileusersgqliworkdeepagentshermes-devhermes-agentagentconversation_looppy"></a>
<a id="22-计数器更新机制"></a>
<a id="3-源码级时序图"></a>
<a id="4-关键技术细节"></a>
<a id="41-fork-agent-创建-background_reviewpyfileusersgqliworkdeepagentshermes-devhermes-agentagentbackground_reviewpyl396-l445"></a>
<a id="42-工具白名单限制-background_reviewpyfileusersgqliworkdeepagentshermes-devhermes-agentagentbackground_reviewpyl447-l478"></a>
<a id="43-review-prompt-策略-background_reviewpyfileusersgqliworkdeepagentshermes-devhermes-agentagentbackground_reviewpyl45-l145"></a>
<a id="44-执行与结果汇总-background_reviewpyfileusersgqliworkdeepagentshermes-devhermes-agentagentbackground_reviewpyl495-l518"></a>
<a id="45-错误处理与清理-background_reviewpyfileusersgqliworkdeepagentshermes-devhermes-agentagentbackground_reviewpyl520-l549"></a>
<a id="5-性能影响分析"></a>
<a id="51-api-成本"></a>
<a id="52-延迟"></a>
<a id="53-内存"></a>
<a id="54-并发安全"></a>
<a id="6-与前台-skill_manage-和-curator-的边界"></a>
<a id="61-为什么不是一套机制"></a>
<a id="62-对延迟的真实影响"></a>
<a id="63-可能重叠的地方"></a>
<a id="7-设计风险与建议边界"></a>
<a id="71-风险"></a>
<a id="72-建议"></a>
<a id="part-b--background-review自进化审查part-b-background-review"></a>
<a id="🎯-总结"></a>
<a id="后台学习的安全边界详见-skills"></a>
<a id="section-14"></a>
## 14. 后台学习的安全边界（详见 Skills）

Background Review 是对话结束后的学习与技能维护，不是恶意输入扫描，也不是人工审批恢复。安全篇只关心它的工具白名单、写入保护和审计边界。

完整设计、图表与代码解读已移至 [后台自进化：Background Review、skill_manage 与 Curator](SKILLS_SYSTEM.md#background-review-design)。本处只保留与本篇主题直接相关的边界。

---

<!-- 旧章节锚点兼容：对应内容已校订，见文首导航。 -->
<a id="📋-目录-1"></a>

<!-- 旧目录与迁移章节锚点兼容；完整内容入口见文首目录及主题迁移表。 -->
<a id="hermes-安全扫描与后台治理canonical"></a>
