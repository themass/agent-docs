# ADR-004：以智能体为中心的分层架构与横切增强点

- **状态**：Accepted
- **日期**：2026-10-17

## Context

JC 的本质是**简历优化智能体**，不是「带几个模型调用的 CRUD 应用」。但代码里一度出现了与这个定位相反的结构问题，而且是**反复**出现：

1. `jc.services` 与 `jc.mcp` **互相 import**，形成真实循环依赖。它没有在启动时炸掉，只是因为有一半 import 被写在函数体内，Python 解析得足够晚。
2. `jc.llm`（模型传输层）要 import `jc.services.llm_log_service` 才能记审计日志——基础设施依赖业务编排，方向颠倒。
3. `jc.skills.composer`（prompt 组装）与 `jc.services.role_families`（岗位方法论）互相依赖。
4. 多模态的 OpenAI `image_url` 线格式在两个地方各手写一份，各自做 base64。
5. 角色的工具权限（`_SKILL_SCOPE`）是 DeerFlow 传输适配器里的私有变量，管理后台要 import 下划线私有名才能回答「这个角色能做什么」。

共同点不是「某个文件写坏了」，而是**没有一条写下来的、可以被检查的层次契约**。评审能抓到第一次，抓不到第三次。

## Decision

### 1. 分层与依赖方向（单向，不可逆转）

```text
        ┌──────────────────────────────────────┐
        │  api/        HTTP/SSE 入站适配器      │
        │  mcp/        Agent 工具入站适配器     │   ← 入站：谁都可以调它，它不是任何人的依赖
        └──────────────┬───────────────────────┘
                       │
        ┌──────────────▼───────────────────────┐
        │  services/   业务编排（有状态、有 I/O）│
        └──────────────┬───────────────────────┘
                       │
   ┌───────────────────┼──────────────────┬─────────────────┐
   │                   │                  │                 │
┌──▼──────┐    ┌───────▼──────┐   ┌───────▼──────┐  ┌───────▼──────┐
│ agent/  │    │   skills/    │   │    llm/      │  │   stores/    │
│ 角色、   │    │ prompt 组装  │   │ 路由/传输/   │  │  持久化      │
│ 工具目录 │    │              │   │ 审计/多模态  │  │              │
└──┬──────┘    └───────┬──────┘   └───────┬──────┘  └───────┬──────┘
   │                   │                  │                 │
   └───────────────────┴────────┬─────────┴─────────────────┘
                                │
                   ┌────────────▼─────────────┐
                   │ domain/   纯方法论，零 I/O │
                   │ authz/    归属守卫        │
                   │ models/ schemas/ config/  │
                   └──────────────────────────┘

   diagnostics/  读所有层，没有任何层依赖它
```

硬规则：

- **入站适配器永远不是依赖。** `services/` 不得 import `mcp/`、`api/`、`diagnostics/`。一次工具调用、一次 HTTP 请求、一个脚本都只是调用方。
- **`llm/` 是基础设施**，不得 import `services/`、`agent/`、`mcp/`。审计日志属于 `llm/call_log.py`。
- **`domain/` 零 I/O**：不得出现 sqlalchemy / redis / litellm / httpx。它只放数据和纯函数（岗位 playbook、结构规则、评分启发式），这样 `services/` 和 `skills/` 都能依赖它而不必互相依赖。
- **`authz/` 在所有需要鉴权的层之下**。`RunScope` 不是 MCP 类型：工具调用、HTTP 处理和离线脚本需要的是同一个「我是谁、绑定哪份档案、从哪个 session 写」。
- **`diagnostics/` 只读不被读**。管理后台的清单天然要横跨所有层，这个宽度对运维报表是对的，对业务服务是错的。

这些规则由 `backend/server/tests/test_architecture_layers.py` **强制执行**，不是靠评审。它用 AST 遍历全树，**包括函数体内的 import**——因为上一次的循环正是靠函数内 import 藏住的。失败时正确的做法几乎永远是把代码挪到允许持有它的层，而不是改测试。

### 1.1 仓库布局只有一个所有者：`jc/paths.py`

**任何层都可以 import `jc.paths`**，因为它只做路径计算，不 import 任何 `jc` 模块。它不在分层图里是因为它在分层图下面。

这条规则是从一个真实缺陷里长出来的，值得记下来：同一份布局知识曾经被 11 处代码用 4 种写法各自重算（`parents[2]`、`parents[3]`、`parents[2].parent`、`parents[3].parent`），其中 `llm/router.py` 少算了一层，把「server 根目录」解析成了 `src/`。后果是：

- `ensure_dotenv_loaded()` 找不到 `.env`，静默 return，**从来没真正加载过**；
- `routing.yaml` 只能靠**兜底候选**命中，所以进程**必须从 `backend/server` 启动**；从任何其他目录启动就 `FileNotFoundError`。

为什么这个 bug 能活这么久：**三处降级全是静默的**。缺 `.env` 不报错，缺 prompt 得到空字符串，缺 skill 目录得到空列表。更糟的是它让两个测试「因为错误的原因通过」——那两个测试 `delenv("JC_LLM_API_KEY")` 来断言「这个端点没配」，而真实的 `.env` 从未被加载，所以断言永远成立。修好路径之后它们立刻红了。

所以现在的约束是三条，每一条都对应上面的一种失效方式：

| 约束 | 实现 | 防的是哪种失效 |
|---|---|---|
| 根目录按**名字**自证 | `paths.py` 导入时 `assert SERVER_ROOT.name == "server"` | `parents[]` 索引算错。读代码看不出差一层，只有问「这个目录叫什么」才能发现 |
| 配置路径按 server 根解析，不按 cwd | `resolve_under_server(raw)` | `JC_SKILLS_ROOT` 这类设置默认写成 `../agent/...`，裸 `Path()` 会相对**当前工作目录**解析 |
| 代码里不得再出现 `parents[` | `tests/test_paths.py::test_layout_knowledge_is_not_recomputed_outside_paths_module` | 第 12 处重算。只豁免 `paths.py` 与 `config.py`（后者不能 import settings 以外的东西） |

`tests/test_paths.py` 还逐个断言代码里引用的 10 个 agent 资产真实存在，并在 `tmp_path` 下 `chdir` 后重新加载 router 与 skills —— 即「从任意目录启动」这条，是被测试守住的，不是被约定守住的。

另外两条相关的约定：

- **测试不读开发者的 `.env`。** `tests/conftest.py` 有一个 autouse fixture 把 `ensure_dotenv_loaded` 置空。否则「断言某个 key 没配」的测试结果取决于跑测试的机器上有没有配网关——CI 绿、本机红，两边都证明不了什么。
- **alembic 版本文件豁免 E501**（`pyproject.toml` 的 per-file-ignores）。生成的列定义重排后就没法和产出它的 model 对照 diff 了，而那里的长行从未藏过缺陷。除行宽之外的规则照旧强制。豁免这 75 条之后 `ruff check` 整仓干净，lint 输出才重新有人看。

### 2. 智能体的三个横切增强点（新增横切功能只能落在这三处）

我们是智能体产品，所以增强手段应该是 **hook / 中间件 / 拦截器**，而不是在业务代码里东插一段：

| 层 | 机制 | 位置 | 适合做什么 |
|---|---|---|---|
| 模型调用 | LiteLLM callback + 响应校验 | `jc/llm/audit_hook.py`、`jc/llm/transport.py` 的 `validation_scope` | 审计、计费、token 统计、失败降级、拒答后触发 failover |
| Agent 轮次 | `AgentMiddleware.before_agent` | `jc/deerflow_middleware.py` 的 `JCProductRulesMiddleware` | 注入产品规则、会话上下文、回复语言 |
| 工具调用 | `interceptor(request, handler)` | `jc/mcp/interceptors.py` | 调用前后的门禁，如导出前审稿 |

**不要引入第四种机制。** 需要新的横切能力时，先判断它属于「每次模型调用」「每个 agent 轮次」还是「每次工具调用」，然后扩展对应那一层。

### 3. 权限边界由签名保证，不由参数过滤保证

档案 patch 原来是**一个**函数带 `apply: bool`，靠工具分发器记得把模型传来的 `apply` 摘掉。漏掉一次 `pop` 就是一次确认绕过。

现在拆成两个服务函数：

- `propose_patch(...)` —— 只写待确认记录，是工具层能够到的唯一入口；
- `apply_confirmed_patch(..., confirm_id=)` —— 真正落库，唯一调用方是确认接口。

工具层不 import 后者，所以**不存在一个模型能传的参数会导致写入**。ADR-003 的边界从此写在类型签名里，而不是写在一个 if 分支里。

### 4. 多模态只有一个线格式所有者

`jc/llm/vision.py` 独占 OpenAI 多模态 content 的构造：`ImageRef` 是图片进入系统的唯一方式（上传字节或浏览器 `data:` URL），`image_part` / `build_vision_content` 拥有线格式，`describe_image` 负责「图 → 文」给纯文本下游。路由、重试、failover、审计一律仍走 `LLMRouter` 的 `vision` scenario。

## 已解决：身份不再经进程环境变量传递（原「全进程串行」事故）

**历史问题（已修复，record 保留供回溯）：** `adapters/deerflow_harness_client.py` 曾用 `_HARNESS_RUN_LOCK` 把**整轮对话**串行化，因为会话身份（`JC_MCP_USER_ID` / `JC_MCP_PROFILE_ID` / `JC_MCP_SESSION_ID` 等）是写进 `os.environ`、再被 `deerflow_middleware` 与 `mcp/interceptors` 读回来的——而内嵌的 MCP stdio 子进程是进程全局、跨用户复用的连接池（`deerflow.mcp.session_pool`），环境变量只在子进程 spawn 那一刻生效，之后是全进程可变状态，一个用户的身份可能在下一个用户的请求到达前被覆写。锁掩盖的是这个越权风险，不是单纯的性能权衡。

**现状：身份作为显式参数随每次调用传递，不再有进程级锁。**

- `DeerFlowClient.stream(...)` 的 `authz_attributes` 关键字参数（DeerFlow 官方预留的请求级业务属性字典）承载 `jc_profile_id` / `jc_session_id` / `jc_job_id` / `jc_mock_session_id` / `jc_agent_skill` / `jc_reply_locale`，经 `_EMBEDDED_AUTHORIZATION_CONTEXT_KEYS` 白名单进入 LangGraph `context`，`runtime.context["authz_attributes"]` 对单次调用是只读、不可被其他并发调用篡改的。`user_id` 走 DeerFlow 自带的 `user_id` 参数与 `resolve_runtime_user_id` 解析链路。
- `jc` MCP 工具的 `jc_user_id` / `jc_profile_id` / `jc_session_id` / `jc_job_id` / `jc_mock_session_id` 作为普通工具参数出现在 schema 里（FastMCP 没有「声明参数但对模型隐藏」的机制），但服务端从不信任模型填的值——`jc.mcp.identity_interceptor` 在请求到达 `jc.mcp.server` 前，用 `request.override(args=...)` 把这几个字段强制覆写成从 `runtime.context["authz_attributes"]` 解析出的真实值。模型填什么都会被覆盖，这是标准的「服务端用会话态覆盖客户端输入」，不是「藏参数」。
- `deerflow_middleware.py` 的 `JCProductRulesMiddleware` 同样从 `runtime.context["authz_attributes"]` 读取，不再读任何 `JC_MCP_*` / `JC_AGENT_*` 环境变量。
- `_HARNESS_RUN_LOCK`、`_acquire_run_slot`、`release_run_slot`、`harness_queue_depth`、排队可见性事件（`queued`）均已删除——这些都是为锁的存在而建的基础设施，锁消失后它们本身失去意义。**跨用户不再有全进程排队**，只剩「同一用户同一会话内」的 `followUpQueue` / `steerQueue`（前端 `useAgentSession` 的正确行为，防止同一份档案被两轮并行覆盖，与本节无关）。
- `_CLIENT_CACHE` 里缓存的内嵌 client 仍是进程级、按 `(extensions_config_path, checkpoint_dsn, available_skills)` 为 key 复用的——这是安全的，因为 key 本身不含身份，`available_skills` 是构造时固定的集合（`_available_skills`），不再有运行期可变的 `_jc_skill` 实例属性。

角色独立成包仍是下一步演化方向：目标形态是「每个角色有自己的 soul + 专属 skill + 专属工具面」，`agent/roles.py` 的 `SKILL_SCOPE` 是这个方向的第一步。如果 DeerFlow 挡住这个形态，换 harness 的判断依据是它，而不是别的。

## Consequences

- 新增横切功能必须落在三个增强点之一，否则评审直接退回。
- 新增层必须同时在 `test_architecture_layers.py` 加上自己的规则条目。
- 分层测试会拦住「临时在函数里 import 一下」这种绕路，这是故意的。
- `domain/` 的收益是可以零 fixture 测试；一个 `open()` 或一个数据库 import 就会毁掉它，所以该层有独立的 I/O 禁止测试。
