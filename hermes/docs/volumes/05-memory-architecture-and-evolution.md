# 卷五附录 B · Memory 协作架构与自我进化（Skills / Curator / Trajectory）

> **卷标准**：[`VOLUME_STANDARD.md`](VOLUME_STANDARD.md) · **完成度**：[`MANIFEST.md`](MANIFEST.md)  
> **本文件边界**：自 legacy `MEMORY_SYSTEM.md` 迁入的 **§6 协作与数据流**、**§9 扩展机制**、**附录 A/B（六层对比与演进表述）**。  
> **三层运行时 + 使用指南 + Provider 清单** → [卷五附录 A · Memory 参考](05-memory-system-reference.md)；循环内 Session/Memory 分工 → [卷三第6章](03-runtime-session-and-loop.md#sec-ch6)；后台复盘 fork → [卷八 §3](08-security-and-governance.md#3-后台复盘background-review)。  
> **权威源码**：`agent/memory_manager.py`、`tools/skill_usage.py`、`agent/curator.py`、`agent/trajectory.py`、`tools/skills_tool.py`、`agent/conversation_compression.py`

---

## 本附录目录

- [C. 协作、数据流与架构](#c-协作数据流与架构)（MemoryManager、协作矩阵、端到端流向）
- [D. 扩展机制：Skills / Curator / Trajectory](#d-扩展机制skills--curator--trajectory)（与 memory 协同的进化路径）
- [E. 附录：六层视角与演进表述](#e-附录六层视角与演进表述)（对外叙事用三层；对比框架时用六层）

---

<a id="c-协作数据流与架构"></a>

## C. 协作、数据流与架构

### 设计目标与非目标

#### 1.1 设计目标

如果只看功能名称，Hermes memory 很容易被误解成“多加几个存储后端”。但从源码上看，它追求的是下面几个更具体的目标：

- **低成本长期上下文**
  让一小部分高价值事实稳定进入 prompt，而不是每轮都做昂贵召回。
- **完整历史可追溯**
  让过去对话可检索、可回顾、可摘要，而不是只保留当前窗口。
- **本地优先但可增强**
  在没有外部依赖时，内建 memory 和 session archive 仍然可用；需要时再接 provider。
- **不把 recall 冒充成 user input**
  这是 Hermes memory 在安全和行为稳定性上的核心底线。
- **不让 memory 侵占全部系统复杂度**
  memory 重要，但它必须和 skills、tool loop、gateway、delegation 保持边界。

#### 1.2 非目标

同样重要的是，Hermes 当前**不追求**下面这些事情：

- **不追求 mid-session 热更新 system prompt**
  built-in memory 设计上就是 next-session-oriented，而不是 mutable prompt store。
- **不追求无限容量**
  `MEMORY.md` / `USER.md` 明确受限，强迫系统做 curated memory 而不是日志堆积。
- **不追求多个外部 provider 叠加**
  工程上优先避免 schema 冲突、治理混乱和双重写入。
- **不把 skill / trajectory 强行当成 memory 主层**
  它们相关，但角色不同。

### MemoryManager 与协作矩阵

#### 2.3 协作矩阵

这套系统最容易误判的地方,是把所有“看起来像记忆”的东西混在一起。下面这张协作矩阵用来区分谁负责什么:

| 组件 | 它真正负责的事 | 它不应该负责的事 | 主要协作对象 |
|------|----------------|------------------|--------------|
| `MemoryStore` | `MEMORY.md` / `USER.md` 的加载、冻结快照、文件级读写 | 外部 provider 生命周期 | `run_agent.py`, `memory_tool.py` |
| `memory` tool | 把长期稳定事实写入 built-in persistent memory | 搜索完整历史会话 | `MemoryStore` |
| `SessionDB` | 会话存档、FTS5 索引、历史检索底座 | system prompt 注入 | `run_agent.py`, `session_search_tool.py` |
| `session_search` | 基于 `state.db` 做历史回忆和 focused summary | 持久写入长期偏好 | `SessionDB` |
| `MemoryManager` | 编排一个 external provider 的 prefetch / sync / hooks | 替代 built-in memory 本体 | `MemoryProvider`, `run_agent.py` |
| external provider | 更深的语义 recall / user modeling / 外部持久化 | 管理 Hermes 全部记忆策略 | `MemoryManager` |

看这张表时,最重要的一条是:

> Hermes 不是一个“统一大 memory 仓库”,而是几套边界清晰、用途不同的记忆机制并行存在。

#### 2.4 MemoryManager 内部架构

```mermaid
classDiagram
    class MemoryManager {
        -List~MemoryProvider~ _providers
        -Dict~str, MemoryProvider~ _tool_to_provider
        -bool _has_external
        
        +add_provider(provider) None
        +build_system_prompt() str
        +prefetch_all(query, session_id) str
        +sync_all(user_msg, assistant_msg) None
        +queue_prefetch_all(query) None
        +handle_tool_call(name, args) str
        +has_tool(name) bool
    }
    
    class MemoryProvider {
        <<interface>>
        +name str
        +initialize() None
        +system_prompt_block() str
        +prefetch(query, session_id) str
        +queue_prefetch(query, session_id) None
        +sync_turn(user_msg, assistant_msg) None
        +get_tool_schemas() List
        +handle_tool_call(name, args) str
        +shutdown() None
    }
    
    class BuiltinMemoryProvider {
        -MemoryStore _store
        
        +prefetch() ""  # 无操作
        +sync_turn() None  # 无操作
        +get_tool_schemas() [memory tool schema]
    }
    
    class HonchoProvider {
        -HonchoClient _client
        -str _app_id
        -str _user_id
        
        +prefetch() 语义召回
        +sync_turn() 后台写入
        +on_session_end() 提炼摘要
    }
    
    class Mem0Provider {
        -Mem0Client _client
        
        +prefetch() 向量检索
        +sync_turn() 嵌入存储
    }
    
    MemoryManager o-- MemoryProvider : manages 1..2
    MemoryProvider <|-- BuiltinMemoryProvider
    MemoryProvider <|-- HonchoProvider
    MemoryProvider <|-- Mem0Provider
```

**关键设计约束**:
- ✅ Built-in Provider 始终存在且不可移除
- ✅ 最多允许 **1 个** External Provider(避免工具 schema 冲突)
- ✅ 单 Provider 失败不阻塞其他 Provider
- ✅ Tool name 冲突检测与警告

### 完整数据流向（含压缩、沉淀与第二轮拉取）


```mermaid
sequenceDiagram
    participant User as 用户
    participant RC as run_conversation
    participant PB as prompt_builder
    participant CC as ContextCompressor
    participant MS as MemoryStore
    participant Disk as MEMORY.md/USER.md
    participant MM as MemoryManager
    participant Ext as External Provider
    participant SDB as SessionDB (state.db)
    participant Skills as skills/
    participant Traj as trajectory/
    participant LLM as LLM API
    
    Note over User,LLM: === 第 N 轮：调用前准备阶段 ===
    User->>RC: 发送消息
    RC->>PB: _build_system_prompt()
    PB-->>RC: system_prompt (人格+skills+context)
    
    RC->>MS: load_from_disk()
    MS->>Disk: 读取 MEMORY.md / USER.md
    Disk-->>MS: 原始文本
    MS->>MS: 去重 + 验证字符上限
    MS->>MS: 渲染为 system block
    MS->>MS: 存入 _system_prompt_snapshot
    MS-->>RC: frozen snapshot
    
    alt 上下文超限触发压缩
        RC->>CC: _compress_context(messages)
        CC->>CC: 1. Prune old tool results (cheap pass)
        CC->>CC: 2. Protect head messages (system + first N)
        CC->>CC: 3. Protect tail by token budget (~20K tokens)
        CC->>CC: 4. Summarize middle turns via auxiliary LLM
        CC->>CC: 5. Merge iterative summary if exists
        CC-->>RC: compressed messages + new system_prompt
        RC->>SDB: create_child_session(parent_session_id)
        SDB-->>RC: new session_id
        Note over RC: conversation_history = None (fresh start)
    end
    
    RC->>MM: on_turn_start(turn_count, user_msg)
    MM->>Ext: on_turn_start()
    
    RC->>MM: prefetch_all(user_message)
    MM->>Ext: prefetch(query, session_id)
    Ext-->>MM: recalled memories (semantic/vector)
    MM->>MM: build_memory_context_block
    MM-->>RC: <memory-context> fenced block
    
    RC->>RC: Inject prefetch into user message (API-call-time only)
    RC->>RC: Build api_messages (system + history + tools)
    
    alt Anthropic cache control enabled
        RC->>RC: apply_anthropic_cache_control(api_messages)
    end
    
    RC->>LLM: API 调用 (chat.completions.create)
    
    Note over User,LLM: === 第 N 轮：工具执行循环 ===
    loop 直到纯文本响应或达到迭代上限
        LLM-->>RC: assistant response (tool_calls or text)
        
        alt 模型返回 tool_calls
            RC->>RC: Execute tools (terminal/read_file/search/etc.)
            RC->>RC: Append tool results to messages
            
            opt memory 工具被调用
                RC->>MS: add/replace/remove entry
                MS->>Disk: 原子写回 MEMORY.md/USER.md
                Disk-->>MS: 确认
                MS-->>RC: live state
                
                RC->>MM: on_memory_write(entry)
                MM->>Ext: 镜像写入 (可选)
            end
            
            opt skill_manage 工具被调用
                RC->>Skills: create/update/delete skill
                Skills-->>RC: confirmation
            end
            
            RC->>RC: Check iteration budget
            RC->>LLM: 下一轮 API 调用 (带 tool results)
        else 模型返回纯文本
            LLM-->>RC: final_response (text content)
        end
    end
    
    Note over User,LLM: === 第 N 轮：调用后沉淀阶段 ===
    
    par 并行沉淀到多个存储
        RC->>SDB: _flush_messages_to_session_db()
        SDB->>SDB: INSERT INTO sessions/messages
        SDB->>SDB: UPDATE FTS5 index
        SDB-->>RC: confirmed
        
        RC->>Traj: _save_trajectory()
        Traj->>Traj: Convert to ShareGPT format
        Traj->>Traj: Write to trajectory/*.jsonl
        Traj-->>RC: saved
        
        RC->>MM: sync_all(user_msg, assistant_msg)
        MM->>Ext: sync_turn(...)
        Ext->>Ext: 后台嵌入/存储到向量库
        Ext-->>MM: acknowledged
        
        RC->>MM: queue_prefetch_all(next_query)
        MM->>Ext: 异步预取下一轮 (daemon thread)
        Ext-->>MM: prefetch cached
    end
    
    Note over Disk: MEMORY.md/USER.md 已实时更新
    Note over SDB: state.db 已归档完整会话
    Note over Traj: trajectory 已导出训练资产
    Note over Ext: External provider 已同步并预取
    
    Note over User,LLM: === 第 N+1 轮：拉取与复用阶段 ===
    User->>RC: 发送新消息 (continuation)
    
    RC->>SDB: get_session(session_id)
    SDB-->>RC: stored system_prompt + messages
    
    alt 延续会话 (stored system_prompt exists)
        RC->>RC: Reuse stored system_prompt (cache prefix match)
        Note over RC: 避免 rebuild 破坏 Anthropic prefix cache
    else 新会话
        RC->>PB: _build_system_prompt() (fresh build)
    end
    
    RC->>MS: load_from_disk() (再次加载，可能已有更新)
    MS->>Disk: 读取最新 MEMORY.md / USER.md
    Disk-->>MS: updated content
    MS-->>RC: new frozen snapshot
    
    RC->>MM: on_turn_start(turn_count+1, new_user_msg)
    RC->>MM: prefetch_all(new_user_message)
    MM->>Ext: prefetch(query) (使用上一轮 queue_prefetch 的结果)
    Ext-->>MM: warmed context (low latency)
    MM-->>RC: <memory-context> for turn N+1
    
    RC->>LLM: API 调用 (带更新的上下文)
    
    Note over Disk: 下次会话才会看到第 N 轮写入的 memory
    Note over Ext: Prefetch 结果已在后台准备好
```

**关键观察**:
1. **写盘是实时的** - `memory` 工具立即更新 `MEMORY.md` / `USER.md`
2. **Prompt 生效是延迟的** - 当前会话仍使用 frozen snapshot，下一轮才重新加载
3. **External Provider 是增强的** - 提供实时语义召回，但不替代 built-in
4. **压缩是主动的** - 上下文超限时触发 ContextCompressor，创建子会话链
5. **沉淀是多路径的** - SessionDB (归档) + Trajectory (训练) + External (向量库) 并行写入
6. **预取是异步的** - `queue_prefetch_all` 在后台 daemon thread 中预热下一轮上下文
7. **缓存是优化的** - Anthropic prefix cache 通过复用 stored system_prompt 保持命中

### 当前实现真正的「层级」与易误判点

#### 7. 当前实现真正的“层级”

如果一定要讲层级，我建议用下面这组更贴近现实的维度，而不是旧的六层官方口径：

| 维度 | 当前实现 |
|------|----------|
| **始终在线长期记忆** | `MEMORY.md` + `USER.md` |
| **历史会话档案** | `state.db` + FTS5 |
| **可选语义增强** | external provider |
| **运行态工作记忆** | 当前 messages / tool loop / context window |
| **方法论沉淀** | skills |
| **训练与离线资产** | trajectories / compressor / RL |

这样更容易避免概念污染。

---

#### 8. 设计优劣势

##### 8.1 优势

- 主层清晰：built-in memory 和 session archive 职责不同
- 本地优先：没有外部 provider 也能工作
- 成本稳定：frozen snapshot 避免每轮重注入
- 安全意识较强：写入扫描 + fenced recall
- 可扩展：provider interface 很清楚

##### 8.2 代价

- built-in memory 不会在当前 session 热更新
- 长期记忆容量刻意受限，需要持续精编
- external provider 只能单选，不能叠加
- 对初学者来说，memory / session_search / skills 边界不直观

---

#### 9. 读源码时最容易误判的点

##### 9.1 不要把 `MemoryManager` 当成 built-in memory 本体

当前 `MemoryManager` 主要是 external provider 编排器。

built-in persistent memory 的核心实现其实是：

- `MemoryStore`
- `memory` tool

##### 9.2 不要把 `session_search` 当成 provider

`session_search` 是 Hermes 核心工具，不属于 external provider 插件体系。

##### 9.3 不要把 skills 当成 built-in memory

skills 可以沉淀经验，但它们不是 `MEMORY.md` / `USER.md` 那套持久记忆文件。

---


<a id="d-扩展机制skills--curator--trajectory"></a>

## D. 扩展机制（非 memory 主模型）

> Skills、Curator、Trajectory **不是** Persistent Memory 的子类型。  
> 主模型仍是三层；本节描述与 memory **协同**的进化/沉淀机制。  
> 已删除旧稿中错误的 `memory(action="write")` /「<5KB」示例（与 §3 API 冲突）。

### 本节范围

本文只回答：

- memory 如何与 skills 协作
- 对话如何变成训练资产
- Hermes 所谓“self-improving”在工程上是怎么分层的

---

### 2. Hermes 的"进化"不是单一路径

Hermes 所谓进化，至少有四条不同路径：

1. **Curated Memory 更新**（curated memory = 精选记忆 / 策展记忆）
   - **是什么**: Agent 主动将学到的稳定事实写入 `MEMORY.md` / `USER.md`
   - **作用**: 持久化用户偏好、环境事实、项目约定，改善未来会话的初始上下文
   - **示例**: "用户喜欢简洁代码" → 写入 USER.md → 下次会话自动遵循

2. **Session Archive 增长**（session archive = 会话归档）
   - **是什么**: 每次会话结束后，完整对话自动保存到 `state.db`（SQLite 数据库）
   - **作用**: 积累完整历史，支持按需回忆和搜索过去的对话
   - **示例**: "上次是怎么解决那个 bug 的？" → `session_search` → 找到相关会话

3. **Skill 沉淀**（skill = 技能）
   - **是什么**: Agent 将可复用的方法论保存为独立技能文件（SKILL.md）
   - **作用**: 把"怎么做"抽出来形成可加载资产，避免重复摸索
   - **示例**: "调试 Python import 错误的方法" → 保存为 skill → 下次直接应用

4. **Trajectory / Training Data 积累**（trajectory = 轨迹 / 训练数据）
   - **是什么**: 将会话转换为标准化的 ShareGPT 格式，保存到 JSONL 文件
   - **作用**: 为模型微调、错误分析、性能监控提供训练和研究数据
   - **示例**: 收集 1000 个成功对话 → 微调模型 → 提升整体性能

所以"进化"不是一个按钮，而是多个沉淀面并行发生。

### 5. 进化路径三：Skills

#### 5.1 为什么 skill 不应被混同为 memory

memory 解决的是：

- 记住什么

skill 解决的是：

- 下次怎么做

这两者显然相关，但不是一回事。

#### 5.2 Hermes 当前的工程策略

Hermes 的主线不是“自动无限生成 skills 并自我改写一切”，而是：

- 提供 `skill_manage`
- 提供 `skills_list` / `skill_view`
- 在 prompt 中鼓励 agent 将稳定方法论沉淀成 skill
- 在后台 memory/skill review 节点做机会性检查

这说明 Hermes 确实在朝 self-improving 方向走，但工程姿态更接近：

- 可控沉淀
- 工具显式化
- 允许 review / patch

而不是一个黑箱式“自动学习引擎”。

#### 5.3 什么时候该沉淀成 skill

适合 skill 的内容：

- 固定工作流
- 多步操作套路
- 特定技术栈最佳实践
- 某类任务的稳定模板

不适合 skill 的内容：

- 用户个人偏好
- 一次性 bug 细节
- 临时上下文

---

#### 5.4 Skill Telemetry 系统（底层实现）

**存储位置**: `~/.hermes/skills/.usage.json`

**数据结构**:
```json
{
  "debug-python": {
    "use_count": 15,
    "view_count": 42,
    "patch_count": 3,
    "last_used_at": "2026-05-01T10:30:00+00:00",
    "last_viewed_at": "2026-05-01T11:15:00+00:00",
    "last_patched_at": "2026-04-28T14:20:00+00:00",
    "created_at": "2026-04-15T09:00:00+00:00",
    "state": "active",
    "pinned": false,
    "archived_at": null
  },
  "web-scraping": {
    "use_count": 8,
    "view_count": 20,
    "patch_count": 1,
    "last_used_at": "2026-04-20T16:45:00+00:00",
    "last_viewed_at": "2026-04-25T08:30:00+00:00",
    "last_patched_at": "2026-04-16T12:00:00+00:00",
    "created_at": "2026-04-10T10:00:00+00:00",
    "state": "stale",
    "pinned": false,
    "archived_at": null
  }
}
```

**计数器更新逻辑**:

```python
## tools/skill_usage.py (第 314-336 行)

def bump_view(skill_name: str) -> None:
    """Bump view_count and last_viewed_at. Called from skill_view()."""
    def _apply(rec: Dict[str, Any]) -> None:
        rec["view_count"] = int(rec.get("view_count") or 0) + 1
        rec["last_viewed_at"] = _now_iso()
    _mutate(skill_name, _apply)


def bump_use(skill_name: str) -> None:
    """Bump use_count and last_used_at. Called when a skill is actively used."""
    def _apply(rec: Dict[str, Any]) -> None:
        rec["use_count"] = int(rec.get("use_count") or 0) + 1
        rec["last_used_at"] = _now_iso()
    _mutate(skill_name, _apply)


def bump_patch(skill_name: str) -> None:
    """Bump patch_count and last_patched_at. Called from skill_manage (patch/edit)."""
    def _apply(rec: Dict[str, Any]) -> None:
        rec["patch_count"] = int(rec.get("patch_count") or 0) + 1
        rec["last_patched_at"] = _now_iso()
    _mutate(skill_name, _apply)
```

**原子写入机制**:

```python
## tools/skill_usage.py (第 249-271 行)
def save_usage(data: Dict[str, Dict[str, Any]]) -> None:
    """Write the usage map atomically. Best-effort — errors are logged, not raised."""
    path = _usage_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), prefix=".usage_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())  # 确保数据刷到磁盘
            os.replace(tmp_path, path)  # 原子替换
        except BaseException:
            try:
                os.unlink(tmp_path)  # 失败时清理临时文件
            except OSError:
                pass
            raise
    except Exception as e:
        logger.debug("Failed to write %s: %s", path, e, exc_info=True)
```

**设计原则**:
- ✅ **Sidecar 模式**: 遥测数据与 SKILL.md 分离，避免污染用户内容
- ✅ **原子写入**: 使用 tempfile + os.replace 防止损坏
- ✅ **Best-effort**: 失败只记录日志，不影响工具调用
- ✅ **Provenance Filter**: 只追踪 agent-created skills，忽略 bundled/hub skills

---

#### 5.5 写入时机与执行流程

**触发位置**: 同样在主循环的工具调用分支中（[run_agent.py#L9323](file:///Users/gqli/work/deepagents/hermes-agent/run_agent.py#L9323)）

```python
## run_agent.py (第 9320-9324 行)
## Reset nudge counters
if function_name == "memory":
    self._turns_since_memory = 0
elif function_name == "skill_manage":
    self._iters_since_skill = 0  # 重置技能提示计数器
```

**执行流程**:

```mermaid
sequenceDiagram
    participant User as 用户
    participant LLM as LLM
    participant MainLoop as 主循环
    participant Tool as skill_manage
    participant FS as 文件系统
    participant Cache as Skills Cache
    participant Telemetry as .usage.json

    User->>LLM: 提出复杂任务
    LLM->>MainLoop: 返回 response + tool_calls
    
    alt 包含 skill_manage 调用
        MainLoop->>Tool: _invoke_tool("skill_manage", args)
        Tool->>Tool: 验证名称/解析 frontmatter
        Tool->>FS: 创建目录 + 写入 SKILL.md
        FS-->>Tool: 写入成功
        Tool->>Cache: clear_skills_system_prompt_cache()
        Tool->>Telemetry: bump_patch/bump_use (更新遥测)
        Telemetry-->>Tool: 更新成功
        Tool-->>MainLoop: {"success": true, "path": "..."}
        MainLoop->>LLM: 继续下一轮对话
    else 不包含 skill_manage 调用
        MainLoop->>LLM: 继续下一轮对话
    end
```

**关键特点**:
- ✅ **同步阻塞**: 工具执行完成后才继续下一轮对话
- ✅ **即时生效**: 写入后立即清除缓存，下次会话就能加载新技能
- ✅ **Agent 自主**: LLM 根据 `SKILLS_GUIDANCE` prompt 决定是否调用
- ✅ **遥测更新**: 同时更新 `.usage.json` 中的计数器

**实际示例**:

```
用户: "帮我调试这个 Python import 错误"

Agent: [执行 8 步调试流程]
       1. read_file("error.log")
       2. terminal("python -c 'import sys; print(sys.path)'")
       3. read_file("__init__.py")
       4. patch(path="__init__.py", ...)
       5. terminal("pytest tests/")
       6. read_file("test_output.log")
       7. patch(path="setup.py", ...)
       8. terminal("pytest tests/ -v")
       
       [成功解决，识别为可复用方法]
       
       {
         "role": "assistant",
         "tool_calls": [{
           "name": "skill_manage",
           "arguments": {
             "action": "create",
             "name": "debug-python-import",
             "content": "---\nname: debug-python-import\ndescription: ...\n---\n\n# Debug Python Import Errors\n\n## Steps\n1. Check error.log...\n..."
           }
         }]
       }

主循环: [执行 skill_manage 工具]
        → 验证名称格式（小写、连字符、≤64字符）
        → 解析 frontmatter
        → 检查同名冲突
        → 创建 ~/.hermes/skills/debug-python-import/
        → 写入 SKILL.md
        → 清除 Skills Cache
        → 更新 .usage.json (created_at, use_count=1)
        → 返回工具结果给 LLM

LLM: "我已将此调试方法保存为技能 'debug-python-import'，下次遇到类似问题可直接使用。"

[下次会话开始时]
→ skills_list() 返回新技能索引
→ skill_view("debug-python-import") 加载完整内容
→ Agent 应用此技能的方法论
```

---

#### 5.6 Skill 沉淀决策流程

```mermaid
graph TD
    Start[任务完成] --> Check1{是否复杂任务?<br/>5+ 工具调用}
    
    Check1 -->|否| End1[不创建 skill]
    Check1 -->|是| Check2{是否发现<br/>可复用方法?}
    
    Check2 -->|否| End2[不创建 skill]
    Check2 -->|是| Check3{是用户偏好<br/>还是通用方法?}
    
    Check3 -->|用户偏好| Memory[使用 memory 工具<br/>写入 MEMORY.md/USER.md]
    Check3 -->|通用方法| Check4{是否包含<br/>多步骤流程?}
    
    Check4 -->|否| Check5{是否是<br/>技术最佳实践?}
    Check4 -->|是| CreateSkill[skill_manage action=create]
    
    Check5 -->|否| End3[不创建 skill]
    Check5 -->|是| CreateSkill
    
    CreateSkill --> Review{是否需要<br/>review?}
    Review -->|是| Curator[后台 curator review]
    Review -->|否| Done[Skill 创建完成]
    
    Curator --> Approve{是否通过?}
    Approve -->|是| Done
    Approve -->|否| Patch[skill_manage action=patch]
    Patch --> Done
    
    style CreateSkill fill:#90EE90
    style Memory fill:#87CEEB
    style End1 fill:#FFB6C1
    style End2 fill:#FFB6C1
    style End3 fill:#FFB6C1
```

**决策要点**:
1. **复杂度检查**: 至少 5+ 工具调用，确保不是简单任务
2. **可复用性**: 方法是否能应用于未来类似场景
3. **分类判断**: 用户偏好 → memory，通用方法 → skill
4. **流程完整性**: 是否包含明确的步骤序列
5. **Review 机制**: 重要技能可能需要 curator 审核

---

#### 5.7 Skill 沉淀时序图

```mermaid
sequenceDiagram
    participant User as 用户
    participant Agent as Agent
    participant Tool as skill_manage
    participant FS as 文件系统
    participant Cache as Skills Cache
    participant Curator as Curator (可选)

    Note over Agent: 任务执行阶段
    User->>Agent: 提出复杂任务
    Agent->>Agent: 执行任务 (5+ tool calls)
    Agent->>Agent: 发现可复用方法
    
    Note over Agent: 决策阶段
    Agent->>Agent: 判断是否适合 skill
    alt 适合 skill
        Agent->>Tool: skill_manage(action="create", ...)
    else 不适合 skill
        Agent->>Agent: 跳过或使用 memory 工具
    end
    
    Note over Tool,FS: 创建阶段
    Tool->>Tool: 验证名称格式
    Tool->>Tool: 解析 frontmatter
    Tool->>FS: 检查同名冲突
    alt 无冲突
        Tool->>FS: 创建目录结构
        Tool->>FS: 写入 SKILL.md
        Tool->>Cache: clear_skills_system_prompt_cache()
        Tool-->>Agent: {"success": true, "path": "..."}
    else 有冲突
        Tool-->>Agent: {"success": false, "error": "..."}
    end
    
    Note over Agent,Curator: Review 阶段 (可选)
    alt 需要 review
        Agent->>Curator: 触发后台 review
        Curator->>Curator: 检查技能质量
        alt 通过
            Curator->>FS: 标记为 approved
        else 不通过
            Curator->>Agent: 返回修改建议
            Agent->>Tool: skill_manage(action="patch", ...)
        end
    end
    
    Note over Agent: 后续使用
    User->>Agent: 新任务
    Agent->>Cache: skills_list() / skill_view()
    Cache-->>Agent: 返回技能索引/内容
    Agent->>Agent: 应用技能方法
```

**关键节点说明**:

1. **任务执行阶段**: Agent 在执行复杂任务时识别模式
2. **决策阶段**: 根据复杂度、可复用性、分类进行判断
3. **创建阶段**: 
   - 验证名称（小写、连字符、≤64字符）
   - 解析 frontmatter（name, description, platforms等）
   - 检查冲突（同名技能已存在则失败）
   - 创建目录结构（`~/.hermes/skills/<category>/<name>/`）
   - 写入 SKILL.md
   - 清除缓存（触发 Skills Index 重建）
4. **Review 阶段**: 可选的 curator 审核流程
5. **后续使用**: 通过 `skills_list()` 和 `skill_view()` 加载技能

---

#### 5.8 Skill vs Memory 对比表

| 维度 | Skill | Memory |
|------|-------|--------|
| **解决的问题** | 下次怎么做（程序性记忆） | 记住什么（陈述性记忆） |
| **存储位置** | `~/.hermes/skills/<category>/<name>/SKILL.md` | `~/.hermes/memories/MEMORY.md` / `USER.md` |
| **内容类型** | 工作流、步骤、模板、最佳实践 | 用户偏好、环境事实、项目约定 |
| **容量** | 无限制（每个技能独立文件） | 有限（需保持精简） |
| **加载方式** | 按需加载（`skill_view()`） | 每轮自动注入（prefetch） |
| **更新频率** | 较低（稳定后很少修改） | 中等（持续精编） |
| **适用场景** | 固定工作流、多步操作套路 | 个人偏好、稳定经验 |
| **示例** | "Debug Python 的系统化方法" | "用户喜欢简洁的响应" |

**选择原则**:
- ✅ **问自己**: "这是关于'做什么'还是'怎么做'?"
  - 做什么（what）→ Memory
  - 怎么做（how）→ Skill
- ✅ **问自己**: "这个信息是一次性的还是会重复出现?"
  - 一次性 → Session Archive（state.db）
  - 重复出现 → Skill 或 Memory
- ✅ **问自己**: "这是一个通用的方法论还是个人的偏好?"
  - 通用方法论 → Skill
  - 个人偏好 → Memory

---

#### 5.9 所有进化机制的触发时机对比

| 机制 | 中文含义 | 主要作用 | 效果 | 触发位置 | 是否阻塞主循环 | 触发者 | 代码行号 |
|------|---------|---------|------|---------|--------------|--------|----------|
| **skill_manage** | 技能管理工具 | Agent 主动创建/更新可复用的方法论（SKILL.md） | 下次会话可直接应用该方法，避免重复摸索 | 主循环内（工具调用分支） | ✅ 是（同步） | Agent（LLM） | [run_agent.py#L9323](file:///Users/gqli/work/deepagents/hermes-agent/run_agent.py#L9323) |
| **memory 工具** | 记忆管理工具 | Agent 主动记录用户偏好、环境事实、项目约定 | 下次会话自动遵循这些偏好和事实 | 主循环内（工具调用分支） | ✅ 是（同步） | Agent（LLM） | [run_agent.py#L9321](file:///Users/gqli/work/deepagents/hermes-agent/run_agent.py#L9321) |
| **Session Archive** | 会话归档 | 会话结束后自动保存完整对话到 SQLite 数据库 | 支持通过 `session_search` 搜索过去的解决方案 | 主循环结束后 | ❌ 否（会后） | 运行时（自动） | [run_agent.py#L13613](file:///Users/gqli/work/deepagents/hermes-agent/run_agent.py#L13613) |
| **Trajectory Export** | 轨迹导出 | 将会话转换为 ShareGPT 格式保存到 JSONL 文件 | 为模型微调、错误分析、性能监控提供训练数据 | 主循环结束后 | ❌ 否（会后） | 运行时（自动） | [run_agent.py#L13607](file:///Users/gqli/work/deepagents/hermes-agent/run_agent.py#L13607) |
| **Curator Review** | 策展人审查 / 后台审查 | 定期自动检查并整合相似技能，保持技能库整洁 | 防止技能库膨胀，提升技能质量，节省用户整理时间 | 完全独立 | ❌ 否（异步） | 调度器（定时） | 独立进程 |

**关键结论**:

1. **Skill 和 Memory 的写入**确实在**主循环中**，由 Agent 主动调用工具触发
   - ✅ 同步阻塞：工具执行完成才继续
   - ✅ 即时生效：下次会话就能加载
   - ✅ Agent 自主：LLM 根据 prompt 决定是否调用

2. **Session Archive 和 Trajectory**在**主循环结束后**自动触发，不阻塞响应
   - ❌ 会后执行：不影响当前会话响应速度
   - ❌ 自动触发：无需 Agent 显式调用
   - ✅ 完整保存：包括所有 messages、tool calls、results

3. **Curator Review**是**完全独立的后台进程**，与主循环无关
   - ❌ 独立进程：不与用户交互
   - ❌ 异步执行：不影响当前会话
   - ✅ 定期触发：可配置间隔（默认 24h）

这种设计确保了：
- ✅ **即时反馈**: Skill/Memory 修改后立即生效
- ✅ **用户体验**: 会后操作不阻塞响应
- ✅ **系统稳定性**: 后台任务不影响前台交互

#### 5.7 Curator 自动生命周期管理

**配置文件**: `~/.hermes/config.yaml`

```yaml
curator:
  enabled: true
  interval_hours: 24          # 每 24 小时运行一次
  min_idle_hours: 2           # Agent 空闲至少 2 小时才运行
  stale_after_days: 30        # 30 天未使用标记为 stale
  archive_after_days: 90      # 90 天未使用自动归档
```

**状态机**:

```mermaid
stateDiagram-v2
    direction LR
    [*] --> Active: 创建 skill
    Active --> Stale: 超过 stale_after_days 未活动
    Stale --> Active: 重新使用
    Stale --> Archived: 超过 archive_after_days 未活动
    Archived --> [*]: 永久存档
    
    note right of Active
      pinned skills
      永不转换
    end note
```

**自动转换逻辑**:

```python
## agent/curator.py (第 215-255 行)
def apply_automatic_transitions(now: Optional[datetime] = None) -> Dict[str, int]:
    """Walk every agent-created skill and move active/stale/archived based on
    the latest real activity timestamp. Pinned skills are never touched."""
    from tools import skill_usage as _u

    if now is None:
        now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(days=get_stale_after_days())
    archive_cutoff = now - timedelta(days=get_archive_after_days())

    counts = {"marked_stale": 0, "archived": 0, "reactivated": 0, "checked": 0}

    for row in _u.agent_created_report():
        counts["checked"] += 1
        name = row["name"]
        if row.get("pinned"):
            continue  # Pinned skills 永不转换

        # 获取最新活动时间（use/view/patch 的最新时间）
        last_activity = _parse_iso(row.get("last_activity_at"))
        # 如果从未活动，使用 created_at 作为锚点
        anchor = last_activity or _parse_iso(row.get("created_at")) or now
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)

        current = row.get("state", _u.STATE_ACTIVE)

        # 判断是否需要归档
        if anchor <= archive_cutoff and current != _u.STATE_ARCHIVED:
            ok, _msg = _u.archive_skill(name)
            if ok:
                counts["archived"] += 1
        # 判断是否需要标记为 stale
        elif anchor <= stale_cutoff and current == _u.STATE_ACTIVE:
            _u.set_state(name, _u.STATE_STALE)
            counts["marked_stale"] += 1
        # 判断是否需要重新激活
        elif anchor > stale_cutoff and current == _u.STATE_STALE:
            _u.set_state(name, _u.STATE_ACTIVE)
            counts["reactivated"] += 1

    return counts
```

**归档实现**:

```python
## tools/skill_usage.py (第 376-420 行)
def archive_skill(skill_name: str) -> Tuple[bool, str]:
    """Move an agent-created skill directory to ~/.hermes/skills/.archive/."""
    if not is_agent_created(skill_name):
        return False, f"skill '{skill_name}' is bundled or hub-installed; never archive"

    skill_dir = _find_skill_dir(skill_name)
    if skill_dir is None:
        return False, f"skill '{skill_name}' not found"

    archive_root = _archive_dir()  # ~/.hermes/skills/.archive/
    try:
        archive_root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return False, f"failed to create archive dir: {e}"

    # 扁平化目录结构（忽略 category 嵌套）
    dest = archive_root / skill_dir.name
    if dest.exists():
        # 如果目标已存在，添加时间戳避免冲突
        dest = archive_root / f"{skill_dir.name}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    try:
        shutil.move(str(skill_dir), str(dest))
        set_state(skill_name, STATE_ARCHIVED)
        return True, f"archived to {dest}"
    except OSError as e:
        return False, f"failed to move: {e}"
```

**恢复技能**:

```bash
## CLI 命令
hermes curator restore <skill-name>

## 底层实现
mv ~/.hermes/skills/.archive/<skill-name> ~/.hermes/skills/<skill-name>
```

**设计原则**:
- ✅ **Pinned Skills 保护**: 标记为 pinned 的技能永远不会被自动归档
- ✅ **Provenance Filter**: 只管理 agent-created skills，忽略 bundled/hub skills
- ✅ **可逆操作**: 归档不是删除，可以随时恢复
- ✅ **渐进式降级**: Active → Stale → Archived，给用户多次机会

#### 5.10 三种进化机制的生命周期管理对比

| 机制 | 是否需要过期 | 是否需要错误更正 | 管理方式 |
|------|------------|----------------|---------|
| **Skills** | ✅ 是（避免膨胀） | ✅ 是（方法过时） | Curator Review 自动整理 + 用户手动 pin/unpin |
| **Session Archive** | ❌ 否（永久保存） | ❌ 否（历史记录） | 无需管理，按需搜索 |
| **Curated Memory** | ❌ 否（人工控制） | ✅ 是（事实变更） | Agent 主动更新 + 用户手动编辑 |

**关键差异**:

1. **Skills 需要自动整理**:
   - 原因：Agent 可能创建大量狭窄技能，导致技能库混乱
   - 解决：Curator Review 定期合并相似技能，归档过时技能

2. **Session Archive 不需要管理**:
   - 原因：历史记录永远有价值，存储成本低
   - 解决：通过索引和搜索提高效率，不删除任何数据

3. **Curated Memory 需要人工策展**:
   - 原因：容量有限（<5KB），需要保持高信噪比
   - 解决：Agent 主动更新 + 用户手动编辑，不依赖自动化

#### 6.1 它属于什么层

Trajectory（轨迹）是训练和研究资产，不是在线 recall memory。

它的目标不是改善“当前这次会话”的上下文，而是：

- 生成可分析的对话轨迹
- 为 RL / fine-tuning / evaluation 准备数据

#### 6.2 为什么它不该算进 memory 主模型

因为它既不参与日常 prompt 注入，也不承担用户级 recall。

它更多是：

- 离线资产
- 训练输入
- 研究数据

把它硬塞进“memory 层级”会导致概念膨胀。

#### 6.3 但为什么仍值得放在这里讲

因为 Hermes 的品牌叙事不是“有记忆就够了”，而是：

- 记住
- 复盘
- 沉淀
- 再学习

所以 trajectory 虽不是 memory 主层，但确实是长期进化闭环的一部分。

---

#### 6.4 Trajectory 导出的底层实现

**存储格式**: JSONL（每行一个完整的会话）

**输出文件**:
- `trajectory_samples.jsonl`: 成功完成的会话
- `failed_trajectories.jsonl`: 失败或中断的会话

**触发位置**: 在主循环结束后（[run_agent.py#L13607](file:///Users/gqli/work/deepagents/hermes-agent/run_agent.py#L13607)）

```python
## run_agent.py (第 13607 行)
## Save trajectory if enabled
self._save_trajectory(messages, _summarize_user_message_for_log(user_message), completed)
```

**执行流程**:

```mermaid
sequenceDiagram
    participant User as 用户
    participant MainLoop as 主循环
    participant Exporter as _save_trajectory
    participant File as JSONL file

    User->>MainLoop: 提出任务
    MainLoop->>MainLoop: 执行多轮对话
    
    alt 会话结束
        MainLoop->>Exporter: _save_trajectory(messages, completed)
        Exporter->>Exporter: 转换为 ShareGPT 格式
        Exporter->>File: append JSON entry
        File-->>Exporter: 写入成功
        Exporter-->>MainLoop: 导出完成
        MainLoop->>User: 返回最终响应
    end
```

**数据结构**（ShareGPT 格式）:

```json
{
  "conversations": [
    {
      "from": "human",
      "value": "帮我修复这个 Python bug"
    },
    {
      "from": "gpt",
      "value": "<think>\n我需要先查看错误信息...\n</think>\n\n让我检查一下日志。",
      "tool_calls": [
        {
          "id": "call_abc123",
          "type": "function",
          "function": {
            "name": "read_file",
            "arguments": "{\"file_path\": \"error.log\"}"
          }
        }
      ]
    },
    {
      "from": "tool",
      "name": "read_file",
      "content": "Traceback (most recent call last):\n  ...",
      "tool_call_id": "call_abc123"
    },
    {
      "from": "gpt",
      "value": "我找到了问题所在..."
    }
  ],
  "timestamp": "2026-05-01T10:30:00+00:00",
  "model": "claude-3-opus-20240229",
  "completed": true
}
```

**导出逻辑**:

```python
## agent/trajectory.py (第 30-57 行)
def save_trajectory(trajectory: List[Dict[str, Any]], model: str,
                    completed: bool, filename: str = None):
    """Append a trajectory entry to a JSONL file."""
    if filename is None:
        filename = "trajectory_samples.jsonl" if completed else "failed_trajectories.jsonl"

    entry = {
        "conversations": trajectory,
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "completed": completed,
    }

    try:
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info("Trajectory saved to %s", filename)
    except Exception as e:
        logger.warning("Failed to save trajectory: %s", e)
```

**调用时机**: 在 `batch_runner.py` 中，每个会话结束后自动调用

```python
## batch_runner.py (简化版)
def run_batch_session(agent, task: str) -> None:
    """Run a single session and save trajectory."""
    messages = []
    
    # 执行会话
    response = agent.run(task, messages=messages)
    
    # 转换为 ShareGPT 格式
    trajectory = agent._convert_to_trajectory_format(messages)
    
    # 保存轨迹
    completed = response.status == "completed"
    save_trajectory(
        trajectory=trajectory,
        model=agent.model_name,
        completed=completed
    )
```

**Scratchpad 转换**:

```python
## agent/trajectory.py (第 16-21 行)
def convert_scratchpad_to_think(content: str) -> str:
    """Convert <REASONING_SCRATCHPAD> tags to <think> tags."""
    if not content or "<REASONING_SCRATCHPAD>" not in content:
        return content
    return content.replace("<REASONING_SCRATCHPAD>", "<think>").replace("</REASONING_SCRATCHPAD>", "</think>")
```

**用途**:
- 📊 **微调数据集**: 用于 SFT（Supervised Fine-Tuning）
- 🧪 **评估基准**: 构建任务特定的 eval suite
- 🔍 **错误分析**: 研究失败模式和改进方向
- 📈 **性能监控**: 追踪 token 使用、成本、成功率等指标

**设计原则**:
- ✅ **完整保留**: 包括 tool calls/results、thinking process
- ✅ **标准化格式**: ShareGPT 兼容，便于与其他框架互操作
- ✅ **增量追加**: JSONL 格式支持流式写入，无需加载整个文件
- ✅ **分离成败**: 成功和失败的轨迹分开存储，便于针对性分析

---

#### 7.1 Curator Review（策展人审查）机制（LLM 驱动的技能整合）

**触发位置**: ❌ **完全独立，不在主循环中**

**审查范围**: ⚠️ **仅针对 Skills（技能），不包括 Session Archive 和 Curated Memory**

> **重要说明**: Curator Review 的职责是**技能库的整理和优化**，不负责 Session Archive 和 Curated Memory 的生命周期管理。
>
> - **Session Archive**: 永久保存，不过期，用户可通过 `session_search` 按需搜索
> - **Curated Memory**: 由 Agent 在对话中主动更新，无自动过期机制
> - **Skills**: 需要定期整理，避免膨胀，因此引入 Curator Review

**触发条件**:
1. **定时触发**: 每 `interval_hours` 小时检查一次（默认 24h）
2. **空闲检测**: Agent 必须空闲至少 `min_idle_hours` 小时（默认 2h）
3. **手动触发**: `hermes curator run --now`

**审查内容**:
- ✅ **技能整合**: 识别相似技能，合并为 umbrella skill
- ✅ **技能归档**: 将过时/狭窄的技能移动到 `.archive/`
- ✅ **技能质量**: 检查技能名称是否过窄（包含 PR 号、具体错误字符串等）
- ❌ **Session Archive**: 不处理（永久保存）
- ❌ **Curated Memory**: 不处理（由 Agent 主动更新）

> **Curator = 策展人 / 管理员**：负责后台自动审查和整合技能的专用 agent。

**执行流程**:

```mermaid
sequenceDiagram
    participant Scheduler as 调度器
    participant Checker as 空闲检测
    participant ForkedAgent as Forked Agent
    participant Tools as skill_manage/skills_list
    participant FS as 文件系统
    participant Usage as .usage.json

    loop 每小时检查
        Scheduler->>Checker: should_run_now()
        Checker->>Checker: 检查 enabled/paused/interval/idle
        
        alt 满足条件
            Checker-->>Scheduler: True
            Scheduler->>ForkedAgent: 启动 forked agent
            ForkedAgent->>Tools: skills_list() 获取所有技能
            Tools-->>ForkedAgent: 返回技能列表 + 遥测数据
            
            ForkedAgent->>ForkedAgent: 识别 PREFIX CLUSTERS
            loop 每个 cluster (2+ skills)
                ForkedAgent->>ForkedAgent: 判断是否需要 umbrella
                alt 需要整合
                    ForkedAgent->>Tools: skill_manage(action="create"/"patch")
                    Tools->>FS: 创建/修改 SKILL.md
                    FS-->>Tools: 成功
                    Tools-->>ForkedAgent: {"success": true}
                    
                    ForkedAgent->>Tools: skill_manage(action="write_file")
                    Tools->>FS: 添加 references/templates/scripts
                    FS-->>Tools: 成功
                    
                    ForkedAgent->>Usage: archive_skill(sibling_name)
                    Usage->>FS: mv ~/.hermes/skills/<sibling> .archive/
                    FS-->>Usage: 成功
                    Usage-->>ForkedAgent: {"success": true}
                else 不需要整合
                    ForkedAgent->>ForkedAgent: 跳过
                end
            end
            
            ForkedAgent->>ForkedAgent: 生成结构化 YAML 报告
            ForkedAgent->>Scheduler: 返回总结报告
            Scheduler->>Scheduler: 更新 last_run_at
        else 不满足
            Checker-->>Scheduler: False
            Scheduler->>Scheduler: 等待下次检查
        end
    end
```

**关键特点**:
- ❌ **独立进程**: 不与用户交互
- ❌ **异步执行**: 不影响当前会话响应速度
- ✅ **定期触发**: 可配置间隔（默认 24h）
- ✅ **空闲检测**: 只在 Agent 空闲 ≥2h 时运行

> （完整 Curator Review 时序见上一节 mermaid，此处不重复。）



**Review Prompt 核心要求**:

```python
## agent/curator.py (第 262-350 行，简化版)
CURATOR_REVIEW_PROMPT = (
    "你是 Hermes 的后台技能 CURATOR。这是一个 UMBRELLA-BUILDING consolidation pass，"
    "不是被动审计，也不是重复查找器。\n\n"
    
    "目标：构建一个 CLASS-LEVEL INSTRUCTIONS AND EXPERIENTIAL KNOWLEDGE 库。"
    "数百个狭窄技能的集合（每个只捕获一次会话的特定 bug）是库的失败 —— "
    "不是特性。\n\n"
    
    "硬性规则:\n"
    "1. 不要触碰 bundled 或 hub-installed skills\n"
    "2. 不要删除任何技能。归档（移动到 .archive/）是最大破坏性操作\n"
    "3. 不要触碰 pinned=yes 的技能\n"
    "4. 不要使用 usage counters 作为跳过整合的理由。基于 CONTENT 判断重叠\n"
    "5. 不要因为 '每个技能有不同的 trigger' 而拒绝整合\n\n"
    
    "工作方法:\n"
    "1. 扫描候选列表，识别 PREFIX CLUSTERS（共享首词或领域关键词的技能）\n"
    "2. 对于每个 2+ 成员的 cluster，问：'这些技能服务的 UMBRELLA CLASS 是什么？'\n"
    "3. 三种整合方式:\n"
    "   a. MERGE INTO EXISTING UMBRELLA — patch 现有技能，添加 labeled section\n"
    "   b. CREATE A NEW UMBRELLA SKILL.md — create 新的 class-level skill\n"
    "   c. DEMOTE TO REFERENCES/TEMPLATES/SCRIPTS — move to support directories\n"
    "4. 标记名称过窄的技能（包含 PR 号、feature codename、具体错误字符串）\n"
    "5. 迭代。一轮整合后，扫描剩余集寻找下一个 umbrella 机会\n"
)
```

**结构化输出格式**:

```yaml
## Curator 必须在响应中包含此 YAML block
consolidations:
  - from: "debug-python-import-error"
    into: "debug-python"
    reason: "Import errors are a subset of general Python debugging"
  - from: "debug-python-type-error"
    into: "debug-python"
    reason: "Type errors belong under the same umbrella"

prunings:
  - name: "fix-pr-12345"
    reason: "Session-specific PR fix, too narrow for a standalone skill"
  - name: "audit-gateway-config-2024"
    reason: "Dated audit artifact, content absorbed into hermes-config umbrella"
```

**解析与执行**:

```python
## agent/curator.py (第 509-587 行)
def _parse_structured_summary(llm_final: str) -> Dict[str, List[Dict[str, str]]]:
    """Extract the structured YAML block from the curator's final response."""
    import re
    match = re.search(r"```ya?ml\s*\n(.*?)\n```", llm_final, re.DOTALL | re.IGNORECASE)
    if not match:
        return {"consolidations": [], "prunings": []}
    
    body = match.group(1)
    try:
        import yaml
        data = yaml.safe_load(body)
    except Exception:
        return {"consolidations": [], "prunings": []}
    
    # 解析 consolidations 和 prunings 列表
    out = {"consolidations": [], "prunings": []}
    # ... 详细解析逻辑 ...
    return out
```

**启发式回退**:

如果 LLM 未能生成有效的 YAML，Curator 会使用工具调用证据进行启发式分类：

```python
## agent/curator.py (第 401-506 行)
def _classify_removed_skills(
    removed: List[str],
    added: List[str],
    after_names: Set[str],
    tool_calls: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Split removed into consolidated vs pruned using tool-call evidence.
    
    Heuristic: scan skill_manage tool calls and look for write_file/patch/create/edit
    actions whose target skill references the removed skill's name.
    """
    # ... 详细实现 ...
```

**设计原则**:
- ✅ **LLM 驱动**: 利用 LLM 的语义理解能力识别技能重叠
- ✅ **双重保障**: 结构化 YAML + 启发式回退
- ✅ **非破坏性**: 只归档，不删除，随时可恢复
- ✅ **透明报告**: 每次 review 生成详细的 YAML 报告

---

<a id="e-附录六层视角与演进表述"></a>

## E. 附录 A：六层扩展视角

> **非官方主模型。** 仅用于架构对比；对外叙事请用三层。

### 2.1 六层扩展视角（架构分析用 · 非官方主模型）

> ⚠️ 下图将 skills、compression、trajectory 与 runtime memory **画在同一塔里**，便于和 OpenHarness / deer-flow 对比。**运行时主 API 仍以 §2.2 三层为准。**

Hermes 在**扩展分析**中常用六层叙事,从持久化到训练数据逐层递进:

```mermaid
graph TB
    subgraph L6["L6: 训练数据层 Trajectory"]
        T1[ShareGPT 格式导出]
        T2[模型微调数据集]
        T3[RL 轨迹数据]
    end
    
    subgraph L5["L5: 压缩摘要层 Compression"]
        C1[Context Compressor]
        C2[会话分割 parent_session_id]
        C3[降低训练成本]
    end
    
    subgraph L4["L4: 冻结提示 MEMORY/USER.md"]
        M1[MEMORY.md<br/>项目约定/环境事实]
        M2[USER.md<br/>用户偏好/工作风格]
        M3[Frozen Snapshot<br/>会话启动时加载]
    end
    
    subgraph L3["L3: 工作记忆 Context Window"]
        W1[当前 messages 列表]
        W2[Tool Loop 状态]
        W3[临时推理链]
    end
    
    subgraph L2["L2: 情景记忆 Session Archive"]
        S1[state.db<br/>SQLite + FTS5]
        S2[session_search 工具]
        S3[历史会话召回]
    end
    
    subgraph L1["L1: 程序记忆 Skills"]
        P1[skills/ 目录<br/>SKILL.md]
        P2[skill_view 工具]
        P3[自进化机制]
    end
    
    subgraph External["外部增强层 Optional Provider"]
        E1[Honcho / Mem0 / Hindsight]
        E2[语义召回]
        E3[User Modeling]
    end
    
    L6 -.->|离线分析| L5
    L5 -->|压缩触发| L4
    L4 -->|冻结注入| L3
    L3 -->|每轮更新| L2
    L2 -->|按需搜索| L3
    L1 -->|渐进披露| L3
    External -->|prefetch/sync| L3
    
    style L1 fill:#e1f5ff
    style L2 fill:#fff4e1
    style L3 fill:#ffe1f5
    style L4 fill:#e1ffe1
    style L5 fill:#f5e1ff
    style L6 fill:#ffe1e1
    style External fill:#f0f0f0
```

**各层职责**:

| 层级 | 载体 | 读写频率 | 典型用途 | 示例 |
|------|------|---------|---------|------|
| **L1 程序记忆** | `skills/*.md` | 低频写/高频读 | 方法论沉淀、可复用工作流 | `code-review`, `debug-python` |
| **L2 情景记忆** | `state.db` (FTS5) | 每次会话写/按需读 | 完整历史档案、跨会话召回 | "上周修过某个 auth bug" |
| **L3 工作记忆** | `messages` 列表 | 每轮读写 | 当前对话上下文、工具调用链 | 本轮的 reasoning + tool results |
| **L4 冻结提示** | `MEMORY.md`/`USER.md` | 手动写/会话启动读 | 稳定事实、用户偏好、项目约定 | "用户喜欢简洁回答" |
| **L5 压缩摘要** | parent_session_id 链 | 阈值触发 | 降低上下文长度、训练成本控制 | 长会话分割为父子链 |
| **L6 训练数据** | ShareGPT JSONL | 批量导出 | 模型微调、RL 训练 | `trajectory_compressor.py` |
| **External** | Honcho/Mem0 API | 每轮 prefetch/sync | 语义召回、深度用户建模 | 向量数据库检索 |

### 2.2 三层主模型 vs 六层扩展

> **重要澄清**: 正文 §1–§6 聚焦**三层主模型**(Persistent Memory + Session Search + External Provider),这是 Hermes memory 的核心运行时。
>
> L1/L5/L6 属于**扩展沉淀机制**,与 skills/trajectory/compression 专题交叉,在 [附录 D · 扩展机制](#d-扩展机制skills--curator--trajectory) 中详述。

## E. 附录 B：演进表述与时序

### 8. 一个更准确的演化时序图

```mermaid
graph TD
    U[User interaction] --> A[Current session]

    A --> B{What was learned?}

    B -->|Stable fact / preference| C[memory tool]
    B -->|Past task detail worth recalling later| D[state.db]
    B -->|Reusable workflow / method| E[skill_manage]
    B -->|Training / evaluation asset| F[trajectory]

    C --> G[MEMORY.md / USER.md]
    D --> H[session_search recall]
    E --> I[skills]
    F --> J[offline analysis / RL / fine-tuning]
```

这个图比“六层塔”更忠实于当前工程现实。

---

### 9. 对“Hermes 会自我进化”的准确表述

建议把这个说法写得更稳一些。

可以写：

- Hermes 具备 **持续沉淀经验** 的机制
- 它通过 curated memory（精选记忆）、session archive（会话归档）、skills（技能）和 training assets（训练资产）形成多条学习路径
- 一部分进化由 agent 主动触发，一部分由用户或离线流程显式管理

不建议继续写成：

- “Hermes 有一个统一六层自进化记忆引擎”

因为这会把太多不同子系统强行归到一个抽象里。

---


### 11. 最后给架构对比使用者的结论

如果你在跨框架对比 Hermes memory，最稳妥的说法应该是：

- Hermes 的 **主记忆模型** 是三层：
  built-in persistent memory（内置持久化记忆）、session search（会话搜索）、optional external provider（可选外部提供者）
- Hermes 的 **长期进化机制** 另外包括：
  skills（技能）、curator review（策展人审查 / 后台审查）、trajectory/training assets（轨迹 / 训练资产）

这个表述既能保住 Hermes 的优势，也更经得起源码核对。

